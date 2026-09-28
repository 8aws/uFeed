<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { api, ApiError } from '$lib/api';
	import { locale, t } from '$lib/i18n';
	import { DeviceSpeech, readableText, speechSupported, type SpeechState } from '$lib/speech';
	import { speechPrefs } from '$lib/prefs';
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
		autostart = false
	}: {
		article: Article;
		title: string;
		sourceName: string;
		contentEl: HTMLElement | null;
		serverAllowed: boolean;
		autostart?: boolean; // accessibility: read as soon as the article opens
	} = $props();

	const SERVER_LANGS = ['es', 'en'];
	const RATES = [0.75, 0.85, 1, 1.1, 1.25, 1.5, 1.75, 2];
	const lang = $derived((article.lang || $locale || 'es').split(/[-_]/)[0].toLowerCase());
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

	// --- Device voice -----------------------------------------------------------
	let speech = $state.raw<DeviceSpeech | null>(null);
	let dState = $state<SpeechState>('idle');
	let dIndex = $state(0);
	let dTotal = $state(0);

	function devicePlay() {
		msg = '';
		speech ??= new DeviceSpeech(
			readableText(title, contentEl),
			lang,
			rate,
			(s, i, n) => {
				dState = s;
				dIndex = i;
				dTotal = n;
			},
			$speechPrefs.deviceVoice[lang]
		);
		if (dState === 'playing') speech.pause();
		else speech.play();
	}

	// --- Server voice -------------------------------------------------------------
	let sState = $state<'idle' | 'loading' | 'ready'>('idle');
	let url = $state('');
	let audioEl = $state<HTMLAudioElement | null>(null);

	async function serverLoad() {
		if (sState === 'loading') return;
		msg = '';
		sState = 'loading';
		try {
			const r = await api.articleAudio(article.id, lang, $speechPrefs.gender);
			url = r.url;
			sState = 'ready';
			await Promise.resolve();
			if (audioEl) {
				audioEl.playbackRate = rate;
				// After a long generation the tap no longer counts as a gesture
				// (iOS): then the player's own ▶ starts it.
				audioEl.play().catch(() => (msg = $t('listen_ready_tap')));
			}
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

	onMount(async () => {
		if (!autostart) return;
		await tick(); // the article body (below this bar) is bound by now
		// Content is rendered by now; the tap that opened the article still
		// counts as the gesture browsers require to start speaking.
		if (mode === 'server') serverLoad();
		else devicePlay();
	});
	function stopAll() {
		speech?.stop();
		audioEl?.pause();
	}
	onDestroy(() => {
		speech?.stop();
		audioEl?.pause();
	});
</script>

<div class="listen" role="group" aria-label={$t('listen')}>
	<div class="lrow">
		{#if mode === 'device'}
			<button class="pbtn" onclick={devicePlay} aria-label={dState === 'playing' ? 'pause' : 'play'}>
				{dState === 'playing' ? '⏸' : '▶'}
			</button>
			<button onclick={() => speech?.skip(-1)} disabled={!speech} aria-label="previous">⏮</button>
			<button onclick={() => speech?.skip(1)} disabled={!speech} aria-label="next">⏭</button>
			{#if dTotal}<span class="muted small">{dIndex + 1}/{dTotal}</span>{/if}
		{:else if sState === 'ready'}
			<audio
				bind:this={audioEl}
				src={url}
				controls
				preload="auto"
				onplay={onServerPlay}
				onloadedmetadata={() => audioEl && (audioEl.playbackRate = rate)}
			></audio>
		{:else}
			<button class="pbtn" onclick={serverLoad} disabled={sState === 'loading'} aria-label="play">
				{sState === 'loading' ? '⏳' : '▶'}
			</button>
			{#if sState === 'loading'}<span class="muted small">{$t('listen_preparing')}</span>{/if}
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
	</div>
	{#if serverAvailable && deviceAvailable}
		<div class="seg">
			<button class:active={mode === 'device'} onclick={() => setMode('device')}>📱 {$t('listen_device')}</button>
			<button class:active={mode === 'server'} onclick={() => setMode('server')}>☁️ {$t('listen_server')}</button>
		</div>
	{/if}
	{#if !deviceAvailable && !serverAvailable}<p class="muted small">{$t('listen_no_voice')}</p>{/if}
	{#if msg}<p class="muted small">{msg}</p>{/if}
</div>

<style>
	.listen {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin: 0.6rem 0;
		padding: 0.55rem 0.7rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface);
	}
	.lrow {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.lrow button {
		padding: 0.3rem 0.6rem;
	}
	.pbtn {
		min-width: 2.6rem;
		font-size: 1rem;
	}
	audio {
		flex: 1 1 220px;
		min-width: 0;
		height: 36px;
	}
	select {
		width: auto;
		padding: 0.25rem 0.35rem;
		margin-left: auto;
	}
	.seg {
		display: flex;
		gap: 0.3rem;
	}
	.seg button {
		font-size: 0.8rem;
		padding: 0.2rem 0.6rem;
		border-radius: 999px;
	}
	.seg button.active {
		background: var(--accent-soft);
		color: var(--accent);
		border-color: var(--accent);
	}
	.muted {
		color: var(--muted);
	}
	.small {
		font-size: 0.8rem;
		margin: 0;
	}
</style>
