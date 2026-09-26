<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError, downloadOpml, importOpml } from '$lib/api';
	import { clearTokens, setTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import { toolbarLabels, type ToolbarLabels } from '$lib/prefs';
	import { relativeTime } from '$lib/format';
	import type { ApiKey, ApiKeyCreated, Folder, Locale, Role, Subscription } from '$lib/types';
	import { CATALOG, LANG_FLAG, type CatalogFeed, type CatalogSection, type FeedLang } from '$lib/catalog';
	import { addCatalogFeed, ensureFolder, feedKey } from '$lib/catalogActions';

	const LABEL_MODES: ToolbarLabels[] = ['auto', 'both', 'icons', 'text'];

	let importMsg = $state('');
	let fileInput: HTMLInputElement;
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
				[catSubs, catFolders] = await Promise.all([api.listSources(), api.listFolders()]);
			} catch {
				starterLoaded = false;
			}
		}
	}

	async function addFeed(s: CatalogSection, f: CatalogFeed) {
		if (catBusy.has(f.url) || isSub(f)) return;
		setBusy(f.url, true);
		try {
			const folder = await ensureFolder(catName(s), catFolders);
			const sub = await addCatalogFeed(f, folder?.id ?? null);
			// The worker fetches new sources on its next tick; no manual refresh,
			// which would spend the plan's refresh cooldown.
			if (sub) catSubs = [...catSubs, sub];
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
	let cooldowns = $state<Record<Role, number> | null>(null);

	function scopeLabels(k: ApiKey): string {
		const sc = k.scopes.length ? k.scopes : ['read', 'state']; // [] = full access
		return sc.map((x) => $t(x === 'state' ? 'scope_state' : 'scope_read')).join(' · ');
	}

	function planLimit(role: Role): string {
		const secs = cooldowns?.[role];
		if (secs === undefined) return '';
		return secs > 0 ? `${$t('refresh_every')} ${Math.round(secs / 60)} min` : $t('refresh_immediate');
	}

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
			created = await api.createKey(name, allowState ? ['read', 'state'] : ['read']);
			await loadKeys();
		} catch {
			/* ignore */
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
		api.site().then((c) => (cooldowns = c.refresh_cooldown_s)).catch(() => {});
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

	<section>
		<h2>{$t('language')}</h2>
		<div class="row">
			<button class:active={$locale === 'en'} onclick={() => changeLanguage('en')}>English</button>
			<button class:active={$locale === 'es'} onclick={() => changeLanguage('es')}>Español</button>
		</div>
	</section>

	<section>
		<h2>{$t('appearance')}</h2>
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
	</section>

	<section>
		<h2>{$t('feeds')}</h2>
		<div class="row">
			<button onclick={() => fileInput.click()}>{$t('import_opml')}</button>
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
			{#each CATALOG as s (s.id)}
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
		<h2>{$t('api_access')}</h2>
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
	</section>

	<section id="password">
		<h2>{$t('password')}</h2>
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
	</section>

	<section>
		<h2>{$t('account')}</h2>
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
				{#if cooldowns}· {planLimit($user.role)}{/if}
			</p>
		{/if}
		<button onclick={logout}>{$t('logout')}</button>
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
