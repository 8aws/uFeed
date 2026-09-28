<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime } from '$lib/format';
	import { CATALOG, LANG_FLAG, type CatalogSection, type FeedLang } from '$lib/catalog';
	import type { HiddenArticle, SourceHealth } from '$lib/types';

	let flash = $state('');
	let error = $state('');
	let open = $state<Record<string, boolean>>({});
	const toggle = (k: string) => (open[k] = !open[k]);

	function saved(msg = $t('saved_ok')) {
		flash = msg;
		setTimeout(() => (flash = ''), 2000);
	}
	function fail(e: unknown) {
		error = e instanceof ApiError ? e.message : '⚠';
		setTimeout(() => (error = ''), 4000);
	}

	// --- Starter catalogue (edited as a draft, saved in one go) ---------------
	let draft = $state<CatalogSection[]>([]);
	let custom = $state(false);
	let updatedAt = $state<string | null>(null);
	let dirty = $state(false);
	let savingCat = $state(false);
	let openSec = $state<string | null>(null);
	// Add-feed form of the open section (only one section is open at a time).
	let nf = $state<{ url: string; lang: FeedLang; busy: boolean; msg: string }>({
		url: '',
		lang: 'en',
		busy: false,
		msg: ''
	});
	function openSection(id: string | null) {
		openSec = openSec === id ? null : id;
		nf = { url: '', lang: $locale === 'es' ? 'es' : 'en', busy: false, msg: '' };
	}

	const clone = (c: CatalogSection[]) => JSON.parse(JSON.stringify(c)) as CatalogSection[];
	const touch = () => (dirty = true);

	async function loadCatalog() {
		const c = await api.catalog();
		custom = c.sections !== null;
		updatedAt = c.updated_at;
		draft = clone(c.sections ?? CATALOG);
		dirty = false;
	}

	function secName(s: CatalogSection) {
		return $locale === 'es' ? s.name_es : s.name_en;
	}
	function slug(v: string) {
		return (
			v
				.toLowerCase()
				.normalize('NFD')
				.replace(/[̀-ͯ]/g, '')
				.replace(/[^a-z0-9]+/g, '-')
				.replace(/^-+|-+$/g, '')
				.slice(0, 40) || 'section'
		);
	}

	function addSection() {
		let id = 'new-section';
		for (let i = 2; draft.some((s) => s.id === id); i++) id = `new-section-${i}`;
		draft = [...draft, { id, name_en: 'New section', name_es: 'Nueva sección', feeds: [] }];
		openSection(id);
		touch();
	}
	function renameId(s: CatalogSection) {
		// Keep ids stable once saved; only brand-new sections follow their name.
		if (!s.id.startsWith('new-section')) return;
		let id = slug(s.name_en);
		for (let i = 2; draft.some((x) => x !== s && x.id === id); i++) id = `${slug(s.name_en)}-${i}`;
		s.id = id;
		openSec = id;
	}
	function moveSection(i: number, dir: -1 | 1) {
		const j = i + dir;
		if (j < 0 || j >= draft.length) return;
		const next = [...draft];
		[next[i], next[j]] = [next[j], next[i]];
		draft = next;
		touch();
	}
	function removeSection(s: CatalogSection) {
		if (!confirm($t('confirm_remove_section'))) return;
		draft = draft.filter((x) => x !== s);
		touch();
	}
	function removeFeed(s: CatalogSection, i: number) {
		s.feeds = s.feeds.filter((_, k) => k !== i);
		touch();
	}

	// Validate through the same discovery the reader uses, so only live feeds
	// get into the list; the feed's own title pre-fills the display name.
	async function addFeed(s: CatalogSection) {
		const n = nf;
		const url = n.url.trim();
		if (!url || n.busy) return;
		n.busy = true;
		n.msg = '';
		try {
			const found = await api.discover(url);
			if (!found.length) {
				n.msg = $t('no_feeds_found');
				return;
			}
			const f = found[0];
			if (s.feeds.some((x) => x.url === f.feed_url)) {
				n.msg = '✓';
				return;
			}
			s.feeds = [...s.feeds, { title: (f.title || new URL(f.feed_url).hostname).slice(0, 120), url: f.feed_url, lang: n.lang }];
			n.url = '';
			touch();
		} catch (e) {
			n.msg = e instanceof ApiError ? e.message : $t('no_feeds_found');
		} finally {
			n.busy = false;
		}
	}

	async function saveCatalog() {
		savingCat = true;
		try {
			const c = await api.saveCatalog(draft);
			custom = true;
			updatedAt = c.updated_at;
			draft = clone(c.sections ?? CATALOG);
			dirty = false;
			saved();
		} catch (e) {
			fail(e);
		} finally {
			savingCat = false;
		}
	}

	async function restoreBuiltin() {
		if (!confirm($t('confirm_restore_catalog'))) return;
		try {
			await api.saveCatalog(null);
			await loadCatalog();
			saved();
		} catch (e) {
			fail(e);
		}
	}

	// --- Shared rankings --------------------------------------------------------
	let hidden = $state<HiddenArticle[]>([]);
	async function unhide(h: HiddenArticle) {
		try {
			await api.setHidden(h.article.id, false);
			hidden = hidden.filter((x) => x !== h);
			saved();
		} catch (e) {
			fail(e);
		}
	}

	// --- Feed health --------------------------------------------------------------
	let sources = $state<SourceHealth[]>([]);
	const problems = $derived(sources.filter((x) => x.status !== 'ok'));
	const orphans = $derived(sources.filter((x) => x.subscribers === 0).length);

	async function togglePause(src: SourceHealth) {
		try {
			await api.pauseSource(src.source_id, src.status !== 'paused');
			sources = await api.adminSources();
			saved();
		} catch (e) {
			fail(e);
		}
	}
	async function deleteOrphans() {
		try {
			const r = await api.deleteOrphanSources();
			sources = await api.adminSources();
			saved(`${r.deleted} ${$t('orphans_deleted')}`);
		} catch (e) {
			fail(e);
		}
	}

	onMount(async () => {
		// Check the live role (the cached profile may predate a role change).
		const me = await api.me().catch(() => null);
		if (me) user.set(me);
		if (me && me.role !== 'editor' && me.role !== 'admin') {
			goto('/');
			return;
		}
		loadCatalog().catch(fail);
		api.hiddenArticles().then((h) => (hidden = h)).catch(fail);
		api.adminSources().then((s) => (sources = s)).catch(fail);
	});
</script>

<svelte:window
	onbeforeunload={(e) => {
		if (dirty) e.preventDefault();
	}}
/>

<div class="page">
	<a class="back" href="/settings">← {$t('settings')}</a>
	<h1>✎ {$t('curation')}</h1>
	<p class="muted small">{$t('curation_hint')}</p>
	{#if $user?.role === 'admin'}
		<a class="pill" href="/admin">🛡 {$t('admin')} →</a>
	{/if}
	{#if flash}<p class="flash">✓ {flash}</p>{/if}
	{#if error}<p class="err">{error}</p>{/if}

	<section>
		<button class="collapse" onclick={() => toggle('catalog')} aria-expanded={!!open.catalog}>
			<h2>🌱 {$t('starter_sources')} {dirty ? '•' : ''}</h2>
			<span class="chev" aria-hidden="true">{open.catalog ? '▾' : '▸'}</span>
		</button>
		{#if open.catalog}
			<p class="muted small">
				{$t('catalog_editor_hint')}
				{custom && updatedAt ? `${$t('last_edit')}: ${relativeTime(updatedAt, $locale)}.` : $t('catalog_builtin')}
			</p>
			<ul class="sections">
				{#each draft as s, i (s)}
					<li class="sec">
						<div class="sechead">
							<button class="secname" onclick={() => openSection(s.id)}>
								{openSec === s.id ? '▾' : '▸'} {secName(s)}
								<span class="muted small">
									· {s.feeds.filter((f) => f.lang === 'en').length}{LANG_FLAG.en}
									{s.feeds.filter((f) => f.lang === 'es').length}{LANG_FLAG.es}
								</span>
							</button>
							<span class="secctl">
								<button class="icon" onclick={() => moveSection(i, -1)} disabled={i === 0} aria-label="up">↑</button>
								<button class="icon" onclick={() => moveSection(i, 1)} disabled={i === draft.length - 1} aria-label="down">↓</button>
								<button class="icon danger" onclick={() => removeSection(s)} aria-label={$t('catalog_remove')}>✕</button>
							</span>
						</div>
						{#if openSec === s.id}
							<div class="secbody">
								<div class="names">
									<label>
										🇬🇧 <input bind:value={s.name_en} maxlength="80" oninput={touch} onchange={() => renameId(s)} />
									</label>
									<label>🇪🇸 <input bind:value={s.name_es} maxlength="80" oninput={touch} /></label>
								</div>
								<ul class="feeds">
									{#each s.feeds as f, k (f.url)}
										<li>
											<select bind:value={f.lang} onchange={touch} aria-label={$t('language')}>
												<option value="en">{LANG_FLAG.en}</option>
												<option value="es">{LANG_FLAG.es}</option>
											</select>
											<span class="fmain">
												<input bind:value={f.title} maxlength="120" oninput={touch} aria-label="title" />
												<span class="muted small ellipsis">{f.url}</span>
											</span>
											<button class="icon danger" onclick={() => removeFeed(s, k)} aria-label={$t('catalog_remove')}>✕</button>
										</li>
									{/each}
								</ul>
								<form
									class="addfeed"
									onsubmit={(e) => {
										e.preventDefault();
										addFeed(s);
									}}
								>
									<select bind:value={nf.lang} aria-label={$t('language')}>
										<option value="en">{LANG_FLAG.en}</option>
										<option value="es">{LANG_FLAG.es}</option>
									</select>
									<input bind:value={nf.url} placeholder={$t('add_feed_placeholder')} />
									<button type="submit" disabled={nf.busy}>{nf.busy ? '…' : '+ ' + $t('catalog_add')}</button>
								</form>
								{#if nf.msg}<p class="muted small">{nf.msg}</p>{/if}
							</div>
						{/if}
					</li>
				{/each}
			</ul>
			<div class="row">
				<button onclick={addSection}>+ {$t('add_section')}</button>
				<button class="primary" onclick={saveCatalog} disabled={!dirty || savingCat}>
					{savingCat ? '…' : $t('save')}
				</button>
				{#if dirty}<button onclick={() => loadCatalog()}>{$t('discard')}</button>{/if}
				{#if custom}<button onclick={restoreBuiltin}>{$t('restore_builtin')}</button>{/if}
			</div>
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('hidden')} aria-expanded={!!open.hidden}>
			<h2>🚫 {$t('hidden_from_trending')} ({hidden.length})</h2>
			<span class="chev" aria-hidden="true">{open.hidden ? '▾' : '▸'}</span>
		</button>
		{#if open.hidden}
			<p class="muted small">{$t('hidden_hint')}</p>
			{#if hidden.length === 0}
				<p class="muted">{$t('nothing_hidden')}</p>
			{:else}
				<ul class="list">
					{#each hidden as h (h.article.id)}
						<li>
							<span class="fmain">
								<span class="ellipsis"><strong>{h.article.title}</strong></span>
								<span class="muted small">
									{relativeTime(h.hidden_at, $locale)}{h.hidden_by ? ` · ${h.hidden_by}` : ''}
								</span>
							</span>
							<button class="small-btn" onclick={() => unhide(h)}>↺ {$t('show_again')}</button>
						</li>
					{/each}
				</ul>
			{/if}
		{/if}
	</section>

	<section>
		<button class="collapse" onclick={() => toggle('health')} aria-expanded={!!open.health}>
			<h2>🩺 {$t('feed_health')} ({problems.length}/{sources.length})</h2>
			<span class="chev" aria-hidden="true">{open.health ? '▾' : '▸'}</span>
		</button>
		{#if open.health}
			<p class="muted small">{$t('feed_health_hint')}</p>
			<ul class="list">
				{#each problems as src (src.source_id)}
					<li>
						<span class="fmain">
							<span class="ellipsis">
								<span class="st st-{src.status}">{$t(`st_${src.status}` as 'st_ok')}</span>
								<strong>{src.title}</strong> · {src.subscribers} {$t('subscribers')}
							</span>
							<span class="muted small ellipsis">
								{#if src.last_error}{$t('error')}: {src.last_error} ·{/if}
								{$t('last_post')}: {src.last_article_at ? relativeTime(src.last_article_at, $locale) : '—'}
							</span>
						</span>
						<button class="small-btn" onclick={() => togglePause(src)}>
							{src.status === 'paused' ? `▶ ${$t('resume')}` : `⏸ ${$t('pause')}`}
						</button>
					</li>
				{/each}
			</ul>
			{#if orphans > 0}
				<button class="small-btn spaced" onclick={deleteOrphans}>🧹 {$t('delete_orphans')} ({orphans})</button>
			{/if}
		{/if}
	</section>
</div>

<style>
	.page {
		max-width: 720px;
		margin: 0 auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.1rem;
	}
	.back {
		font-size: 0.9rem;
	}
	h1 {
		margin: 0;
	}
	h2 {
		margin: 0;
		font-size: 0.95rem;
	}
	.pill {
		align-self: flex-start;
		font-size: 0.9rem;
		border: 1px solid var(--accent);
		border-radius: 999px;
		padding: 0.3rem 0.8rem;
	}
	section {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1rem 1.25rem;
		min-width: 0;
	}
	.collapse {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		background: none;
		border: none;
		padding: 0;
		color: inherit;
		text-align: left;
	}
	section:has(.collapse[aria-expanded='true']) .collapse {
		margin-bottom: 0.6rem;
	}
	.muted {
		color: var(--muted);
	}
	.small {
		font-size: 0.8rem;
	}
	.ellipsis {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.75rem;
	}
	.sections,
	.feeds,
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}
	.sec {
		border-top: 1px solid var(--border);
		padding: 0.4rem 0;
	}
	.sechead {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.secname {
		background: none;
		border: none;
		padding: 0.2rem 0;
		text-align: left;
		color: inherit;
		font-weight: 600;
		flex: 1;
		min-width: 0;
	}
	.secctl {
		display: flex;
		gap: 0.25rem;
		flex: none;
	}
	.icon {
		padding: 0.15rem 0.45rem;
		font-size: 0.8rem;
	}
	.danger {
		color: var(--danger);
	}
	.secbody {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.4rem 0 0.4rem 0.9rem;
	}
	.names {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.names label {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex: 1 1 200px;
	}
	.names input {
		flex: 1;
		min-width: 0;
	}
	.feeds li,
	.list li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.3rem 0;
		min-width: 0;
	}
	.list li {
		border-top: 1px solid var(--border);
	}
	.fmain {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
	}
	.fmain input {
		padding: 0.2rem 0.4rem;
	}
	.feeds select,
	.addfeed select {
		width: auto;
		flex: none;
		padding: 0.2rem 0.3rem;
	}
	.fmain input {
		width: 100%;
	}
	.addfeed {
		display: flex;
		gap: 0.4rem;
	}
	.addfeed input {
		flex: 1;
		min-width: 0;
	}
	.small-btn {
		padding: 0.25rem 0.6rem;
		font-size: 0.8rem;
		flex: none;
	}
	.spaced {
		margin-top: 0.75rem;
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
	.flash {
		margin: 0;
		color: var(--accent);
		font-size: 0.9rem;
	}
	.err {
		margin: 0;
		color: var(--danger);
		font-size: 0.9rem;
	}
	@media (max-width: 640px) {
		.page {
			padding: 1rem;
		}
	}
</style>
