<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime, readingTime, stripHtml } from '$lib/format';
	import type { Article, DiscoveredFeed, Folder, Subscription, TrendingItem } from '$lib/types';

	type View = 'list' | 'cards' | 'masonry';

	function initialView(): View {
		if (typeof localStorage !== 'undefined') {
			const v = localStorage.getItem('view');
			if (v === 'list' || v === 'cards' || v === 'masonry') return v;
		}
		return 'list';
	}

	type Filter =
		| { kind: 'all' }
		| { kind: 'unread' }
		| { kind: 'saved' }
		| { kind: 'favorites' }
		| { kind: 'source'; id: string }
		| { kind: 'folder'; id: string };

	let folders = $state<Folder[]>([]);
	let subs = $state<Subscription[]>([]);
	let filter = $state<Filter>({ kind: 'unread' });

	let articles = $state<Article[]>([]);
	let cursor = $state<string | null>(null);
	let hasMore = $state(false);
	let loading = $state(false);
	let selected = $state(0);
	let openArticle = $state<Article | null>(null);
	let trending = $state<TrendingItem[]>([]);
	let readerEl = $state<HTMLElement | null>(null);
	let readingStart = 0;
	let query = $state('');
	let view = $state<View>(initialView());
	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	function setView(v: View) {
		view = v;
		try {
			localStorage.setItem('view', v);
		} catch {
			/* ignore */
		}
	}

	function onSearchInput() {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => loadArticles(true), 300);
	}

	// Add-feed UI.
	let showAdd = $state(false);
	let feedUrl = $state('');
	let candidates = $state<DiscoveredFeed[]>([]);
	let discovering = $state(false);
	let discoverMsg = $state('');

	const totalUnread = $derived(subs.reduce((n, s) => n + s.unread_count, 0));

	function buildParams(reset: boolean): Record<string, string> {
		const p: Record<string, string> = { limit: '30' };
		if (filter.kind === 'unread') p.unread = 'true';
		if (filter.kind === 'saved') p.saved = 'true';
		if (filter.kind === 'favorites') p.favorite = 'true';
		if (filter.kind === 'source') p.source = filter.id;
		if (filter.kind === 'folder') p.folder = filter.id;
		if (query.trim()) p.q = query.trim();
		if (!reset && cursor) p.cursor = cursor;
		return p;
	}

	async function loadSidebar() {
		[folders, subs] = await Promise.all([api.listFolders(), api.listSources()]);
	}

	async function loadArticles(reset: boolean) {
		if (loading) return;
		loading = true;
		try {
			const page = await api.listArticles(buildParams(reset));
			articles = reset ? page.items : [...articles, ...page.items];
			cursor = page.next_cursor;
			hasMore = !!page.next_cursor;
			if (reset) selected = 0;
		} finally {
			loading = false;
		}
	}

	function setFilter(f: Filter) {
		filter = f;
		openArticle = null;
		loadArticles(true);
	}

	function flushReadEvent() {
		const a = openArticle;
		if (!a || !readingStart) return;
		const dwell = Date.now() - readingStart;
		let completion = 1;
		if (readerEl && readerEl.scrollHeight > readerEl.clientHeight) {
			completion = (readerEl.scrollTop + readerEl.clientHeight) / readerEl.scrollHeight;
		}
		readingStart = 0;
		if (dwell > 1000) api.readEvent(a.id, dwell, Math.max(0, Math.min(1, completion))).catch(() => {});
	}

	function openArticleObj(a: Article) {
		flushReadEvent();
		openArticle = a;
		readingStart = Date.now();
		if (!a.is_read) markRead(a, true);
	}

	async function open(i: number) {
		if (i < 0 || i >= articles.length) return;
		selected = i;
		openArticleObj(articles[i]);
	}

	function closeReader() {
		flushReadEvent();
		openArticle = null;
	}

	async function toggleFavorite(a: Article) {
		a.is_favorite = !a.is_favorite;
		articles = [...articles];
		try {
			await api.setFavorite(a.id, a.is_favorite);
		} catch {
			a.is_favorite = !a.is_favorite;
			articles = [...articles];
		}
	}

	async function loadTrending() {
		try {
			trending = await api.trending(48, 8);
		} catch {
			trending = [];
		}
	}

	async function markRead(a: Article, read: boolean) {
		a.is_read = read;
		articles = [...articles];
		try {
			await api.setRead(a.id, read);
			await refreshUnreadFor(a.source_id);
		} catch {
			/* ignore; UI already updated optimistically */
		}
	}

	async function toggleSave(a: Article) {
		a.is_saved = !a.is_saved;
		articles = [...articles];
		try {
			await api.setSaved(a.id, a.is_saved);
		} catch {
			a.is_saved = !a.is_saved;
			articles = [...articles];
		}
	}

	async function refreshUnreadFor(_sourceId: string) {
		try {
			subs = await api.listSources();
		} catch {
			/* ignore */
		}
	}

	async function markAllRead() {
		const source_id = filter.kind === 'source' ? filter.id : null;
		const folder_id = filter.kind === 'folder' ? filter.id : null;
		await api.markAllRead(folder_id, source_id);
		await Promise.all([loadArticles(true), loadSidebar()]);
	}

	async function runDiscover() {
		discoverMsg = '';
		candidates = [];
		discovering = true;
		try {
			candidates = await api.discover(feedUrl);
			if (candidates.length === 0) discoverMsg = $t('no_feeds_found');
		} catch (e) {
			discoverMsg = e instanceof ApiError ? e.message : $t('no_feeds_found');
		} finally {
			discovering = false;
		}
	}

	async function subscribe(url: string) {
		await api.subscribe(url);
		showAdd = false;
		feedUrl = '';
		candidates = [];
		await loadSidebar();
	}

	async function unsubscribe(sub: Subscription) {
		if (!confirm($t('confirm_unsubscribe'))) return;
		await api.unsubscribe(sub.id);
		if (filter.kind === 'source' && filter.id === sub.source.id) setFilter({ kind: 'unread' });
		await loadSidebar();
	}

	function logout() {
		clearTokens();
		goto('/login');
	}

	function onKey(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
		if (e.key === 'j') {
			selected = Math.min(selected + 1, articles.length - 1);
			scrollToSelected();
		} else if (e.key === 'k') {
			selected = Math.max(selected - 1, 0);
			scrollToSelected();
		} else if (e.key === 'o' || e.key === 'Enter') {
			open(selected);
		} else if (e.key === 'm') {
			const a = articles[selected];
			if (a) markRead(a, !a.is_read);
		} else if (e.key === 's') {
			const a = articles[selected];
			if (a) toggleSave(a);
		} else if (e.key === 'f') {
			const a = articles[selected];
			if (a) toggleFavorite(a);
		} else if (e.key === 'Escape') {
			if (openArticle) closeReader();
		}
	}

	function scrollToSelected() {
		document.querySelector(`[data-idx="${selected}"]`)?.scrollIntoView({ block: 'nearest' });
	}

	function sentinel(node: HTMLElement) {
		const io = new IntersectionObserver((entries) => {
			if (entries[0].isIntersecting && hasMore && !loading) loadArticles(false);
		});
		io.observe(node);
		return { destroy: () => io.disconnect() };
	}

	function title(a: Article): string {
		return a.title || a.url || '(untitled)';
	}

	function sourceName(sourceId: string): string {
		const s = subs.find((x) => x.source.id === sourceId);
		return s?.custom_title || s?.source.title || s?.source.feed_url || '';
	}

	function folderName(id: string): string {
		return folders.find((f) => f.id === id)?.name ?? '';
	}

	onMount(async () => {
		await loadSidebar();
		await loadArticles(true);
		loadTrending();
	});

	onDestroy(() => flushReadEvent());
</script>

<svelte:window onkeydown={onKey} />

<div class="shell" class:reading={openArticle}>
	<aside class="sidebar">
		<div class="brand">
			<div class="brand-name">
				<strong>{$t('app_name')}</strong>
				{#if $user}<span class="who ellipsis">{$user.email}</span>{/if}
			</div>
			<a href="/settings" title={$t('settings')} aria-label={$t('settings')}>⚙</a>
		</div>

		<input
			class="search"
			type="search"
			placeholder={$t('search_placeholder')}
			bind:value={query}
			oninput={onSearchInput}
		/>

		<nav>
			<button class="nav" class:active={filter.kind === 'all'} onclick={() => setFilter({ kind: 'all' })}>
				{$t('all')}
			</button>
			<button
				class="nav"
				class:active={filter.kind === 'unread'}
				onclick={() => setFilter({ kind: 'unread' })}
			>
				{$t('unread')} {#if totalUnread}<span class="badge">{totalUnread}</span>{/if}
			</button>
			<button
				class="nav"
				class:active={filter.kind === 'saved'}
				onclick={() => setFilter({ kind: 'saved' })}
			>
				{$t('saved')}
			</button>
			<button
				class="nav"
				class:active={filter.kind === 'favorites'}
				onclick={() => setFilter({ kind: 'favorites' })}
			>
				★ {$t('favorites')}
			</button>
		</nav>

		<div class="section">
			<span>{$t('feeds')}</span>
			<button class="mini" onclick={() => (showAdd = !showAdd)}>＋</button>
		</div>

		{#if showAdd}
			<div class="add">
				<input placeholder={$t('add_feed_placeholder')} bind:value={feedUrl} />
				<button class="primary" onclick={runDiscover} disabled={discovering || !feedUrl}>
					{$t('discover')}
				</button>
				{#if discoverMsg}<p class="muted small">{discoverMsg}</p>{/if}
				{#each candidates as c (c.feed_url)}
					<div class="cand">
						<span class="ellipsis">{c.title || c.feed_url}</span>
						<button class="mini" onclick={() => subscribe(c.feed_url)}>{$t('subscribe')}</button>
					</div>
				{/each}
			</div>
		{/if}

		<ul class="feeds">
			{#each subs as s (s.id)}
				<li class:active={filter.kind === 'source' && filter.id === s.source.id}>
					<button class="feed" onclick={() => setFilter({ kind: 'source', id: s.source.id })}>
						{#if s.source.favicon_url}
							<img class="favicon" src={s.source.favicon_url} alt="" loading="lazy" />
						{:else}
							<span class="favicon dot"></span>
						{/if}
						<span class="ellipsis">{s.custom_title || s.source.title || s.source.feed_url}</span>
						{#if s.unread_count}<span class="badge">{s.unread_count}</span>{/if}
					</button>
					<button class="x" title={$t('unsubscribe')} onclick={() => unsubscribe(s)}>×</button>
				</li>
			{/each}
		</ul>

		<div class="spacer"></div>
		<button class="nav" onclick={logout}>{$t('logout')}</button>
	</aside>

	<main class="list">
		<header>
			<h2>
				{#if filter.kind === 'source'}{sourceName(filter.id)}
				{:else if filter.kind === 'folder'}{folderName(filter.id)}
				{:else}{$t(filter.kind)}{/if}
			</h2>
			<div class="actions">
				<div class="viewsel" role="group" aria-label="view">
					<button class:active={view === 'list'} onclick={() => setView('list')} title={$t('view_list')}>☰</button>
					<button class:active={view === 'cards'} onclick={() => setView('cards')} title={$t('view_cards')}>▭</button>
					<button class:active={view === 'masonry'} onclick={() => setView('masonry')} title={$t('view_masonry')}>▦</button>
				</div>
				<button onclick={() => loadArticles(true)} title={$t('refresh')}>↻</button>
				<button onclick={markAllRead}>{$t('mark_all_read')}</button>
			</div>
		</header>

		{#if trending.length > 0}
			<section class="trending">
				<h3>🔥 {$t('trending')}</h3>
				<div class="cards">
					{#each trending as ti (ti.article.id)}
						<button class="card" onclick={() => openArticleObj(ti.article)}>
							<span class="ctitle">{ti.article.title || ti.article.url}</span>
							<span class="cmeta muted">
								{sourceName(ti.article.source_id) || ''} · {ti.readers}
								{$t('readers')}
							</span>
						</button>
					{/each}
				</div>
			</section>
		{/if}

		{#if articles.length === 0 && !loading}
			<p class="empty muted">{$t('no_articles')}</p>
		{/if}

		{#if view === 'list'}
			<ul>
				{#each articles as a, i (a.id)}
					<!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
					<li
						data-idx={i}
						role="button"
						tabindex="0"
						class:selected={i === selected}
						class:read={a.is_read}
						onclick={() => open(i)}
						onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open(i))}
					>
						<div class="row">
							<span class="atitle">{title(a)}</span>
							<span class="time muted">{relativeTime(a.published_at, $locale)}</span>
						</div>
						<div class="meta muted">
							<span class="ellipsis">{sourceName(a.source_id)}</span>
							{#if a.is_saved}<span class="star">★</span>{/if}
							{#if a.is_favorite}<span class="star">♥</span>{/if}
						</div>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="grid" class:masonry={view === 'masonry'}>
				{#each articles as a, i (a.id)}
					<!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
					<article
						data-idx={i}
						role="button"
						tabindex="0"
						class="acard"
						class:selected={i === selected}
						class:read={a.is_read}
						onclick={() => open(i)}
						onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), open(i))}
					>
						{#if a.image_url}
							<img class="thumb" src={a.image_url} alt="" loading="lazy" />
						{/if}
						<div class="acard-body">
							<div class="atitle">{title(a)}</div>
							<div class="meta muted">
								<span class="ellipsis">{sourceName(a.source_id)}</span>
								<span>· {relativeTime(a.published_at, $locale)}</span>
								{#if a.is_saved}<span class="star">★</span>{/if}
								{#if a.is_favorite}<span class="star">♥</span>{/if}
							</div>
							<p class="excerpt">{stripHtml(a.summary || a.content_html)}</p>
						</div>
					</article>
				{/each}
			</div>
		{/if}

		{#if loading}<p class="muted center">{$t('loading')}</p>{/if}
		{#if hasMore}<div use:sentinel></div>{/if}
		<p class="hint muted">{$t('shortcuts')}</p>
	</main>

	{#if openArticle}
		{@const a = openArticle}
		<article class="reader" bind:this={readerEl}>
			<div class="reader-head">
				<button class="close" onclick={closeReader} aria-label="close">×</button>
				<div class="reader-actions">
					<button onclick={() => markRead(a, !a.is_read)}>
						{a.is_read ? $t('mark_unread') : $t('mark_read')}
					</button>
					<button class:active={a.is_saved} onclick={() => toggleSave(a)}>
						{a.is_saved ? $t('unsave') : $t('save')}
					</button>
					<button class:active={a.is_favorite} onclick={() => toggleFavorite(a)}>
						{a.is_favorite ? '★' : '☆'} {a.is_favorite ? $t('unfavorite') : $t('favorite')}
					</button>
					{#if a.url}<a class="btn" href={a.url} target="_blank" rel="noopener">{$t('open_original')}</a>{/if}
				</div>
			</div>
			<h1>{title(a)}</h1>
			<p class="muted small">
				{sourceName(a.source_id)}
				{#if a.author}· {$t('by')} {a.author}{/if}
				· {relativeTime(a.published_at, $locale)}
				{#if a.word_count}· {readingTime(a.word_count, $locale)}{/if}
			</p>
			{#if a.tags.length}
				<div class="tags">
					{#each a.tags as tag (tag)}<span class="tag">{tag}</span>{/each}
				</div>
			{/if}
			<div class="content">
				{@html a.content_html || a.summary || ''}
			</div>
		</article>
	{/if}
</div>

<style>
	.shell {
		display: grid;
		grid-template-columns: 260px minmax(320px, 1fr) minmax(0, 1.4fr);
		height: 100vh;
		overflow: hidden;
	}
	.shell:not(.reading) {
		grid-template-columns: 260px 1fr;
	}
	.brand-name {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.who {
		font-size: 0.72rem;
		color: var(--muted);
		max-width: 180px;
	}
	.search {
		margin: 0.25rem 0;
	}
	.viewsel {
		display: inline-flex;
	}
	.viewsel button {
		border-radius: 0;
		padding: 0.4rem 0.55rem;
	}
	.viewsel button:first-child {
		border-radius: var(--radius) 0 0 var(--radius);
	}
	.viewsel button:last-child {
		border-radius: 0 var(--radius) var(--radius) 0;
		border-left: none;
	}
	.viewsel button:nth-child(2) {
		border-left: none;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 0.75rem;
		padding: 0.5rem 0.25rem;
	}
	.grid.masonry {
		display: block;
		column-width: 340px;
		column-gap: 0.75rem;
	}
	.acard {
		display: flex;
		gap: 0.75rem;
		padding: 0.6rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		cursor: pointer;
		text-align: left;
		width: 100%;
		border-left: 3px solid transparent;
	}
	.grid.masonry .acard {
		break-inside: avoid;
		margin-bottom: 0.75rem;
	}
	.acard.selected {
		border-left-color: var(--accent);
	}
	.acard.read .atitle {
		color: var(--muted);
		font-weight: 400;
	}
	.thumb {
		width: 96px;
		height: 96px;
		object-fit: cover;
		border-radius: 6px;
		flex: none;
	}
	.acard-body {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.excerpt {
		margin: 0.15rem 0 0;
		font-size: 0.85rem;
		color: var(--muted);
		display: -webkit-box;
		-webkit-line-clamp: 4;
		line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.sidebar {
		border-right: 1px solid var(--border);
		background: var(--surface);
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		overflow-y: auto;
	}
	.brand {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 1.1rem;
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.nav {
		text-align: left;
		border: none;
		background: none;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.nav.active {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.section {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
		margin-top: 0.5rem;
	}
	.mini {
		padding: 0.1rem 0.5rem;
	}
	.add {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.cand {
		display: flex;
		gap: 0.4rem;
		align-items: center;
		justify-content: space-between;
	}
	.feeds {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}
	.feeds li {
		display: flex;
		align-items: center;
	}
	.feeds li.active {
		background: var(--accent-soft);
		border-radius: var(--radius);
	}
	.feed {
		flex: 1;
		text-align: left;
		border: none;
		background: none;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.x {
		border: none;
		background: none;
		color: var(--muted);
		opacity: 0;
	}
	.feeds li:hover .x {
		opacity: 1;
	}
	.badge {
		background: var(--accent);
		color: #fff;
		border-radius: 999px;
		padding: 0 0.4rem;
		font-size: 0.72rem;
	}
	.favicon {
		width: 16px;
		height: 16px;
		border-radius: 3px;
		flex: none;
		object-fit: cover;
	}
	.favicon.dot {
		width: 8px;
		height: 8px;
		margin: 0 4px;
		border-radius: 50%;
		background: var(--border);
	}
	.trending {
		padding: 0.75rem 0.25rem;
		border-bottom: 1px solid var(--border);
	}
	.trending h3 {
		margin: 0 0 0.5rem;
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--muted);
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: 0.5rem;
	}
	.card {
		text-align: left;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 0.5rem;
	}
	.ctitle {
		font-weight: 600;
		font-size: 0.85rem;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.cmeta {
		font-size: 0.72rem;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-top: 0.5rem;
	}
	.tag {
		font-size: 0.72rem;
		background: var(--accent-soft);
		color: var(--accent);
		border-radius: 999px;
		padding: 0.1rem 0.5rem;
	}
	.spacer {
		flex: 1;
	}
	.list {
		border-right: 1px solid var(--border);
		overflow-y: auto;
		padding: 0 0.5rem 2rem;
	}
	.list header {
		position: sticky;
		top: 0;
		background: var(--bg);
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.6rem 0.25rem;
		z-index: 1;
	}
	.list header h2 {
		margin: 0;
		font-size: 1rem;
	}
	.actions {
		display: flex;
		gap: 0.4rem;
	}
	.list ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.list li {
		padding: 0.6rem 0.5rem;
		border-bottom: 1px solid var(--border);
		cursor: pointer;
		border-left: 3px solid transparent;
	}
	.list li.selected {
		background: var(--accent-soft);
		border-left-color: var(--accent);
	}
	.list li.read .atitle {
		color: var(--muted);
		font-weight: 400;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.atitle {
		font-weight: 600;
	}
	.time {
		flex: none;
		font-size: 0.8rem;
	}
	.meta {
		display: flex;
		justify-content: space-between;
		font-size: 0.8rem;
		margin-top: 0.2rem;
	}
	.star {
		color: #eab308;
	}
	.reader {
		overflow-y: auto;
		padding: 1.25rem 1.5rem 3rem;
	}
	.reader-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		position: sticky;
		top: 0;
		background: var(--bg);
		padding-bottom: 0.5rem;
	}
	.reader-actions {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	.btn {
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.45rem 0.8rem;
	}
	.reader .content {
		margin-top: 1rem;
		line-height: 1.7;
		overflow-wrap: anywhere;
	}
	.reader .content :global(img) {
		max-width: 100%;
		height: auto;
	}
	.close {
		border: none;
		background: none;
		font-size: 1.4rem;
		line-height: 1;
	}
	.ellipsis {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.small {
		font-size: 0.82rem;
	}
	.center {
		text-align: center;
	}
	.hint {
		text-align: center;
		font-size: 0.75rem;
		padding: 1rem 0;
	}
	.empty {
		padding: 2rem;
		text-align: center;
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}

	@media (max-width: 900px) {
		.shell {
			grid-template-columns: 1fr;
		}
		.sidebar {
			display: none;
		}
		.reader {
			position: fixed;
			inset: 0;
			background: var(--bg);
			z-index: 10;
		}
	}
</style>
