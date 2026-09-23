<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime, readingTime, stripHtml } from '$lib/format';
	import type { Article, DiscoveredFeed, Folder, Insights, Subscription } from '$lib/types';

	type View = 'list' | 'cardlist' | 'cards' | 'masonry';

	function initialView(): View {
		if (typeof localStorage !== 'undefined') {
			const v = localStorage.getItem('view');
			if (v === 'list' || v === 'cardlist' || v === 'cards' || v === 'masonry') return v;
		}
		// No explicit choice yet: phones default to the single-column card list
		// (image + title + excerpt), desktop to the compact list.
		if (typeof window !== 'undefined' && window.innerWidth <= 900) return 'cardlist';
		return 'list';
	}

	type Filter =
		| { kind: 'all' }
		| { kind: 'unread' }
		| { kind: 'saved' }
		| { kind: 'favorites' }
		| { kind: 'foryou' }
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
	let insights = $state<Insights | null>(null);
	let ranking = $state<keyof Insights>('trending_now');
	let carouselEl = $state<HTMLElement | null>(null);
	let readerEl = $state<HTMLElement | null>(null);
	let readingStart = 0;
	let similarList = $state<Article[]>([]);
	let refreshing = $state(false);
	let refreshMsg = $state('');

	const RANKINGS: (keyof Insights)[] = [
		'trending_now',
		'top',
		'most_saved',
		'deep_reads',
		'hidden_gems'
	];
	const currentList = $derived(insights ? insights[ranking] : []);
	const grouped = $derived(
		folders.map((f) => ({ folder: f, subs: subs.filter((s) => s.folder_id === f.id) }))
	);
	const ungrouped = $derived(subs.filter((s) => !s.folder_id));
	let query = $state('');
	let searchMode = $state<'text' | 'ai'>('text');
	let view = $state<View>(initialView());
	let searchTimer: ReturnType<typeof setTimeout> | undefined;
	// Mobile-only: the sidebar becomes an off-canvas drawer.
	let sidebarOpen = $state(false);

	function loadCollapsed(): Set<string> {
		try {
			return new Set(JSON.parse(localStorage.getItem('collapsed_folders') || '[]'));
		} catch {
			return new Set();
		}
	}
	let collapsed = $state<Set<string>>(loadCollapsed());

	function toggleCollapse(id: string) {
		const next = new Set(collapsed);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		collapsed = next;
		try {
			localStorage.setItem('collapsed_folders', JSON.stringify([...next]));
		} catch {
			/* ignore */
		}
	}

	function initialShowTrending(): boolean {
		try {
			const v = localStorage.getItem('show_trending');
			if (v === '0') return false;
			if (v === '1') return true;
		} catch {
			/* ignore */
		}
		return typeof window === 'undefined' || window.innerWidth > 900;
	}
	let showTrending = $state(initialShowTrending());

	function toggleTrending() {
		showTrending = !showTrending;
		try {
			localStorage.setItem('show_trending', showTrending ? '1' : '0');
		} catch {
			/* ignore */
		}
	}

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
		if (query.trim()) {
			p.q = query.trim();
			if (searchMode === 'ai') p.semantic = 'true';
		}
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
			if (filter.kind === 'foryou') {
				articles = await api.forYou(40);
				cursor = null;
				hasMore = false;
				if (reset) selected = 0;
				return;
			}
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
		sidebarOpen = false; // close the mobile drawer after picking a feed/folder
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
		similarList = [];
		api.similar(a.id, 6)
			.then((r) => {
				if (openArticle?.id === a.id) similarList = r;
			})
			.catch(() => {});
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
		similarList = [];
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

	async function refresh() {
		if (refreshing) return;
		refreshing = true;
		refreshMsg = $t('searching');
		try {
			const src = filter.kind === 'source' ? filter.id : undefined;
			const res = await api.refresh(src);
			await Promise.all([loadArticles(true), loadSidebar()]);
			loadInsights();
			refreshMsg =
				res.new_articles > 0 ? `+${res.new_articles} ${$t('new_items')}` : $t('no_new');
		} catch {
			refreshMsg = '⚠';
		} finally {
			refreshing = false;
			setTimeout(() => (refreshMsg = ''), 5000);
		}
	}

	async function loadInsights() {
		try {
			insights = await api.insights(720, 12);
		} catch {
			insights = null;
		}
	}

	function scrollCarousel(dir: 1 | -1) {
		carouselEl?.scrollBy({ left: dir * Math.max(300, carouselEl.clientWidth * 0.8), behavior: 'smooth' });
	}

	async function newFolder() {
		const name = prompt($t('new_folder'));
		if (name && name.trim()) {
			await api.createFolder(name.trim());
			await loadSidebar();
		}
	}

	async function assignFolder(sub: Subscription, folderId: string) {
		await api.updateSubscription(sub.id, { folder_id: folderId || null });
		await loadSidebar();
	}

	async function removeFolder(folder: Folder) {
		if (!confirm($t('confirm_delete_folder'))) return;
		await api.deleteFolder(folder.id);
		if (filter.kind === 'folder' && filter.id === folder.id) setFilter({ kind: 'unread' });
		await loadSidebar();
	}

	function folderUnread(subsIn: Subscription[]): number {
		return subsIn.reduce((n, s) => n + s.unread_count, 0);
	}

	async function shareArticle(a: Article) {
		if (a.url) {
			try {
				await navigator.clipboard.writeText(a.url);
			} catch {
				/* ignore */
			}
			api.engage(a.id, 'share').catch(() => {});
		}
	}

	function openOriginal(a: Article) {
		api.engage(a.id, 'open').catch(() => {});
	}

	async function markRead(a: Article, read: boolean) {
		a.is_read = read;
		articles = [...articles];
		// Marking read from the list without opening is a weak "skip" signal.
		if (read && openArticle?.id !== a.id) api.engage(a.id, 'skip').catch(() => {});
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

	function sourceFavicon(id: string): string | null {
		return subs.find((x) => x.source.id === id)?.source.favicon_url ?? null;
	}

	function thumbUrl(a: Article): string | null {
		return a.image_url || sourceFavicon(a.source_id);
	}

	function hideImg(e: Event) {
		const el = e.currentTarget;
		if (el instanceof HTMLElement) el.style.display = 'none';
	}

	onMount(async () => {
		await loadSidebar();
		await loadArticles(true);
		loadInsights();
	});

	onDestroy(() => flushReadEvent());
</script>

<svelte:window onkeydown={onKey} />

<div class="shell" class:reading={openArticle}>
	{#if sidebarOpen}
		<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
		<div class="backdrop" onclick={() => (sidebarOpen = false)}></div>
	{/if}
	<aside class="sidebar" class:open={sidebarOpen}>
		<div class="brand">
			<div class="brand-left">
				<img class="brand-logo" src="/logo.png" alt="" width="28" height="28" />
				<div class="brand-name">
					<strong>{$t('app_name')}</strong>
					{#if $user}<span class="who ellipsis">{$user.display_name || $user.email}</span>{/if}
				</div>
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
		{#if query.trim()}
			<div class="searchmode">
				<button
					class:active={searchMode === 'text'}
					onclick={() => {
						searchMode = 'text';
						loadArticles(true);
					}}>{$t('search_text')}</button
				>
				<button
					class:active={searchMode === 'ai'}
					onclick={() => {
						searchMode = 'ai';
						loadArticles(true);
					}}>✨ {$t('search_ai')}</button
				>
			</div>
		{/if}

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
			<button
				class="nav"
				class:active={filter.kind === 'foryou'}
				onclick={() => setFilter({ kind: 'foryou' })}
			>
				✨ {$t('for_you')}
			</button>
		</nav>

		{#snippet feedRow(s: Subscription)}
			<li class:active={filter.kind === 'source' && filter.id === s.source.id}>
				<button class="feed" onclick={() => setFilter({ kind: 'source', id: s.source.id })}>
					{#if s.source.favicon_url}
						<img class="favicon" src={s.source.favicon_url} alt="" loading="lazy" onerror={hideImg} />
					{:else}
						<span class="favicon dot"></span>
					{/if}
					<span class="ellipsis">{s.custom_title || s.source.title || s.source.feed_url}</span>
					{#if s.unread_count}<span class="badge">{s.unread_count}</span>{/if}
				</button>
				<select
					class="movesel"
					title={$t('folders')}
					onchange={(e) => assignFolder(s, (e.currentTarget as HTMLSelectElement).value)}
				>
					<option value="" selected={!s.folder_id}>{$t('no_folder')}</option>
					{#each folders as f (f.id)}
						<option value={f.id} selected={s.folder_id === f.id}>{f.name}</option>
					{/each}
				</select>
				<button class="x" title={$t('unsubscribe')} onclick={() => unsubscribe(s)}>×</button>
			</li>
		{/snippet}

		<div class="section">
			<span>{$t('feeds')}</span>
			<span class="section-actions">
				<button class="mini" title={$t('new_folder')} onclick={newFolder}>📁</button>
				<button class="mini" title={$t('add_feed')} onclick={() => (showAdd = !showAdd)}>＋</button>
			</span>
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

		{#each grouped as g (g.folder.id)}
			<div class="folder-row">
				<button
					class="caret"
					aria-label="toggle"
					onclick={() => toggleCollapse(g.folder.id)}
				>
					{collapsed.has(g.folder.id) ? '▸' : '▾'}
				</button>
				<button
					class="feed folder"
					class:active={filter.kind === 'folder' && filter.id === g.folder.id}
					onclick={() => setFilter({ kind: 'folder', id: g.folder.id })}
				>
					<span class="ellipsis">📁 {g.folder.name}</span>
					{#if folderUnread(g.subs)}<span class="badge">{folderUnread(g.subs)}</span>{/if}
				</button>
				<button class="x" title={$t('delete_folder')} onclick={() => removeFolder(g.folder)}>×</button>
			</div>
			{#if !collapsed.has(g.folder.id)}
				<ul class="feeds indent">
					{#each g.subs as s (s.id)}{@render feedRow(s)}{/each}
				</ul>
			{/if}
		{/each}

		<ul class="feeds">
			{#each ungrouped as s (s.id)}{@render feedRow(s)}{/each}
		</ul>

		<div class="spacer"></div>
		<button class="nav" onclick={logout}>{$t('logout')}</button>
	</aside>

	<main class="list">
		<header>
			<button
				class="hamburger"
				onclick={() => (sidebarOpen = !sidebarOpen)}
				aria-label={$t('menu')}
				title={$t('menu')}
			>☰</button>
			<h2>
				{#if filter.kind === 'source'}{sourceName(filter.id)}
				{:else if filter.kind === 'folder'}{folderName(filter.id)}
				{:else}{$t(filter.kind)}{/if}
			</h2>
			<div class="actions">
				{#if refreshMsg}<span class="refresh-msg muted">{refreshMsg}</span>{/if}
				<div class="viewsel" role="group" aria-label="view">
					<button class:active={view === 'list'} onclick={() => setView('list')} title={$t('view_list')}>☰</button>
					<button class:active={view === 'cardlist'} onclick={() => setView('cardlist')} title={$t('view_cardlist')}>▤</button>
					<button class:active={view === 'cards'} onclick={() => setView('cards')} title={$t('view_cards')}>▭</button>
					<button class:active={view === 'masonry'} onclick={() => setView('masonry')} title={$t('view_masonry')}>▦</button>
				</div>
				<button
					class:active={showTrending}
					onclick={toggleTrending}
					title="{$t('trending_bar')} — {showTrending ? $t('hide') : $t('show')}"
				>🔥</button>
				<button
					onclick={refresh}
					disabled={refreshing}
					class:spin={refreshing}
					title={$t('refresh')}
				>↻</button>
				<button onclick={markAllRead}>{$t('mark_all_read')}</button>
			</div>
		</header>

		{#if insights && showTrending}
			<section class="trending">
				<div class="rank-tabs">
					{#each RANKINGS as r (r)}
						<button class="rtab" class:active={ranking === r} onclick={() => (ranking = r)}>
							{$t(r)}
						</button>
					{/each}
				</div>
				{#if currentList.length > 0}
					<div class="carousel-wrap">
						<button class="arrow" onclick={() => scrollCarousel(-1)} aria-label="prev">‹</button>
						<div class="carousel" bind:this={carouselEl}>
							{#each currentList as it (it.article.id)}
								<button class="tcard" onclick={() => openArticleObj(it.article)}>
									{#if thumbUrl(it.article)}
										<img
											class="tthumb"
											src={thumbUrl(it.article)}
											alt=""
											loading="lazy"
											onerror={hideImg}
										/>
									{/if}
									<div class="tbody">
										<span class="ctitle">{it.article.title || it.article.url}</span>
										<span class="cmeta muted">
											{sourceName(it.article.source_id) || ''} · {it.readers} {$t('readers')}
										</span>
										<p class="texcerpt">
											{it.article.ai_summary || stripHtml(it.article.summary || it.article.content_html)}
										</p>
									</div>
								</button>
							{/each}
						</div>
						<button class="arrow" onclick={() => scrollCarousel(1)} aria-label="next">›</button>
					</div>
				{/if}
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
							{#if a.dup_count > 1}<span class="dup" title={$t('duplicates')}>+{a.dup_count - 1}</span>{/if}
							{#if a.is_saved}<span class="star">★</span>{/if}
							{#if a.is_favorite}<span class="star">♥</span>{/if}
						</div>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="grid" class:masonry={view === 'masonry'} class:cardlist={view === 'cardlist'}>
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
						{#if thumbUrl(a)}
							<img class="thumb" src={thumbUrl(a)} alt="" loading="lazy" onerror={hideImg} />
						{/if}
						<div class="acard-body">
							<div class="atitle">{title(a)}</div>
							<div class="meta muted">
								<span class="ellipsis">{sourceName(a.source_id)}</span>
								<span>· {relativeTime(a.published_at, $locale)}</span>
								{#if a.dup_count > 1}<span class="dup" title={$t('duplicates')}>+{a.dup_count - 1}</span>{/if}
								{#if a.is_saved}<span class="star">★</span>{/if}
								{#if a.is_favorite}<span class="star">♥</span>{/if}
							</div>
							<p class="excerpt">{a.ai_summary || stripHtml(a.summary || a.content_html)}</p>
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
					{#if a.url}<button onclick={() => shareArticle(a)}>{$t('share')}</button>{/if}
					{#if a.url}
						<a
							class="btn"
							href={a.url}
							target="_blank"
							rel="noopener"
							onclick={() => openOriginal(a)}
						>
							{$t('open_original')}
						</a>
					{/if}
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
			{#if a.ai_summary}
				<div class="ai-summary">
					<span class="ai-summary-label">✨ {$t('summary_label')}</span>
					{a.ai_summary}
				</div>
			{/if}
			<div class="content">
				{@html a.content_html || a.summary || ''}
			</div>
			{#if similarList.length}
				<div class="similar">
					<h3>✨ {$t('similar')}</h3>
					{#each similarList as s (s.id)}
						<button class="simrow" onclick={() => openArticleObj(s)}>
							{#if thumbUrl(s)}
								<img class="simthumb" src={thumbUrl(s)} alt="" loading="lazy" onerror={hideImg} />
							{/if}
							<span class="simbody">
								<span class="ellipsis2">{title(s)}</span>
								<span class="cmeta muted">{sourceName(s.source_id) || ''}</span>
							</span>
						</button>
					{/each}
				</div>
			{/if}
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
	.brand-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.brand-logo {
		border-radius: 6px;
		flex: none;
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
	.searchmode {
		display: flex;
		gap: 0.25rem;
		margin-bottom: 0.25rem;
	}
	.searchmode button {
		flex: 1;
		padding: 0.2rem 0.4rem;
		font-size: 0.78rem;
		border: 1px solid var(--border);
		background: none;
	}
	.searchmode button.active {
		background: var(--accent-soft);
		color: var(--accent);
		border-color: var(--accent);
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
	.grid.cardlist {
		display: flex;
		flex-direction: column;
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
	.feeds li:hover .x,
	.folder-row:hover .x {
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
	.rank-tabs {
		display: flex;
		gap: 0.25rem;
		flex-wrap: wrap;
		margin-bottom: 0.5rem;
	}
	.rtab {
		border: none;
		background: none;
		color: var(--muted);
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
		font-size: 0.8rem;
	}
	.rtab.active {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.carousel-wrap {
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}
	.carousel {
		display: flex;
		gap: 0.5rem;
		overflow-x: auto;
		scroll-behavior: smooth;
		scrollbar-width: thin;
		padding-bottom: 0.25rem;
	}
	.arrow {
		flex: none;
		border-radius: 50%;
		width: 32px;
		height: 32px;
		padding: 0;
		line-height: 1;
	}
	.tcard {
		flex: 0 0 480px;
		max-width: 90vw;
		display: flex;
		gap: 0.6rem;
		padding: 0.6rem;
		text-align: left;
		background: var(--surface);
		border: 1px solid var(--border);
		align-items: flex-start;
	}
	.tthumb {
		width: 104px;
		height: 104px;
		object-fit: cover;
		border-radius: 8px;
		flex: none;
	}
	.ctitle {
		-webkit-line-clamp: 3;
		line-clamp: 3;
	}
	.texcerpt {
		margin: 0.15rem 0 0;
		font-size: 0.78rem;
		color: var(--muted);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.similar {
		margin-top: 1.5rem;
		border-top: 1px solid var(--border);
		padding-top: 1rem;
	}
	.similar h3 {
		margin: 0 0 0.5rem;
		font-size: 0.85rem;
	}
	.simrow {
		display: flex;
		gap: 0.6rem;
		align-items: center;
		width: 100%;
		text-align: left;
		border: none;
		background: none;
		padding: 0.4rem 0;
	}
	.simthumb {
		width: 48px;
		height: 48px;
		object-fit: cover;
		border-radius: 6px;
		flex: none;
	}
	.simbody {
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.ellipsis2 {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
		font-weight: 600;
		font-size: 0.85rem;
	}
	.folder-row {
		display: flex;
		align-items: center;
	}
	.caret {
		border: none;
		background: none;
		color: var(--muted);
		padding: 0 0.25rem;
		font-size: 0.7rem;
	}
	.folder-row .feed.folder {
		flex: 1;
		margin-top: 0;
	}
	.tbody {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
	}
	.section-actions {
		display: inline-flex;
		gap: 0.25rem;
	}
	.feed.folder {
		font-weight: 600;
		margin-top: 0.25rem;
	}
	.feeds.indent .feed {
		padding-left: 1.1rem;
	}
	.movesel {
		width: auto;
		max-width: 0;
		opacity: 0;
		padding: 0;
		border: none;
		font-size: 0.72rem;
		transition: max-width 0.15s;
	}
	.feeds li:hover .movesel {
		max-width: 90px;
		opacity: 1;
		border: 1px solid var(--border);
		padding: 0.1rem 0.2rem;
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
		flex: 1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}
	.hamburger {
		display: none; /* desktop: sidebar is always visible */
		flex: none;
		padding: 0.4rem 0.55rem;
		font-size: 1.1rem;
		line-height: 1;
	}
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 19;
	}
	.actions {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	.refresh-msg {
		font-size: 0.8rem;
		white-space: nowrap;
	}
	.spin {
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.dup {
		background: var(--border);
		color: var(--muted);
		border-radius: 999px;
		padding: 0 0.35rem;
		font-size: 0.72rem;
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
	.ai-summary {
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: var(--accent-soft);
		border-radius: var(--radius);
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.ai-summary-label {
		display: block;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--accent);
		margin-bottom: 0.25rem;
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
		/* Single column. These selectors must beat `.shell:not(.reading)` and
		   `.shell.reading` (higher specificity), or the layout keeps a 260px
		   track for the hidden sidebar and squeezes the list into ~260px. */
		.shell,
		.shell:not(.reading),
		.shell.reading {
			grid-template-columns: 1fr;
		}
		/* Sidebar becomes an off-canvas drawer instead of display:none, so its
		   nav/search/folders stay reachable via the hamburger. */
		.sidebar {
			position: fixed;
			top: 0;
			left: 0;
			bottom: 0;
			width: min(84vw, 320px);
			z-index: 20;
			transform: translateX(-100%);
			transition: transform 0.2s ease;
			box-shadow: 0 0 24px rgba(0, 0, 0, 0.25);
		}
		.sidebar.open {
			transform: translateX(0);
		}
		.hamburger {
			display: inline-flex;
			align-items: center;
		}
		.list {
			border-right: none;
		}
		.list header {
			gap: 0.4rem 0.5rem;
			flex-wrap: wrap;
			padding: 0.5rem 0;
		}
		/* Toolbar drops to its own full-width row and scrolls horizontally,
		   so the title stays on one line and the buttons never squish. */
		.actions {
			order: 3;
			width: 100%;
			overflow-x: auto;
			-webkit-overflow-scrolling: touch;
			scrollbar-width: none;
		}
		.actions::-webkit-scrollbar {
			display: none;
		}
		.actions button {
			flex: none;
		}
		/* Two-column card grids on phones (Feedly-style), single-column list. */
		.grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.5rem;
			padding: 0.5rem 0;
		}
		.grid.masonry {
			column-width: auto;
			column-count: 2;
			column-gap: 0.5rem;
		}
		.grid.cardlist {
			display: flex;
		}
		/* Card-list rows: image left, text right — cap the thumb so the text
		   column is wide (fixes the one-word-per-line wrapping). */
		.grid.cardlist .thumb {
			width: 84px;
			height: 84px;
		}
		.reader {
			position: fixed;
			inset: 0;
			background: var(--bg);
			z-index: 25;
			padding: 1rem 1rem 3rem;
			/* No sideways scroll: content is clipped to the viewport so vertical
			   scrolling can't wobble the page left-right ("flan"). */
			overflow-x: hidden;
			overscroll-behavior: contain;
		}
		/* Action bar must not exceed the right edge: wrap onto more rows and use
		   compact buttons instead of spilling off-screen. */
		.reader-head {
			flex-wrap: wrap;
			gap: 0.4rem;
		}
		.reader-actions {
			flex-wrap: wrap;
		}
		.reader-actions button,
		.reader-actions .btn {
			padding: 0.4rem 0.6rem;
			font-size: 0.85rem;
		}
		/* Long words, wide media, tables and code blocks stay within the column
		   so nothing forces the layout wider than the screen. */
		.reader .content :global(*) {
			max-width: 100%;
		}
		.reader .content :global(pre),
		.reader .content :global(table) {
			overflow-x: auto;
			display: block;
		}
	}
</style>
