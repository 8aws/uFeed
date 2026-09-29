<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError, downloadOpml, importOpml } from '$lib/api';
	import { clearTokens, setTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import { displayPrefs, PACES, speechPrefs, TEXT_SCALES, toolbarLabels, type ToolbarLabels } from '$lib/prefs';
	import { sampleVoice, speechSupported, voicesFor } from '$lib/speech';
	import { clearAudio, warmAudio } from '$lib/offlineAudio';
	import { relativeTime } from '$lib/format';
	import type {
		PlanLimits,
		ApiKey,
		ApiKeyCreated,
		Folder,
		Locale,
		MutedKeyword,
		Role,
		SourceHealth,
		Subscription
	} from '$lib/types';
	import { safeUrl } from '$lib/safe';
	import { CATALOG, LANG_FLAG, fetchCatalog, type CatalogFeed, type CatalogSection, type FeedLang } from '$lib/catalog';
	import { addCatalogFeed, ensureFolder, feedKey } from '$lib/catalogActions';

	const LABEL_MODES: ToolbarLabels[] = ['auto', 'both', 'icons', 'text'];

	let importMsg = $state('');
	let fileInput: HTMLInputElement | undefined = $state();
	let displayName = $state($user?.display_name ?? '');
	let nameSaved = $state(false);

	async function changeLanguage(value: Locale) {
		setLocale(value);
		try {
			await api.updateMe({ locale: value });
		} catch {
			/* not fatal */
		}
	}

	async function saveName() {
		try {
			const updated = await api.updateMe({ display_name: displayName.trim() });
			user.set(updated);
			nameSaved = true;
			setTimeout(() => (nameSaved = false), 1500);
		} catch {
			/* ignore */
		}
	}

	// --- Starter suggestions: the onboarding catalogue, editable any time ---
	// Every section starts collapsed so the page stays short; the password one
	// opens itself when linked to (#password) or when a change is required.
	let open = $state<Record<string, boolean>>({});
	function toggle(key: string) {
		open[key] = !open[key];
	}
	$effect(() => {
		if ($user?.must_change_password || location.hash === '#password') open.password = true;
	});

	let catalog = $state<CatalogSection[]>(CATALOG);
	let starterOpen = $state(false);
	let starterLoaded = false;
	let catSubs = $state<Subscription[]>([]);
	let catFolders: Folder[] = [];
	let catBusy = $state<Set<string>>(new Set());
	let catFilter = $state<'all' | FeedLang>('all');
	const subByKey = $derived(new Map(catSubs.map((x) => [feedKey(x.source.feed_url), x])));

	function catName(s: CatalogSection): string {
		return $locale === 'es' ? s.name_es : s.name_en;
	}
	function catFeeds(s: CatalogSection): CatalogFeed[] {
		const mine: FeedLang = $locale === 'es' ? 'es' : 'en';
		return s.feeds
			.filter((f) => catFilter === 'all' || f.lang === catFilter)
			.sort((a, b) => Number(b.lang === mine) - Number(a.lang === mine));
	}
	function isSub(f: CatalogFeed): boolean {
		return subByKey.has(feedKey(f.url));
	}
	function setBusy(url: string, on: boolean) {
		const next = new Set(catBusy);
		if (on) next.add(url);
		else next.delete(url);
		catBusy = next;
	}

	async function toggleStarter() {
		starterOpen = !starterOpen;
		if (starterOpen && !starterLoaded) {
			starterLoaded = true;
			try {
				[catSubs, catFolders, catalog] = await Promise.all([
					api.listSources(),
					api.listFolders(),
					fetchCatalog()
				]);
			} catch {
				starterLoaded = false;
			}
		}
	}

	async function addFeed(s: CatalogSection, f: CatalogFeed) {
		if (catBusy.has(f.url) || isSub(f)) return;
		setBusy(f.url, true);
		catMsg = '';
		try {
			const folder = await ensureFolder(catName(s), catFolders);
			const sub = await addCatalogFeed(f, folder?.id ?? null);
			// The worker fetches new sources on its next tick; no manual refresh,
			// which would spend the plan's refresh cooldown.
			if (sub) catSubs = [...catSubs, sub];
		} catch (e) {
			if (e instanceof ApiError && e.code === 'plan_limit_feeds') catMsg = $t('plan_limit_feeds');
		} finally {
			setBusy(f.url, false);
		}
	}

	async function removeFeed(f: CatalogFeed) {
		const sub = subByKey.get(feedKey(f.url));
		if (!sub || catBusy.has(f.url)) return;
		setBusy(f.url, true);
		try {
			await api.unsubscribe(sub.id);
			catSubs = catSubs.filter((x) => x.id !== sub.id);
		} catch {
			/* ignore */
		} finally {
			setBusy(f.url, false);
		}
	}

	async function addAll(s: CatalogSection) {
		for (const f of catFeeds(s)) if (!isSub(f)) await addFeed(s, f);
	}

	// --- Filters: muted keywords and muted sources (lazy) ---
	let filtersOpen = $state(false);
	let keywords = $state<MutedKeyword[]>([]);
	let mutedSubs = $state<Subscription[]>([]);
	let newKeyword = $state('');

	async function toggleFilters() {
		filtersOpen = !filtersOpen;
		if (filtersOpen) {
			try {
				const [k, subs] = await Promise.all([api.listKeywords(), api.listSources()]);
				keywords = k;
				mutedSubs = subs.filter((x) => x.muted);
			} catch {
				/* ignore */
			}
		}
	}

	async function addKeyword(e: SubmitEvent) {
		e.preventDefault();
		const kw = newKeyword.trim();
		if (!kw) return;
		try {
			const row = await api.addKeyword(kw);
			if (!keywords.some((k) => k.id === row.id)) keywords = [...keywords, row];
			newKeyword = '';
		} catch {
			/* ignore */
		}
	}

	async function removeKeyword(k: MutedKeyword) {
		try {
			await api.removeKeyword(k.id);
			keywords = keywords.filter((x) => x.id !== k.id);
		} catch {
			/* ignore */
		}
	}

	async function unmuteSub(sub: Subscription) {
		try {
			await api.updateSubscription(sub.id, { muted: false });
			mutedSubs = mutedSubs.filter((x) => x.id !== sub.id);
		} catch {
			/* ignore */
		}
	}

	// --- Feed health (lazy, collapsed by default) ---
	let healthOpen = $state(false);
	let health = $state<SourceHealth[] | null>(null);
	const healthProblems = $derived((health ?? []).filter((h) => h.status !== 'ok'));

	async function toggleHealth() {
		healthOpen = !healthOpen;
		if (healthOpen && health === null) {
			try {
				health = await api.sourcesHealth();
			} catch {
				health = [];
			}
		}
	}

	async function unsubscribeFeed(h: SourceHealth) {
		if (!h.subscription_id) return;
		try {
			await api.unsubscribe(h.subscription_id);
			health = (health ?? []).filter((x) => x.subscription_id !== h.subscription_id);
		} catch {
			/* ignore */
		}
	}

	// --- Password ---
	let curPw = $state('');
	let newPw = $state('');
	let newPw2 = $state('');
	let pwMsg = $state('');
	let pwOk = $state(false);
	let pwBusy = $state(false);

	async function changePassword(e: SubmitEvent) {
		e.preventDefault();
		pwOk = false;
		if (newPw.length < 8) return void (pwMsg = $t('password_too_short'));
		if (newPw !== newPw2) return void (pwMsg = $t('password_mismatch'));
		pwBusy = true;
		try {
			const tokens = await api.changePassword(curPw, newPw);
			setTokens(tokens.access_token, tokens.refresh_token); // keep this session
			user.set(await api.me());
			curPw = newPw = newPw2 = '';
			pwOk = true;
			pwMsg = $t('password_changed');
		} catch (err) {
			pwMsg = err instanceof ApiError && err.code === 'wrong_password' ? $t('wrong_password') : '⚠';
		} finally {
			pwBusy = false;
		}
	}

	// --- API keys (read-only access for external apps such as OneDay) ---
	let keys = $state<ApiKey[]>([]);
	let newKeyName = $state('OneDay');
	let created = $state<ApiKeyCreated | null>(null);
	let copied = $state<'url' | 'key' | null>(null);
	let serverUrl = $state('');
	let allowState = $state(true);
	let myPlan = $state<PlanLimits | null>(null);
	let keyMsg = $state('');
	let catMsg = $state('');

	function scopeLabels(k: ApiKey): string {
		const sc = k.scopes.length ? k.scopes : ['read', 'state']; // [] = full access
		return sc.map((x) => $t(x === 'state' ? 'scope_state' : 'scope_read')).join(' · ');
	}

	function planSummary(p: PlanLimits): string {
		const parts = [
			p.refresh_cooldown_s > 0
				? `${$t('refresh_every')} ${Math.round(p.refresh_cooldown_s / 60)} min`
				: $t('refresh_immediate'),
			`${p.max_feeds === null ? $t('unlimited') : `${$t('up_to')} ${p.max_feeds}`} ${$t('feeds_short')}`,
			`${p.max_api_keys === null ? $t('unlimited') : `${$t('up_to')} ${p.max_api_keys}`} ${$t('api_keys_short')}`,
			p.ai_features ? $t('ai_yes') : $t('ai_no'),
			...(p.tts_server ? [`🔊 ${$t('tts_server_plan')}`] : [])
		];
		return parts.join(' · ');
	}

	// --- Read aloud -------------------------------------------------------------
	const SPEECH_LANGS = ['es', 'en'] as const;
	const SAMPLES: Record<string, string> = {
		es: 'Hola, así sonarán tus artículos en uFeed.',
		en: 'Hi, this is how your articles will sound in uFeed.'
	};
	let deviceVoices = $state<Record<string, string[]>>({ es: [], en: [] });
	function loadVoices() {
		deviceVoices = Object.fromEntries(SPEECH_LANGS.map((l) => [l, voicesFor(l).map((v) => `${v.name}|${v.lang}`)]));
	}
	function toggleSpeech() {
		toggle('speech');
		if (open.speech && speechSupported()) {
			loadVoices();
			// Chrome lists voices asynchronously.
			speechSynthesis.addEventListener('voiceschanged', loadVoices, { once: true });
		}
	}
	function setDeviceVoice(lang: string, name: string) {
		speechPrefs.update((p) => ({ ...p, deviceVoice: { ...p.deviceVoice, [lang]: name } }));
	}
	let audioMsg = $state('');
	async function toggleOfflineAudio(on: boolean) {
		speechPrefs.update((p) => ({ ...p, offlineAudio: on }));
		audioMsg = '';
		if (!on) {
			await clearAudio();
			return;
		}
		try {
			const saved = (await api.listArticles({ saved: 'true', limit: '20' })).items;
			audioMsg = $t('offline_audio_started');
			const mt = ['es', 'en'];
			await warmAudio(saved, {
				gender: $speechPrefs.gender,
				myLang: $speechPrefs.myLanguage ? $locale : null,
				canTranslate: (a) => {
					const src = (a.lang || '').split(/[-_]/)[0].toLowerCase();
					return !!myPlan?.ai_features && mt.includes(src) && mt.includes($locale) && src !== $locale;
				}
			});
			audioMsg = $t('offline_audio_done');
		} catch {
			audioMsg = '';
		}
	}
	const paceOf = (r: number) =>
		(Object.entries(PACES).find(([, v]) => Math.abs(v - r) < 0.01)?.[0] ?? '') as string;

	async function loadKeys() {
		try {
			keys = (await api.listKeys()).filter((k) => !k.revoked_at);
		} catch {
			/* ignore */
		}
	}

	async function createKey() {
		const name = newKeyName.trim();
		if (!name) return;
		try {
			keyMsg = '';
			created = await api.createKey(name, allowState ? ['read', 'state'] : ['read']);
			await loadKeys();
		} catch (e) {
			keyMsg = e instanceof ApiError && e.code === 'plan_limit_keys' ? $t('plan_limit_keys') : '⚠';
		}
	}

	async function revokeKey(k: ApiKey) {
		if (!confirm($t('confirm_revoke'))) return;
		try {
			await api.revokeKey(k.id);
			if (created?.id === k.id) created = null;
			await loadKeys();
		} catch {
			/* ignore */
		}
	}

	async function copy(text: string, what: 'url' | 'key') {
		try {
			await navigator.clipboard.writeText(text);
			copied = what;
			setTimeout(() => (copied = null), 1500);
		} catch {
			/* clipboard unavailable: the value is selectable on screen */
		}
	}

	onMount(() => {
		serverUrl = window.location.origin;
		loadKeys();
		api
			.site()
			.then((c) => (myPlan = $user ? (c.plan_limits[$user.role as Role] ?? null) : null))
			.catch(() => {});
	});

	async function onImport(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		importMsg = '';
		try {
			const res = await importOpml(file);
			importMsg = `+${res.imported} / ${res.skipped} skipped`;
		} catch {
			importMsg = '⚠';
		}
		input.value = '';
	}

	function logout() {
		clearTokens();
		goto('/login');
	}
</script>

<div class="page">
	<a class="back" href="/">← {$t('app_name')}</a>
	<h1>{$t('settings')}</h1>
	{#if $user?.role === 'admin'}
		<a class="adminlink" href="/admin">🛡 {$t('admin')} →</a>
	{/if}
	{#if $user?.role === 'editor' || $user?.role === 'admin'}
		<a class="adminlink" href="/curation">✎ {$t('curation')} →</a>
	{/if}

	<section>
		<button class="collapse" onclick={() => toggle('language')} aria-expanded={!!open.language}>
			<h2>{$t('language')}</h2>
			<span class="chev" aria-hidden="true">{open.language ? '▾' : '▸'}</span>
		</button>
		{#if open.language}
			<div class="row">
				<button class:active={$locale === 'en'} onclick={() => changeLanguage('en')}>English</button>
				<button class:active={$locale === 'es'} onclick={() => changeLanguage('es')}>Español</button>
			</div>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('appearance')} aria-expanded={!!open.appearance}>
			<h2>{$t('appearance')}</h2>
			<span class="chev" aria-hidden="true">{open.appearance ? '▾' : '▸'}</span>
		</button>
		{#if open.appearance}
			<div class="field">
				{$t('toolbar_labels')}
				<div class="row">
					{#each LABEL_MODES as m (m)}
						<button class:active={$toolbarLabels === m} onclick={() => toolbarLabels.set(m)}>
							{$t(`labels_${m}` as 'labels_auto')}
						</button>
					{/each}
				</div>
			</div>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={toggleSpeech} aria-expanded={!!open.speech}>
			<h2>🔊 {$t('speech_settings')}</h2>
			<span class="chev" aria-hidden="true">{open.speech ? '▾' : '▸'}</span>
		</button>
		{#if open.speech}
			<div class="field">
				{$t('pace')}
				<div class="row">
					{#each Object.entries(PACES) as [name, r] (name)}
						<button
							class:active={paceOf($speechPrefs.rate) === name}
							onclick={() => speechPrefs.update((p) => ({ ...p, rate: r }))}
						>
							{$t(`pace_${name}` as 'pace_calm')}
						</button>
					{/each}
				</div>
			</div>
			{#if myPlan?.ai_features}
				<label class="check">
					<input
						type="checkbox"
						checked={$speechPrefs.myLanguage}
						onchange={(e) =>
							speechPrefs.update((p) => ({ ...p, myLanguage: (e.currentTarget as HTMLInputElement).checked }))}
					/>
					{$t('read_my_lang')}
				</label>
				<p class="muted small">{$t('read_my_lang_hint')}</p>
			{/if}
			{#if myPlan?.tts_server}
				<div class="field">
					{$t('speech_engine')}
					<div class="row">
						<button
							class:active={$speechPrefs.mode === 'device'}
							onclick={() => speechPrefs.update((p) => ({ ...p, mode: 'device' }))}
						>
							📱 {$t('device_voice')}
						</button>
						<button
							class:active={$speechPrefs.mode === 'server'}
							onclick={() => speechPrefs.update((p) => ({ ...p, mode: 'server' }))}
						>
							☁️ {$t('server_voice')}
						</button>
					</div>
				</div>
				<div class="field">
					{$t('server_voice')}
					<div class="row">
						<button
							class:active={$speechPrefs.gender === 'f'}
							onclick={() => speechPrefs.update((p) => ({ ...p, gender: 'f' }))}
						>
							{$t('voice_female')}
						</button>
						<button
							class:active={$speechPrefs.gender === 'm'}
							onclick={() => speechPrefs.update((p) => ({ ...p, gender: 'm' }))}
						>
							{$t('voice_male')}
						</button>
					</div>
					<span class="muted small">{$t('server_voice_hint')}</span>
				</div>
				<label class="check">
					<input
						type="checkbox"
						checked={$speechPrefs.offlineAudio}
						onchange={(e) => toggleOfflineAudio((e.currentTarget as HTMLInputElement).checked)}
					/>
					🎧 {$t('offline_audio')}
				</label>
				<p class="muted small">{audioMsg || $t('offline_audio_hint')}</p>
			{/if}
			{#if myPlan?.post_radio}
				<div class="field">
					📻 {$t('post_radio')} · {$t('radio_stop_after')}
					<div class="row">
						<select
							value={$speechPrefs.radioPosts}
							onchange={(e) =>
								speechPrefs.update((p) => ({ ...p, radioPosts: Number((e.currentTarget as HTMLSelectElement).value) }))}
							aria-label={$t('radio_posts')}
						>
							{#each [5, 10, 20, 50, 0].filter((n) => n === 0 || myPlan?.radio_max_posts == null || n <= myPlan.radio_max_posts) as n (n)}
								<option value={n}>{n === 0 ? (myPlan?.radio_max_posts ?? $t('radio_unlimited')) : n} {$t('radio_posts')}</option>
							{/each}
						</select>
						<select
							value={$speechPrefs.radioMinutes}
							onchange={(e) =>
								speechPrefs.update((p) => ({ ...p, radioMinutes: Number((e.currentTarget as HTMLSelectElement).value) }))}
							aria-label={$t('radio_minutes')}
						>
							{#each [15, 30, 60, 120, 0].filter((n) => n === 0 || myPlan?.radio_max_minutes == null || n <= myPlan.radio_max_minutes) as n (n)}
								<option value={n}>{n === 0 ? (myPlan?.radio_max_minutes ?? $t('radio_unlimited')) : n} {$t('radio_minutes')}</option>
							{/each}
						</select>
					</div>
					<span class="muted small">{$t('radio_hint')}</span>
				</div>
			{/if}
			{#if speechSupported()}
				<div class="field">
					{$t('device_voice')}
					{#each SPEECH_LANGS as l (l)}
						<div class="row">
							<span class="vlang">{LANG_FLAG[l]} {$t(`lang_${l}_name` as 'lang_es_name')}</span>
							<select
								value={$speechPrefs.deviceVoice[l] ?? ''}
								onchange={(e) => setDeviceVoice(l, (e.currentTarget as HTMLSelectElement).value)}
							>
								<option value="">{$t('voice_auto')}</option>
								{#each deviceVoices[l] as v (v)}
									<option value={v.split('|')[0]}>{v.split('|')[0]} ({v.split('|')[1]})</option>
								{/each}
							</select>
							<button onclick={() => sampleVoice(l, $speechPrefs.deviceVoice[l] ?? '', $speechPrefs.rate, SAMPLES[l])}>
								▶ {$t('voice_try')}
							</button>
						</div>
					{/each}
					<span class="muted small">{$t('device_voice_hint')}</span>
				</div>
			{/if}
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('a11y')} aria-expanded={!!open.a11y}>
			<h2>♿ {$t('accessibility')}</h2>
			<span class="chev" aria-hidden="true">{open.a11y ? '▾' : '▸'}</span>
		</button>
		{#if open.a11y}
			<div class="field">
				{$t('text_size')}
				<div class="row">
					{#each TEXT_SCALES as sc (sc)}
						<button
							class:active={$displayPrefs.textScale === sc}
							style="font-size: {0.8 + (sc - 1) * 0.9}rem"
							onclick={() => displayPrefs.update((p) => ({ ...p, textScale: sc }))}
							aria-label="{Math.round(sc * 100)}%"
						>
							A <span class="muted small">{Math.round(sc * 100)}%</span>
						</button>
					{/each}
				</div>
			</div>
			<div class="field">
				{$t('font')}
				<div class="row">
					<button
						class:active={$displayPrefs.font === 'system'}
						onclick={() => displayPrefs.update((p) => ({ ...p, font: 'system' }))}
					>
						{$t('font_system')}
					</button>
					<button
						class="atkinson"
						class:active={$displayPrefs.font === 'atkinson'}
						onclick={() => displayPrefs.update((p) => ({ ...p, font: 'atkinson' }))}
					>
						Atkinson Hyperlegible
					</button>
				</div>
				<span class="muted small">{$t('font_hint')}</span>
			</div>
			<label class="check">
				<input
					type="checkbox"
					checked={$speechPrefs.autoRead}
					onchange={(e) =>
						speechPrefs.update((p) => ({ ...p, autoRead: (e.currentTarget as HTMLInputElement).checked }))}
				/>
				{$t('auto_read')}
			</label>
			<p class="muted small">{$t('auto_read_hint')}</p>
			<label class="check">
				<input
					type="checkbox"
					checked={$speechPrefs.highlight}
					onchange={(e) =>
						speechPrefs.update((p) => ({ ...p, highlight: (e.currentTarget as HTMLInputElement).checked }))}
				/>
				{$t('highlight_reading')}
			</label>
			<p class="muted small">{$t('highlight_hint')}</p>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('feeds')} aria-expanded={!!open.feeds}>
			<h2>{$t('feeds')}</h2>
			<span class="chev" aria-hidden="true">{open.feeds ? '▾' : '▸'}</span>
		</button>
		{#if open.feeds}
			<div class="row">
				<button onclick={() => fileInput?.click()}>{$t('import_opml')}</button>
				<button onclick={downloadOpml}>{$t('export_opml')}</button>
				<input
					type="file"
					accept=".opml,.xml,text/xml,application/xml"
					bind:this={fileInput}
					onchange={onImport}
					hidden
				/>
				{#if importMsg}<span class="muted">{importMsg}</span>{/if}
			</div>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={toggleFilters} aria-expanded={filtersOpen}>
			<h2>🔇 {$t('filters')}</h2>
			<span class="chev" aria-hidden="true">{filtersOpen ? '▾' : '▸'}</span>
		</button>
		{#if filtersOpen}
			<p class="muted hint">{$t('filters_hint')}</p>
			<form class="row" onsubmit={addKeyword}>
				<input bind:value={newKeyword} maxlength="100" placeholder={$t('add_keyword')} />
				<button type="submit" disabled={!newKeyword.trim()}>+</button>
			</form>
			{#if keywords.length}
				<div class="chips">
					{#each keywords as k (k.id)}
						<span class="kchip">
							{k.keyword}
							<button class="chipx" aria-label="✕" onclick={() => removeKeyword(k)}>✕</button>
						</span>
					{/each}
				</div>
			{/if}
			<h3 class="subh">{$t('muted_sources')}</h3>
			<p class="muted small">{$t('muted_sources_hint')}</p>
			{#if mutedSubs.length === 0}
				<p class="muted small">{$t('no_muted')}</p>
			{:else}
				<ul class="cfeeds">
					{#each mutedSubs as m (m.id)}
						<li>
							<span class="ftitle">🔇 {m.custom_title || m.source.title || m.source.feed_url}</span>
							<button class="small-btn" onclick={() => unmuteSub(m)}>🔊 {$t('unmute')}</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={toggleHealth} aria-expanded={healthOpen}>
			<h2>
				{$t('feed_health')}
				{#if health && healthProblems.length}<span class="warnbadge">⚠ {healthProblems.length}</span>{/if}
			</h2>
			<span class="chev" aria-hidden="true">{healthOpen ? '▾' : '▸'}</span>
		</button>
		{#if healthOpen}
			<p class="muted hint">{$t('feed_health_hint')}</p>
			{#if health === null}
				<p class="muted">…</p>
			{:else if healthProblems.length === 0}
				<p>✓ {$t('all_feeds_ok')}</p>
			{:else}
				<p class="muted small">{health.length - healthProblems.length} {$t('feeds_ok')}</p>
				<ul class="cfeeds">
					{#each healthProblems as h (h.source_id)}
						<li class="hrow">
							<span class="hinfo">
								<span class="ftitle">
									<span class="st st-{h.status}">{$t(`st_${h.status}` as 'st_ok')}</span>
									{#if safeUrl(h.site_url)}
										<a href={safeUrl(h.site_url)} target="_blank" rel="noopener noreferrer">{h.title}</a>
									{:else}{h.title}{/if}
								</span>
								<span class="muted small ftitle">
									{#if h.last_error}{$t('error')}: {h.last_error} ·{/if}
									{$t('last_post')}: {h.last_article_at ? relativeTime(h.last_article_at, $locale) : '—'}
								</span>
							</span>
							<button class="small-btn" onclick={() => unsubscribeFeed(h)}>{$t('unsubscribe')}</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={toggleStarter} aria-expanded={starterOpen}>
			<h2>{$t('starter_sources')}</h2>
			<span class="chev" aria-hidden="true">{starterOpen ? '▾' : '▸'}</span>
		</button>
		{#if starterOpen}
			<p class="muted hint">{$t('starter_sources_hint')}</p>
			<div class="row langbar">
				<button class:active={catFilter === 'all'} onclick={() => (catFilter = 'all')}>{$t('all_langs')}</button>
				<button class:active={catFilter === 'es'} onclick={() => (catFilter = 'es')}>{LANG_FLAG.es} {$t('lang_es')}</button>
				<button class:active={catFilter === 'en'} onclick={() => (catFilter = 'en')}>{LANG_FLAG.en} {$t('lang_en')}</button>
			</div>
			{#if catMsg}<p class="errmsg">{catMsg}</p>{/if}
			{#each catalog as s (s.id)}
				{@const feeds = catFeeds(s)}
				{@const count = feeds.filter(isSub).length}
				<div class="csec">
					<div class="csec-head">
						<strong>{catName(s)}</strong>
						<span class="muted small">{count}/{feeds.length}</span>
						<button class="small-btn" onclick={() => addAll(s)} disabled={count === feeds.length}>
							+ {$t('catalog_add_all')}
						</button>
					</div>
					<ul class="cfeeds">
						{#each feeds as f (f.url)}
							<li>
								<span class="flag" title={$t(f.lang === 'es' ? 'lang_es' : 'lang_en')}>{LANG_FLAG[f.lang]}</span>
								<span class="ftitle">{f.title}</span>
								{#if isSub(f)}
									<button class="small-btn on" onclick={() => removeFeed(f)} disabled={catBusy.has(f.url)}>
										✓ {$t('catalog_remove')}
									</button>
								{:else}
									<button class="small-btn" onclick={() => addFeed(s, f)} disabled={catBusy.has(f.url)}>
										{catBusy.has(f.url) ? '…' : '+ ' + $t('catalog_add')}
									</button>
								{/if}
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('api')} aria-expanded={!!open.api}>
			<h2>{$t('api_access')}</h2>
			<span class="chev" aria-hidden="true">{open.api ? '▾' : '▸'}</span>
		</button>
		{#if open.api}
			<p class="muted hint">{$t('api_access_hint')}</p>
			<div class="field">
				{$t('server_url')}
				<div class="row">
					<code class="mono">{serverUrl}</code>
					<button onclick={() => copy(serverUrl, 'url')}>{copied === 'url' ? '✓ ' + $t('copied') : $t('copy')}</button>
				</div>
			</div>
			<label class="field">
				{$t('key_name')}
				<div class="row">
					<input bind:value={newKeyName} maxlength="120" />
					<button class="primary" onclick={createKey} disabled={!newKeyName.trim()}>{$t('generate_key')}</button>
				</div>
				{#if keyMsg}<span class="errmsg">{keyMsg}</span>{/if}
			</label>
			<label class="check">
				<input type="checkbox" bind:checked={allowState} />
				{$t('key_allow_state')}
			</label>
			{#if created}
				<div class="newkey">
					<p><strong>{created.name}</strong> — {$t('key_created_once')}</p>
					<div class="row">
						<code class="mono secret">{created.key}</code>
						<button onclick={() => copy(created!.key, 'key')}>{copied === 'key' ? '✓ ' + $t('copied') : $t('copy')}</button>
					</div>
				</div>
			{/if}
			{#if keys.length === 0}
				<p class="muted">{$t('no_keys')}</p>
			{:else}
				<ul class="keys">
					{#each keys as k (k.id)}
						<li>
							<div class="kinfo">
								<strong>{k.name}</strong> <code class="mono">{k.prefix}…</code>
								<span class="muted small">{scopeLabels(k)}</span>
								<span class="muted small">
									{$t('created')} {relativeTime(k.created_at, $locale)} ·
									{k.last_used_at ? `${$t('last_used')} ${relativeTime(k.last_used_at, $locale)}` : $t('never_used')}
								</span>
							</div>
							<button onclick={() => revokeKey(k)}>{$t('revoke')}</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>

	<section id="password">
		<button class="collapse" onclick={() => toggle('password')} aria-expanded={!!open.password}>
			<h2>{$t('password')}</h2>
			<span class="chev" aria-hidden="true">{open.password ? '▾' : '▸'}</span>
		</button>
		{#if open.password}
			{#if $user?.must_change_password}
				<p class="warn">{$t('temp_password_banner')}</p>
			{/if}
			<form class="pwform" onsubmit={changePassword}>
				<input type="email" autocomplete="username" value={$user?.email ?? ''} hidden />
				<input
					type="password"
					bind:value={curPw}
					placeholder={$t('current_password')}
					autocomplete="current-password"
					required
				/>
				<input
					type="password"
					bind:value={newPw}
					placeholder={$t('new_password')}
					autocomplete="new-password"
					minlength="8"
					required
				/>
				<input
					type="password"
					bind:value={newPw2}
					placeholder={$t('confirm_password')}
					autocomplete="new-password"
					minlength="8"
					required
				/>
				<div class="row">
					<button class="primary" type="submit" disabled={pwBusy}>{$t('change_password')}</button>
					{#if pwMsg}<span class={pwOk ? 'okmsg' : 'errmsg'}>{pwMsg}</span>{/if}
				</div>
			</form>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('account')} aria-expanded={!!open.account}>
			<h2>{$t('account')}</h2>
			<span class="chev" aria-hidden="true">{open.account ? '▾' : '▸'}</span>
		</button>
		{#if open.account}
			<label class="field">
				{$t('display_name')}
				<div class="row">
					<input bind:value={displayName} maxlength="60" placeholder={$t('name_placeholder')} />
					<button class="primary" onclick={saveName}>{nameSaved ? '✓' : $t('save')}</button>
				</div>
			</label>
			{#if $user}
				<p class="muted">{$user.email}</p>
				<p class="muted small">
					{$t('plan')}: <strong>{$t(`role_${$user.role}` as 'role_free')}</strong>
					{#if myPlan}· {planSummary(myPlan)}{/if}
				</p>
			{/if}
			<button onclick={logout}>{$t('logout')}</button>
		{/if}
	</section>
</div>

<style>
	.page {
		max-width: 640px;
		margin: 0 auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.back {
		font-size: 0.9rem;
	}
	h1 {
		margin: 0;
	}
	section {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1rem 1.25rem;
	}
	h2 {
		margin: 0 0 0.75rem;
		font-size: 0.95rem;
	}
	.row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.9rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.collapse {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		background: none;
		border: none;
		padding: 0;
		text-align: left;
		cursor: pointer;
	}
	.collapse h2 {
		margin: 0;
	}
	section:has(.collapse[aria-expanded='true']) .collapse {
		margin-bottom: 0.75rem;
	}
	.chev {
		color: var(--muted);
	}
	.langbar {
		margin-bottom: 0.75rem;
	}
	.langbar button {
		border-radius: 999px;
		padding: 0.25rem 0.7rem;
		font-size: 0.82rem;
	}
	.csec {
		border-top: 1px solid var(--border);
		padding: 0.6rem 0;
	}
	.csec-head {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.35rem;
	}
	.csec-head .small-btn {
		margin-left: auto;
	}
	.cfeeds {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.cfeeds li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.88rem;
	}
	.flag {
		flex: none;
	}
	.ftitle {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin: 0.6rem 0;
	}
	.kchip {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0.15rem 0.3rem 0.15rem 0.65rem;
		font-size: 0.85rem;
	}
	.chipx {
		border: none;
		background: none;
		padding: 0 0.25rem;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.subh {
		margin: 1rem 0 0.2rem;
		font-size: 0.9rem;
	}
	.hrow {
		align-items: flex-start !important;
		border-top: 1px solid var(--border);
		padding-top: 0.4rem;
	}
	.hinfo {
		display: flex;
		flex-direction: column;
		min-width: 0;
		flex: 1;
	}
	.warnbadge {
		font-size: 0.75rem;
		color: var(--danger);
		margin-left: 0.4rem;
	}
	.st {
		font-size: 0.72rem;
		border-radius: 999px;
		padding: 0 0.4rem;
		margin-right: 0.3rem;
		border: 1px solid var(--border);
	}
	.st-failing {
		color: var(--danger);
		border-color: var(--danger);
	}
	.st-retrying,
	.st-stale {
		color: var(--accent);
		border-color: var(--accent);
	}
	.small-btn {
		flex: none;
		padding: 0.25rem 0.6rem;
		font-size: 0.8rem;
	}
	.small-btn.on {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	.pwform {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 360px;
	}
	.warn {
		margin: 0 0 0.6rem;
		padding: 0.5rem 0.7rem;
		border-radius: 8px;
		background: var(--accent-soft);
		border: 1px solid var(--accent);
		font-size: 0.85rem;
	}
	.okmsg {
		color: var(--accent);
		font-size: 0.85rem;
	}
	.errmsg {
		color: var(--danger);
		font-size: 0.85rem;
	}
	.atkinson {
		font-family: 'Atkinson Hyperlegible', system-ui, sans-serif;
	}
	.vlang {
		min-width: 6.5rem;
		font-size: 0.85rem;
	}
	.field select {
		flex: 1 1 10rem;
		min-width: 0;
		width: auto;
	}
	.adminlink {
		align-self: flex-start;
		font-size: 0.9rem;
		border: 1px solid var(--accent);
		border-radius: 999px;
		padding: 0.3rem 0.8rem;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.85rem;
		margin: -0.4rem 0 0.9rem;
	}
	.hint {
		margin: 0 0 0.75rem;
		font-size: 0.85rem;
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8rem;
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.3rem 0.5rem;
		overflow-wrap: anywhere;
		color: var(--text, inherit);
	}
	.secret {
		user-select: all;
		-webkit-user-select: all;
		flex: 1;
		min-width: 0;
	}
	.newkey {
		border: 1px solid var(--accent);
		background: var(--accent-soft);
		border-radius: 10px;
		padding: 0.6rem 0.75rem;
		margin-bottom: 0.9rem;
		font-size: 0.85rem;
	}
	.newkey p {
		margin: 0 0 0.4rem;
	}
	.keys {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.keys li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		border-top: 1px solid var(--border);
		padding-top: 0.5rem;
	}
	.kinfo {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.small {
		font-size: 0.78rem;
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
</style>
