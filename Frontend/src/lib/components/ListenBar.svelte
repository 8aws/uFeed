<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { locale, t } from '$lib/i18n';
	import {
		chunks,
		DeviceSpeech,
		readableText,
		speechSupported,
		translationText,
		unlockSpeech,
		type SpeechState
	} from '$lib/speech';
	import { speechPrefs } from '$lib/prefs';
	import { offlineAudioUrl } from '$lib/offlineAudio';
	import { chunkAt, SentenceHighlighter } from '$lib/highlight';
	import { sharedAudio } from '$lib/player';
	import type { Article } from '$lib/types';

	// Read the open article aloud: the device's voice (everyone, free, offline)
	// or the server's neural voice (plans with tts_server; cached MP3 that keeps
	// playing with the screen locked and shows lock-screen controls).
	let {
		article,
		title,
		sourceName,
		contentEl,
		serverAllowed,
		autostart = false,
		myLang = null,
		getTranslation,
		radio = null,
		onradio
	}: {
		article: Article;
		title: string;
		sourceName: string;
		contentEl: HTMLElement | null;
		serverAllowed: boolean;
		autostart?: boolean; // accessibility: read as soon as the article opens
		// "Read in my language": target language when the article must be
		// translated first, and how to get (and show) that translation.
		myLang?: string | null;
		getTranslation?: () => Promise<{ title: string | null; paragraphs: string[] } | null>;
		// Post radio: this post is one of a chain. The bar reports how much was
		// heard (0..1) when it ends, is skipped or the radio is stopped.
		radio?: {
			position: number; // 1-based
			limit: number | null; // posts in this session (null = until the list ends)
			url?: Promise<string | null>; // server audio requested ahead of time
			onfinish: (heard: number) => void;
			onskip: (heard: number) => void;
			onstop: (heard: number) => void;
		} | null;
		onradio?: () => void; // start Post radio from this post (plan feature)
	} = $props();

	const SERVER_LANGS = ['es', 'en'];
	const RATES = [0.75, 0.85, 1, 1.1, 1.25, 1.5, 1.75, 2];
	// Voice language: the translation's when reading in my language.
	const lang = $derived((myLang || article.lang || $locale || 'es').split(/[-_]/)[0].toLowerCase());
	const serverAvailable = $derived(serverAllowed && SERVER_LANGS.includes(lang));
	const deviceAvailable = speechSupported();

	// Engine actually used: the preferred one when it's possible here.
	let mode = $state<'device' | 'server'>('device');
	$effect.pre(() => {
		const want = $speechPrefs.mode;
		mode =
			want === 'server' && serverAvailable
				? 'server'
				: deviceAvailable
					? 'device'
					: serverAvailable
						? 'server'
						: 'device';
	});
	const rate = $derived($speechPrefs.rate);
	let msg = $state('');

	// --- Highlight of the sentence being read (Accessibility) -------------------
	let hl: SentenceHighlighter | null = null;
	async function highlighter(): Promise<SentenceHighlighter | null> {
		if (!$speechPrefs.highlight) return null;
		await tick(); // the translated body may have just been rendered
		if (!contentEl) return null;
		// The body changes when switching to the translation: index it again.
		if (hl && hl.element !== contentEl) {
			hl.destroy();
			hl = null;
		}
		hl ??= new SentenceHighlighter(contentEl);
		return hl;
	}

	// The first chunks are the title (shown above the body). Some feeds repeat it
	// in a footer ("<title> appeared first on…"): searching for it there made
	// the highlight jump down and back, so title chunks aren't highlighted.
	let titleParts = 0;
	const titleChunks = (t: string | null) => (t ? chunks(`${t}.`).length : 0);

	// --- Device voice -----------------------------------------------------------
	let speech = $state.raw<DeviceSpeech | null>(null);
	let dState = $state<SpeechState>('idle');
	let dIndex = $state(0);
	let dTotal = $state(0);
	let dMax = 0; // furthest chunk reached (for "heard")

	async function devicePlay() {
		msg = '';
		if (!speech && myLang && getTranslation) {
			unlockSpeech(); // keep the tap's permission to speak across the await
			dState = 'playing';
			const tr = await getTranslation().catch(() => null);
			if (!tr) {
				dState = 'idle';
				msg = $t('translate_unavailable');
				return;
			}
			await highlighter();
			titleParts = titleChunks(tr.title);
			speech = makeSpeech(translationText(tr.title, tr.paragraphs));
			speech.play();
			return;
		}
		if (!speech) {
			await highlighter();
			titleParts = titleChunks(title);
		}
		speech ??= makeSpeech(readableText(title, contentEl));
		if (dState === 'playing') speech.pause();
		else speech.play();
	}

	function makeSpeech(text: string) {
		return new DeviceSpeech(
			text,
			lang,
			rate,
			(s, i, n) => {
				dState = s;
				dIndex = i;
				dTotal = n;
				if (s === 'playing') {
					dMax = Math.max(dMax, i);
					if (i >= titleParts) hl?.show(speech?.part(i) ?? '');
				} else if (s === 'ended' || s === 'idle') hl?.clear();
				if (s === 'ended') radio?.onfinish(1);
			},
			$speechPrefs.deviceVoice[lang]
		);
	}

	// --- Server voice -------------------------------------------------------------
	let sState = $state<'idle' | 'loading' | 'ready'>('idle');
	let url = $state('');
	// The app-wide element (see lib/player): this bar only acts on it while it
	// "owns" it, i.e. while it's playing this article.
	const me = Math.random().toString(36).slice(2);
	let audioEl = $state<HTMLAudioElement | null>(null);
	const owned = () => !!audioEl && audioEl.dataset.owner === me;
	let sMax = 0; // furthest position reached (s)
	let estSeconds = 0; // length estimate while the live stream has no duration
	// Recordings carry no sentence timing: estimate it from the position.
	let serverChunks: string[] = [];
	let serverIdx = -1;
	let sPlaying = $state(false);
	let sTime = $state(0);
	let sDur = $state(0);
	const mmss = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
	function serverToggle() {
		if (!audioEl) return;
		if (audioEl.paused) audioEl.play().catch(() => (msg = $t('listen_ready_tap')));
		else audioEl.pause();
	}
	function serverSeek(delta: number) {
		if (audioEl) audioEl.currentTime = Math.max(0, Math.min(sDur || 0, audioEl.currentTime + delta));
	}
	// Live streams report no duration until done: use the estimate meanwhile.
	const durationOf = (a: HTMLAudioElement) => (Number.isFinite(a.duration) && a.duration > 0 ? a.duration : estSeconds);
	function onTimeUpdate() {
		if (!owned() || !audioEl) return;
		sTime = audioEl.currentTime;
		sDur = durationOf(audioEl);
		sMax = Math.max(sMax, sTime);
		if (!hl || !sDur || !serverChunks.length) return;
		const i = chunkAt(serverChunks, Math.min(1, audioEl.currentTime / sDur));
		if (i !== serverIdx) {
			serverIdx = i;
			if (i >= titleParts) hl.show(serverChunks[i]);
		}
	}

	async function serverLoad() {
		if (sState === 'loading') return;
		msg = '';
		sState = 'loading';
		try {
			// A recording kept for offline use plays at once (and without connection).
			const stored = await offlineAudioUrl(article.id, lang, $speechPrefs.gender);
			const tr = myLang && getTranslation ? await getTranslation().catch(() => null) : null; // also shows it
			await highlighter();
			const spoken = tr ? translationText(tr.title, tr.paragraphs) : readableText(title, contentEl);
			titleParts = titleChunks(tr ? tr.title : title);
			serverChunks = chunks(spoken);
			serverIdx = -1;
			// Piper reads ~14.5 characters per second of audio at normal speed.
			estSeconds = spoken.length / 14.5;
			url =
				stored ??
				(radio?.url ? await radio.url : null) ??
				(await api.articleAudio(article.id, lang, $speechPrefs.gender, !!myLang)).url;
			sState = 'ready';
			audioEl = sharedAudio();
			audioEl.dataset.owner = me;
			audioEl.src = url;
			audioEl.defaultPlaybackRate = rate;
			audioEl.playbackRate = rate;
			// Live audio starts after the first sentence. If a tap no longer
			// counts (long wait on iOS), the ▶ button starts it.
			audioEl.play().catch(() => (msg = $t('listen_ready_tap')));
		} catch (e) {
			sState = 'idle';
			const code = e instanceof ApiError ? e.code : '';
			if (code === 'tts_lang') {
				msg = $t('listen_lang_unsupported');
				mode = 'device';
			} else if (code === 'plan_limit_tts') msg = $t('listen_plan');
			else if (code === 'rate_limited') msg = $t('listen_rate_limited');
			else msg = $t('listen_unavailable');
		}
	}

	function onServerPlay() {
		if (!owned()) return;
		sPlaying = true;
		if (!('mediaSession' in navigator)) return;
		navigator.mediaSession.metadata = new MediaMetadata({
			title,
			artist: sourceName,
			album: 'uFeed',
			artwork: [{ src: '/icon-512.png', sizes: '512x512', type: 'image/png' }]
		});
	}

	// --- Shared -------------------------------------------------------------------
	function setMode(m: 'device' | 'server') {
		if (m === mode) return;
		stopAll();
		speechPrefs.update((p) => ({ ...p, mode: m }));
	}
	function setRate(r: number) {
		speechPrefs.update((p) => ({ ...p, rate: r }));
		speech?.setRate(r);
		if (audioEl) audioEl.playbackRate = r;
	}

	// Listeners on the shared element, for as long as this bar exists.
	const onPause = () => owned() && (sPlaying = false);
	const onMeta = () => {
		if (owned() && audioEl) {
			audioEl.playbackRate = rate;
			sDur = durationOf(audioEl);
		}
	};
	// A live stream (still being generated) has no known duration. Safari may
	// fire 'ended' when it catches up with what's generated so far, not at the
	// real end: then wait for the finished file (it answers byte ranges with
	// 206) and continue from the same second. Chrome ends at the real end; the
	// same check then just confirms it.
	let recovering = false;
	const onEnded = () => {
		if (!owned() || !audioEl) return;
		if (!Number.isFinite(audioEl.duration) && !recovering) {
			void recoverLive(audioEl.currentTime);
			return;
		}
		finished();
	};
	function finished() {
		sPlaying = false;
		hl?.clear();
		radio?.onfinish(1);
	}
	async function recoverLive(pos: number) {
		recovering = true;
		const a = audioEl!;
		try {
			for (let i = 0; i < 120 && owned(); i++) {
				const ctl = new AbortController();
				const r = await fetch(url, { headers: { Range: 'bytes=0-0' }, signal: ctl.signal }).catch(() => null);
				ctl.abort();
				if (r?.status === 206) {
					a.src = `${url}&final=1`; // the complete file, seekable
					await new Promise<void>((ok) => a.addEventListener('loadedmetadata', () => ok(), { once: true }));
					if (!owned()) return;
					if (pos >= a.duration - 1.5) return finished(); // it really had ended
					a.currentTime = pos;
					sMax = Math.max(sMax, pos);
					await a.play().catch(() => (msg = $t('listen_ready_tap')));
					return;
				}
				await new Promise((ok) => setTimeout(ok, 1000));
			}
		} finally {
			recovering = false;
		}
	}
	onMount(() => {
		const a = sharedAudio();
		a.addEventListener('play', onServerPlay);
		a.addEventListener('pause', onPause);
		a.addEventListener('timeupdate', onTimeUpdate);
		a.addEventListener('loadedmetadata', onMeta);
		a.addEventListener('ended', onEnded);
		// Lock screen / headphones "next" skips to the next post.
		if (radio && 'mediaSession' in navigator) {
			navigator.mediaSession.setActionHandler('nexttrack', () => radio?.onskip(heard()));
		}
		return () => {
			a.removeEventListener('play', onServerPlay);
			a.removeEventListener('pause', onPause);
			a.removeEventListener('timeupdate', onTimeUpdate);
			a.removeEventListener('loadedmetadata', onMeta);
			a.removeEventListener('ended', onEnded);
			if (radio && 'mediaSession' in navigator) navigator.mediaSession.setActionHandler('nexttrack', null);
		};
	});

	/** How much of this post was heard (0..1): Post radio marks it read at 70 %. */
	function heard(): number {
		if (mode === 'device') return dTotal ? (dMax + 1) / dTotal : 0;
		const d = audioEl && owned() ? durationOf(audioEl) : 0;
		return d ? Math.min(1, sMax / d) : 0;
	}

	onMount(async () => {
		if (!autostart && !radio) return;
		await tick(); // the article body (below this bar) is bound by now
		// Content is rendered by now; the tap that opened the article still
		// counts as the gesture browsers require to start speaking.
		if (mode === 'server') serverLoad();
		else devicePlay();
	});
	function stopAll() {
		speech?.stop();
		if (owned()) audioEl?.pause();
	}
	onDestroy(() => {
		speech?.stop();
		if (owned()) audioEl?.pause();
		hl?.destroy();
	});
</script>

<!-- One slim row, pinned with the reader header: the controls stay in reach
     while the article scrolls (and the highlight follows the text). -->
<div class="listen" role="group" aria-label={$t('listen')}>
	{#if mode === 'device'}
		<button class="pbtn" onclick={devicePlay} aria-label={dState === 'playing' ? 'pause' : 'play'}>
			{dState === 'playing' ? '⏸' : '▶'}
		</button>
		<button onclick={() => speech?.skip(-1)} disabled={!speech} aria-label="previous">⏮</button>
		<button onclick={() => speech?.skip(1)} disabled={!speech} aria-label="next">⏭</button>
		<span class="prog">
			{#if dTotal}
				<span class="bar"><span style="width: {((dIndex + 1) / dTotal) * 100}%"></span></span>
				<span class="muted small">{dIndex + 1}/{dTotal}</span>
			{/if}
		</span>
	{:else}
		<button
			class="pbtn"
			onclick={sState === 'ready' ? serverToggle : serverLoad}
			disabled={sState === 'loading'}
			aria-label={sPlaying ? 'pause' : 'play'}
		>
			{sState === 'loading' ? '⏳' : sPlaying ? '⏸' : '▶'}
		</button>
		<button onclick={() => serverSeek(-15)} disabled={sState !== 'ready'} aria-label="-15 s">↺15</button>
		<button onclick={() => serverSeek(15)} disabled={sState !== 'ready'} aria-label="+15 s">15↻</button>
		<span class="prog">
			{#if sState === 'loading'}
				<span class="muted small">{$t('listen_preparing')}</span>
			{:else if sState === 'ready'}
				<input
					type="range"
					min="0"
					max={sDur || 0}
					step="1"
					value={sTime}
					oninput={(e) => audioEl && (audioEl.currentTime = Number((e.currentTarget as HTMLInputElement).value))}
					aria-label="position"
				/>
				<span class="muted small time">{mmss(sTime)}/{mmss(sDur)}</span>
			{/if}
		</span>
	{/if}
	{#if onradio && !radio}
		<button onclick={onradio} title={$t('post_radio_start')} aria-label={$t('post_radio_start')}>📻</button>
	{/if}
	{#if radio}
		<span class="radio" title={$t('post_radio')}>📻 {radio.position}{radio.limit ? `/${radio.limit}` : ''}</span>
		<button onclick={() => radio?.onskip(heard())} title={$t('radio_next')} aria-label={$t('radio_next')}>⏭📰</button>
		<button onclick={() => radio?.onstop(heard())} title={$t('radio_stop')} aria-label={$t('radio_stop')}>⏹</button>
	{/if}
	<select
		value={rate}
		onchange={(e) => setRate(Number((e.currentTarget as HTMLSelectElement).value))}
		aria-label={$t('listen_speed')}
	>
		{#each RATES.includes(rate) ? RATES : [...RATES, rate].sort((a, b) => a - b) as r (r)}
			<option value={r}>{r}×</option>
		{/each}
	</select>
	{#if serverAvailable && deviceAvailable}
		<button
			class="engine"
			onclick={() => setMode(mode === 'device' ? 'server' : 'device')}
			title={mode === 'device' ? $t('listen_device') : $t('listen_server')}
			aria-label={mode === 'device' ? $t('listen_device') : $t('listen_server')}
		>
			{mode === 'device' ? '📱' : '☁️'}
		</button>
	{/if}
	{#if msg || (!deviceAvailable && !serverAvailable)}
		<p class="msg muted small">{msg || $t('listen_no_voice')}</p>
	{/if}
</div>

<style>
	.listen {
		flex: 1 1 100%;
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.3rem;
		padding: 0.3rem 0.45rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface);
	}
	.listen button {
		padding: 0.25rem 0.5rem;
		font-size: 0.9rem;
		flex: none;
	}
	.pbtn {
		min-width: 2.4rem;
	}
	.radio {
		font-size: 0.8rem;
		color: var(--accent);
		font-variant-numeric: tabular-nums;
	}
	.prog {
		flex: 1 1 5rem;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.bar {
		flex: 1;
		height: 4px;
		border-radius: 2px;
		background: var(--border);
		overflow: hidden;
	}
	.bar > span {
		display: block;
		height: 100%;
		background: var(--accent);
	}
	.prog input[type='range'] {
		flex: 1;
		min-width: 0;
		padding: 0;
		accent-color: var(--accent);
	}
	.time {
		flex: none;
		font-variant-numeric: tabular-nums;
	}
	select {
		width: auto;
		flex: none;
		padding: 0.2rem 0.3rem;
	}
	.msg {
		flex: 1 1 100%;
	}
	.muted {
		color: var(--muted);
	}
	.small {
		font-size: 0.78rem;
		margin: 0;
	}
</style>
