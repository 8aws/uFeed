<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { displayPrefs, speechPrefs, toolbarLabels } from '$lib/prefs';
	import {
		applyPending,
		flush,
		initOutbox,
		pendingCount,
		runOp,
		setFolderLookup,
		setState
	} from '$lib/outbox';
	import { embedOf, safeHtml, safeUrl } from '$lib/safe';
	import { offlineAudioUrl, warmAudio } from '$lib/offlineAudio';
	import { playJingle } from '$lib/player';
	import { unlockSpeech } from '$lib/speech';
	import { relativeTime, readingTime, stripHtml } from '$lib/format';
	import Onboarding from '$lib/components/Onboarding.svelte';
	import InstallPrompt from '$lib/components/InstallPrompt.svelte';
	import ListenBar from '$lib/components/ListenBar.svelte';
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
	let offline = $state(typeof navigator !== 'undefined' && !navigator.onLine);
	// Current plan's limits (hide AI entry points the plan doesn't include).
	let aiAllowed = $state(true);
	// Read aloud: the bar opens from the reader (or by itself in accessibility
	// mode); the server voice depends on the plan.
	let listenOpen = $state(false);
	let ttsServerAllowed = $state(false);
	let readerContentEl = $state<HTMLElement | null>(null);
	// Mobile-only: the sidebar becomes an off-canvas drawer.
	let sidebarOpen = $state(false);
	// Long-press bookkeeping: ignore the tap that ends the gesture, and delay
	// removing a just-read post so a mis-press can be undone.
	let lastLongPress = 0;

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

	let listEl = $state<HTMLElement | null>(null);
	// Animated scroll to top driven frame by frame. Native smooth scrolling gets
	// interrupted when content above shifts (lazy images, the trending carousel
	// appearing) because of scroll anchoring; setting an absolute position on
	// every frame always lands at the top.
	function scrollListTop() {
		const el = listEl;
		if (!el || el.scrollTop <= 0) return;
		const start = el.scrollTop;
		const t0 = performance.now();
		const duration = Math.min(500, 180 + start / 8);
		const step = (now: number) => {
			const p = Math.min(1, (now - t0) / duration);
			el.scrollTop = Math.round(start * Math.pow(1 - p, 3));
			if (p < 1) requestAnimationFrame(step);
		};
		requestAnimationFrame(step);
	}

	async function toggleTrending() {
		showTrending = !showTrending;
		try {
			localStorage.setItem('show_trending', showTrending ? '1' : '0');
		} catch {
			/* ignore */
		}
		// Turning it on while scrolled down would otherwise leave the bar out of
		// view — bring the list back to the top so it's visible. Wait for the
		// carousel to be in the DOM first: inserting content above the viewport
		// during a smooth scroll triggers scroll anchoring, which cancels it.
		if (showTrending) {
			await tick();
			scrollListTop();
		}
	}

	const VIEWS: View[] = ['list', 'cardlist', 'cards', 'masonry'];
	const VIEW_ICONS: Record<View, string> = { list: '☰', cardlist: '▤', cards: '▭', masonry: '▦' };
	let viewOpen = $state(false);
	let viewPos = $state({ top: 0, left: 0 });

	function toggleViewMenu(e: MouseEvent) {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		// Below the button, kept inside the viewport (the menu is ~200px wide).
		const left = Math.min(Math.round(r.left), window.innerWidth - 208);
		viewPos = { top: Math.round(r.bottom + 6), left: Math.max(8, left) };
		viewOpen = !viewOpen;
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

	const totalUnread = $derived(subs.reduce((n, s) => n + (s.muted ? 0 : s.unread_count), 0));

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

	// Cold-start snapshot: the sidebar and the first page of Unread from the
	// last session, kept in the offline cache (cleared on logout). It's painted
	// first and then replaced by fresh data, so the app never opens blank.
	const SNAPSHOT_CACHE = 'ufeed-offline-api';
	const SNAPSHOT_KEY = '/__offline/home';
	type Snapshot = {
		user: string;
		folders: Folder[];
		subs: Subscription[];
		articles: Article[];
		cursor: string | null;
	};
	let fromSnapshot = $state(false);

	async function readSnapshot(): Promise<Snapshot | null> {
		try {
			const hit = await (await caches.open(SNAPSHOT_CACHE)).match(SNAPSHOT_KEY);
			const snap = hit ? ((await hit.json()) as Snapshot) : null;
			return snap && snap.user === $user?.id ? snap : null;
		} catch {
			return null;
		}
	}

	function writeSnapshot() {
		if (filter.kind !== 'unread' || !$user || typeof caches === 'undefined') return;
		const snap: Snapshot = {
			user: $user.id,
			folders,
			subs,
			articles: articles.slice(0, 40),
			cursor: articles.length > 40 ? null : cursor
		};
		caches
			.open(SNAPSHOT_CACHE)
			.then((c) =>
				c.put(SNAPSHOT_KEY, new Response(JSON.stringify(snap), { headers: { 'content-type': 'application/json' } }))
			)
			.catch(() => {});
	}

	// Changes made offline and not yet synced win over what the server says,
	// so a post read without connection doesn't come back as unread.
	function withPending(items: Article[]): Article[] {
		applyPending(items);
		return filter.kind === 'unread' ? items.filter((a) => !a.is_read) : items;
	}

	// Send queued offline changes; tell the reader and refresh the counts.
	async function syncOutbox() {
		if ($pendingCount === 0) return;
		const sent = await flush().catch(() => 0);
		if (sent > 0) {
			refreshMsg = `✓ ${sent} ${$t(sent === 1 ? 'synced_one' : 'synced')}`;
			setTimeout(() => (refreshMsg = ''), 4000);
			loadSidebar().catch(() => {});
		}
	}

	// A reset load (new filter, refresh) supersedes one still in flight, so a
	// tap on a feed while the first load is slow isn't lost or overwritten.
	let loadSeq = 0;
	async function loadArticles(reset: boolean) {
		if (loading && !reset) return;
		const seq = ++loadSeq;
		loading = true;
		try {
			if (filter.kind === 'foryou') {
				const items = withPending(await api.forYou(40));
				if (seq !== loadSeq) return;
				articles = items;
				cursor = null;
				hasMore = false;
				if (reset) selected = 0;
				return;
			}
			const page = await api.listArticles(buildParams(reset));
			if (seq !== loadSeq) return;
			const items = withPending(page.items);
			articles = reset ? items : [...articles, ...items];
			cursor = page.next_cursor;
			hasMore = !!page.next_cursor;
			if (reset) {
				selected = 0;
				fromSnapshot = false;
				writeSnapshot();
			}
		} catch (e) {
			if (seq !== loadSeq) return;
			// No connection: fall back to the saved articles kept for offline use.
			if (!navigator.onLine || (e instanceof ApiError && e.code === 'offline')) {
				offline = true;
				if (filter.kind !== 'saved') {
					filter = { kind: 'saved' };
					await loadArticles(true);
					return;
				}
			}
		} finally {
			if (seq === loadSeq) loading = false;
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
		if (dwell > 1000)
			runOp({ type: 'readEvent', id: a.id, dwell_ms: dwell, completion: Math.max(0, Math.min(1, completion)) });
	}

	// On-demand LLM summary for the open article (in the reader's language).
	let llm = $state<{
		id: string;
		summary: string | null;
		title: string | null;
		model: string | null;
		loading: boolean;
		error: string;
	} | null>(null);

	let llmSecs = $state(0); // shown while the on-device LLM works (~15-20 s)
	async function generateLLM(a: Article) {
		if (!llm || llm.id !== a.id || llm.loading) return;
		summaryOpen = true; // the result shows in the (unfolded) box
		llm = { ...llm, loading: true, error: '' };
		llmSecs = 0;
		const tick = setInterval(() => llmSecs++, 1000);
		try {
			const r = await api.aiSummary(a.id, $locale, true);
			if (llm?.id === a.id) llm = { ...llm, ...r, loading: false };
		} catch (e) {
			const code = e instanceof ApiError ? e.code : '';
			const msg =
				code === 'rate_limited'
					? $t('ai_rate')
					: code === 'plan_limit_ai'
						? $t('plan_limit_ai')
						: $t('ai_unavailable');
			if (llm?.id === a.id) llm = { ...llm, loading: false, error: msg };
		} finally {
			clearInterval(tick);
		}
	}

	// Machine translation of the open article into the reader's language
	// (EN<->ES, ~3-4 s, stored and shared); also used by "read in my language".
	const MT_LANGS = ['es', 'en'];
	let tr = $state<{ id: string; title: string | null; paragraphs: string[] } | null>(null);
	let showTr = $state(false);
	let trLoading = $state(false);
	let trError = $state('');
	const baseLang = (l: string | null | undefined) => (l || '').split(/[-_]/)[0].toLowerCase();
	function canTranslate(a: Article): boolean {
		const src = baseLang(a.lang);
		return aiAllowed && MT_LANGS.includes(src) && MT_LANGS.includes($locale) && src !== $locale;
	}
	async function loadTranslation(a: Article) {
		if (tr?.id === a.id) {
			showTr = true;
			return tr;
		}
		trLoading = true;
		trError = '';
		try {
			const r = await api.translation(a.id, $locale, true);
			if (!r.paragraphs || openArticle?.id !== a.id) return null;
			tr = { id: a.id, title: r.title, paragraphs: r.paragraphs };
			showTr = true;
			return tr;
		} catch {
			trError = $t('translate_unavailable');
			return null;
		} finally {
			trLoading = false;
		}
	}
	function toggleTranslation(a: Article) {
		if (showTr && tr?.id === a.id) showTr = false;
		else loadTranslation(a);
	}

	// --- Full article (feeds that only publish an excerpt) ----------------------
	// The server fetches the page once and extracts the article; it's shown
	// instead of the teaser and used by the voice, translation and Post radio.
	const fullHtml = new Map<string, string>();
	const fullPending = new Map<string, Promise<void>>();
	let fullShown = $state<Record<string, boolean>>({});
	let fullBusy = $state<string | null>(null);
	let fullMsg = $state('');
	const isExcerpt = (a: Article) => (a.word_count ?? 0) < 200 || a.full_status === 'ok';
	function loadFull(a: Article, manual = false): Promise<void> {
		if (fullHtml.has(a.id)) {
			fullShown = { ...fullShown, [a.id]: true };
			return Promise.resolve();
		}
		if (!safeUrl(a.url)) return Promise.resolve();
		let p = fullPending.get(a.id);
		if (!p) {
			fullBusy = a.id;
			fullMsg = '';
			p = api
				.fullText(a.id)
				.then((r) => {
					if (r.html) {
						fullHtml.set(a.id, r.html);
						a.full_status = 'ok';
						if (tr?.id === a.id) tr = null; // translated from the teaser
						fullShown = { ...fullShown, [a.id]: true };
					} else if (manual) fullMsg = $t('full_unavailable');
				})
				.catch(() => {
					if (manual) fullMsg = $t('full_unavailable');
				})
				.finally(() => {
					fullPending.delete(a.id);
					if (fullBusy === a.id) fullBusy = null;
				});
			fullPending.set(a.id, p);
		}
		return p;
	}
	function toggleFull(a: Article) {
		moreOpen = false;
		if (fullShown[a.id]) fullShown = { ...fullShown, [a.id]: false };
		else loadFull(a, true);
	}

	function openArticleObj(a: Article, markOnOpen = true) {
		// Opening another post by hand ends Post radio.
		if (radio && radio.queue[radio.pos]?.id !== a.id) radio = null;
		flushReadEvent();
		openArticle = a;
		showTr = false;
		trError = '';
		moreOpen = false;
		fullMsg = '';
		if ($displayPrefs.autoFull && isExcerpt(a)) loadFull(a);
		// Each article opens at its top, close button in reach.
		tick().then(() => readerEl?.scrollTo(0, 0));
		readingStart = Date.now();
		similarList = [];
		llm = { id: a.id, summary: null, title: null, model: null, loading: false, error: '' };
		api.aiSummary(a.id, $locale)
			.then((r) => {
				if (llm?.id === a.id && r.summary) llm = { ...llm, ...r };
			})
			.catch(() => {});
		api.similar(a.id, 6)
			.then((r) => {
				if (openArticle?.id === a.id) similarList = r;
			})
			.catch(() => {});
		// Post radio marks a post read only once 70 % of it was heard.
		if (markOnOpen && !a.is_read) markRead(a, true);
	}

	// --- Post radio: the posts of the current list read one after another -----
	let radioAllowed = $state(false);
	let radioPlan = { posts: null as number | null, minutes: null as number | null };
	let radio = $state<{
		queue: Article[];
		pos: number;
		startedAt: number;
		limit: number | null;
		minutes: number | null;
	} | null>(null);
	const radioUrls = new Map<string, Promise<string | null>>();
	const capTo = (pref: number, max: number | null) => (!pref ? max : max == null ? pref : Math.min(pref, max));

	// Ask for the next post's server audio while this one plays: it starts
	// generating (live) so the chain doesn't pause between posts.
	function prefetchAudio(a: Article | undefined) {
		if (!a || radioUrls.has(a.id) || !ttsServerAllowed || $speechPrefs.mode !== 'server') return;
		const translated = $speechPrefs.myLanguage && canTranslate(a);
		const lang = translated ? $locale : baseLang(a.lang);
		if (!['es', 'en'].includes(lang)) return;
		const g = $speechPrefs.gender;
		radioUrls.set(
			a.id,
			offlineAudioUrl(a.id, lang, g)
				.then((u) => u ?? api.articleAudio(a.id, lang, g, translated).then((r) => r.url))
				.catch(() => null)
		);
	}

	function startRadio() {
		if (!radioAllowed) return;
		const from = openArticle ? articles.findIndex((x) => x.id === openArticle!.id) : 0;
		const queue = articles.slice(Math.max(0, from));
		if (!queue.length) return;
		// Inside the tap: unlocks speech and the shared audio element on iOS,
		// so the whole chain can play (even with the screen locked).
		if ($speechPrefs.mode === 'device') unlockSpeech();
		playJingle();
		radioUrls.clear();
		// Only this post now: the voice generates one article at a time, and
		// the next one asked too early could take the turn of the first.
		prefetchAudio(queue[0]);
		radio = {
			queue,
			pos: 0,
			startedAt: Date.now(),
			limit: capTo($speechPrefs.radioPosts, radioPlan.posts),
			minutes: capTo($speechPrefs.radioMinutes, radioPlan.minutes)
		};
		listenOpen = true;
		if (openArticle?.id !== queue[0].id) openArticleObj(queue[0], false);
	}

	async function radioAdvance(heard: number) {
		const r = radio;
		if (!r) return;
		const cur = r.queue[r.pos];
		if (heard >= 0.7 && !cur.is_read) markRead(cur, true);
		const next = r.queue[r.pos + 1];
		const done =
			!next ||
			(r.limit != null && r.pos + 1 >= r.limit) ||
			(r.minutes != null && Date.now() - r.startedAt >= r.minutes * 60000);
		await playJingle();
		if (radio !== r) return; // stopped meanwhile
		if (done) {
			radio = null;
			refreshMsg = `📻 ${$t('radio_done')}`;
			setTimeout(() => (refreshMsg = ''), 5000);
			return;
		}
		radio = { ...r, pos: r.pos + 1 };
		openArticleObj(next, false);
	}

	// While a post plays, get the next one ready (its audio starts generating),
	// once this one has had time to finish generating (~20x real time).
	$effect(() => {
		const r = radio;
		if (!r) return;
		const id = setTimeout(() => prefetchAudio(r.queue[r.pos + 1]), 12000);
		return () => clearTimeout(id);
	});

	function radioStop(heard: number) {
		const r = radio;
		radio = null;
		if (r && heard >= 0.7 && !r.queue[r.pos].is_read) markRead(r.queue[r.pos], true);
	}

	async function open(i: number) {
		if (i < 0 || i >= articles.length) return;
		// Ignore the tap that ends a long-press gesture (finger still travelling).
		if (Date.now() - lastLongPress < 800) return;
		selected = i;
		openArticleObj(articles[i]);
	}

	function closeReader() {
		radio = null;
		flushReadEvent();
		openArticle = null;
		similarList = [];
	}

	async function toggleFavorite(a: Article) {
		a.is_favorite = !a.is_favorite;
		articles = [...articles];
		try {
			await setState(a.id, 'favorite', a.is_favorite);
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
		} catch (e) {
			// Plan cooldown: tell the user when they can refresh again.
			if (e instanceof ApiError && e.code === 'refresh_cooldown') {
				const mins = Math.max(1, Math.ceil((e.retryAfter ?? 60) / 60));
				refreshMsg = `${$t('refresh_wait')} ${mins} min`;
			} else {
				refreshMsg = '⚠';
			}
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
		return subsIn.reduce((n, s) => n + (s.muted ? 0 : s.unread_count), 0);
	}

	async function toggleMute(sub: Subscription) {
		try {
			const updated = await api.updateSubscription(sub.id, { muted: !sub.muted });
			subs = subs.map((x) => (x.id === sub.id ? { ...x, muted: updated.muted } : x));
			await loadArticles(true);
		} catch {
			/* ignore */
		}
	}

	// Share: the system share sheet where there is one (phones, Safari/Edge
	// on desktop), otherwise copy the link and say so on the button.
	let copiedId = $state<string | null>(null);
	async function shareArticle(a: Article) {
		const url = safeUrl(a.url);
		if (!url) return;
		moreOpen = false;
		if (navigator.share) {
			try {
				await navigator.share({ title: title(a), url });
				runOp({ type: 'engage', id: a.id, kind: 'share' });
				return;
			} catch (e) {
				if ((e as DOMException)?.name === 'AbortError') return; // closed the sheet
			}
		}
		try {
			await navigator.clipboard.writeText(url);
		} catch {
			window.prompt($t('share'), url); // last resort: let them copy it
			return;
		}
		copiedId = a.id;
		setTimeout(() => (copiedId = null), 2500);
		runOp({ type: 'engage', id: a.id, kind: 'share' });
	}

	// Phones: the less used actions live in a "⋯" menu so the header fits one row.
	let moreOpen = $state(false);
	let morePos = $state({ top: 0, right: 0 });
	function toggleMore(e: MouseEvent) {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		morePos = { top: Math.round(r.bottom + 6), right: Math.max(8, Math.round(window.innerWidth - r.right)) };
		moreOpen = !moreOpen;
	}

	// The AI summary box starts folded (remembered): it's there when wanted.
	let summaryOpen = $state(typeof localStorage !== 'undefined' && localStorage.getItem('summary_open') === '1');
	function toggleSummary() {
		summaryOpen = !summaryOpen;
		try {
			localStorage.setItem('summary_open', summaryOpen ? '1' : '0');
		} catch {
			/* ignore */
		}
	}

	// Editors keep spam or unsuitable posts out of the shared Trending/rankings.
	const isCurator = $derived($user?.role === 'editor' || $user?.role === 'admin');
	let hiddenIds = $state<Set<string>>(new Set());
	async function toggleHidden(a: Article) {
		const hide = !hiddenIds.has(a.id);
		try {
			await api.setHidden(a.id, hide);
			const next = new Set(hiddenIds);
			if (hide) next.add(a.id);
			else next.delete(a.id);
			hiddenIds = next;
			loadInsights();
		} catch {
			/* ignore */
		}
	}

	function openOriginal(a: Article) {
		runOp({ type: 'engage', id: a.id, kind: 'open' });
	}

	async function markRead(a: Article, read: boolean) {
		a.is_read = read;
		// In Unread, a read post leaves the list at once (long-press, swipe, m key).
		articles = read && filter.kind === 'unread' ? articles.filter((x) => x.id !== a.id) : [...articles];
		// Marking read from the list without opening is a weak "skip" signal.
		if (read && openArticle?.id !== a.id) runOp({ type: 'engage', id: a.id, kind: 'skip' });
		try {
			// Queued (and synced later) if there's no connection right now.
			if ((await setState(a.id, 'read', read)) === 'sent') await refreshUnreadFor(a.source_id);
		} catch {
			/* permanent failure (e.g. article purged): nothing to retry */
		}
	}

	const audioOpts = () => ({
		gender: $speechPrefs.gender,
		myLang: $speechPrefs.myLanguage ? $locale : null,
		canTranslate
	});

	async function toggleSave(a: Article) {
		a.is_saved = !a.is_saved;
		articles = [...articles];
		try {
			await setState(a.id, 'saved', a.is_saved);
			// Saved for later: keep its recording too, if asked for in Settings.
			if (a.is_saved && $speechPrefs.offlineAudio && ttsServerAllowed) warmAudio([a], audioOpts(), false);
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
		// Apply it here at once; without connection it's queued and synced later
		// (only covering what had arrived by now).
		const inScope = (sourceId: string) =>
			source_id
				? sourceId === source_id
				: folder_id
					? subs.find((x) => x.source.id === sourceId)?.folder_id === folder_id
					: true;
		for (const a of articles) if (inScope(a.source_id)) a.is_read = true;
		articles = filter.kind === 'unread' ? articles.filter((a) => !a.is_read) : [...articles];
		subs = subs.map((x) => (inScope(x.source.id) ? { ...x, unread_count: 0 } : x));
		if ((await runOp({ type: 'markAll', folder_id, source_id })) === 'sent') {
			await Promise.all([loadArticles(true), loadSidebar()]);
		}
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
		try {
			await api.subscribe(url);
		} catch (e) {
			discoverMsg =
				e instanceof ApiError && e.code === 'plan_limit_feeds'
					? $t('plan_limit_feeds')
					: $t('no_feeds_found');
			return;
		}
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

	// YouTube/Vimeo in articles: a thumbnail card that loads the player (the
	// privacy-enhanced one, sandboxed) only when tapped, so nothing is fetched
	// from those sites just by opening the article. Links that stand alone in
	// their paragraph get the same card.
	function embeds(node: HTMLElement, _key: string) {
		const build = () => {
			for (const a of node.querySelectorAll<HTMLAnchorElement>('a[href]')) {
				const e = embedOf(a);
				if (!e) continue;
				// A paragraph holding only this link is replaced whole.
				const block = a.parentElement;
				const sole =
					!!block &&
					block !== node &&
					(block.tagName === 'P' || block.tagName === 'DIV') &&
					block.textContent?.trim() === a.textContent?.trim();
				if (!a.dataset.embed && !sole) continue;
				const card = document.createElement('div');
				card.className = `embed embed-${e.provider}`;
				const play = document.createElement('button');
				play.type = 'button';
				play.className = 'embed-play';
				play.setAttribute('aria-label', `▶ ${e.provider === 'youtube' ? 'YouTube' : 'Vimeo'}`);
				if (e.provider === 'youtube') {
					const img = document.createElement('img');
					img.src = `https://i.ytimg.com/vi/${e.id}/hqdefault.jpg`;
					img.alt = '';
					img.loading = 'lazy';
					play.append(img);
				}
				const icon = document.createElement('span');
				icon.className = 'embed-icon';
				icon.textContent = '▶';
				play.append(icon);
				const link = document.createElement('a');
				link.href = a.href;
				link.target = '_blank';
				link.rel = 'noopener noreferrer nofollow';
				link.className = 'embed-link';
				link.textContent = `${e.provider === 'youtube' ? 'YouTube' : 'Vimeo'} ↗`;
				play.addEventListener('click', () => {
					const f = document.createElement('iframe');
					f.src =
						e.provider === 'youtube'
							? `https://www.youtube-nocookie.com/embed/${e.id}?autoplay=1&rel=0&playsinline=1`
							: `https://player.vimeo.com/video/${e.id}?autoplay=1&dnt=1`;
					f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
					f.allowFullscreen = true;
					f.referrerPolicy = 'strict-origin-when-cross-origin';
					f.setAttribute(
						'sandbox',
						'allow-scripts allow-same-origin allow-presentation allow-popups allow-popups-to-escape-sandbox'
					);
					play.replaceWith(f);
				});
				card.append(play, link);
				(sole ? block : a).replaceWith(card);
			}
		};
		build();
		return { update: () => tick().then(build) };
	}

	// The long-pressed post may vanish while the finger is still down, leaving
	// the next post under it: the release (wherever it lands) and the click
	// right after it are swallowed so they can't open or toggle another post.
	function guardRelease() {
		const swallow = (e: Event) => {
			e.stopPropagation();
			e.preventDefault();
		};
		const release = () => {
			lastLongPress = Date.now();
			window.removeEventListener('pointerup', release, true);
			window.removeEventListener('pointercancel', release, true);
			window.addEventListener('click', swallow, { capture: true, once: true });
			setTimeout(() => window.removeEventListener('click', swallow, true), 400);
		};
		window.addEventListener('pointerup', release, true);
		window.addEventListener('pointercancel', release, true);
	}

	// Long-press a post (touch or mouse) to toggle read without opening it.
	// The following click is suppressed (capture phase) so `open()` doesn't fire.
	function longpress(node: HTMLElement, cb: () => void) {
		let handler = cb;
		let timer: ReturnType<typeof setTimeout> | undefined;
		let fired = false;
		let sx = 0;
		let sy = 0;
		const DELAY = 500;
		const MOVE = 10;
		const start = (e: PointerEvent) => {
			if (e.pointerType === 'mouse' && e.button !== 0) return;
			fired = false;
			sx = e.clientX;
			sy = e.clientY;
			timer = setTimeout(() => {
				fired = true;
				timer = undefined;
				lastLongPress = Date.now();
				guardRelease();
				try {
					navigator.vibrate?.(15);
				} catch {
					/* ignore */
				}
				handler();
			}, DELAY);
		};
		const cancel = () => {
			if (timer) {
				clearTimeout(timer);
				timer = undefined;
			}
			// If the press already fired, mark the release moment so the tap that
			// ends the gesture (and any immediate next tap) is ignored by open().
			if (fired) lastLongPress = Date.now();
		};
		const move = (e: PointerEvent) => {
			if (timer && (Math.abs(e.clientX - sx) > MOVE || Math.abs(e.clientY - sy) > MOVE)) cancel();
		};
		const onclick = (e: MouseEvent) => {
			if (fired) {
				e.stopPropagation();
				e.preventDefault();
				fired = false;
			}
		};
		node.addEventListener('pointerdown', start);
		node.addEventListener('pointermove', move);
		node.addEventListener('pointerup', cancel);
		node.addEventListener('pointercancel', cancel);
		node.addEventListener('pointerleave', cancel);
		node.addEventListener('click', onclick, true);
		return {
			update(next: () => void) {
				handler = next;
			},
			destroy() {
				cancel();
				node.removeEventListener('pointerdown', start);
				node.removeEventListener('pointermove', move);
				node.removeEventListener('pointerup', cancel);
				node.removeEventListener('pointercancel', cancel);
				node.removeEventListener('pointerleave', cancel);
				node.removeEventListener('click', onclick, true);
			}
		};
	}

	// Swipe a post: right = toggle read, left = toggle saved. Works with a finger
	// (pointer events; vertical scrolling stays native via touch-action: pan-y)
	// and with a two-finger trackpad swipe on desktop (horizontal wheel events).
	// A swipe suppresses the tap that ends it, like a long-press.
	function swipe(node: HTMLElement, handlers: { right: () => void; left: () => void }) {
		let h = handlers;
		let armed: '' | 'right' | 'left' = '';
		const threshold = () => Math.min(110, node.offsetWidth * 0.33);

		const render = (dx: number) => {
			node.style.transition = '';
			node.style.transform = `translateX(${dx}px)`;
			node.dataset.swipe = dx > 0 ? 'right' : 'left';
			const now: typeof armed = Math.abs(dx) >= threshold() ? (dx > 0 ? 'right' : 'left') : '';
			if (now && now !== armed) {
				try {
					navigator.vibrate?.(10);
				} catch {
					/* ignore */
				}
			}
			armed = now;
			if (armed) node.dataset.armed = '1';
			else delete node.dataset.armed;
		};
		const reset = () => {
			node.style.transition = 'transform 0.18s ease';
			node.style.transform = '';
			const scroller = node.closest('.list');
			if (scroller) scroller.scrollLeft = 0;
			delete node.dataset.swipe;
			delete node.dataset.armed;
			armed = '';
		};
		const commit = () => {
			lastLongPress = Date.now(); // swallow the tap/click that ends the swipe
			if (armed === 'right') h.right();
			else if (armed === 'left') h.left();
			reset();
		};

		// Touch.
		let pid = -1;
		let sx = 0;
		let sy = 0;
		let tracking = false;
		let horizontal = false;
		const down = (e: PointerEvent) => {
			if (e.pointerType !== 'touch') return;
			pid = e.pointerId;
			sx = e.clientX;
			sy = e.clientY;
			tracking = true;
			horizontal = false;
			armed = '';
		};
		const move = (e: PointerEvent) => {
			if (!tracking || e.pointerId !== pid) return;
			const mx = e.clientX - sx;
			const my = e.clientY - sy;
			if (!horizontal) {
				if (Math.abs(mx) < 12 && Math.abs(my) < 12) return;
				if (Math.abs(mx) < Math.abs(my) * 1.5) {
					tracking = false; // it's a vertical scroll: let the browser have it
					return;
				}
				horizontal = true;
			}
			render(mx);
		};
		const up = () => {
			if (!tracking) return;
			tracking = false;
			if (horizontal) commit();
			else reset();
		};
		const cancel = () => {
			tracking = false;
			reset();
		};

		// Trackpad (desktop): accumulate horizontal wheel deltas; the gesture ends
		// when the events (including momentum) stop.
		let wheelDx = 0;
		let wheeling = false;
		let wheelEnd: ReturnType<typeof setTimeout> | undefined;
		const wheel = (e: WheelEvent) => {
			if (!wheeling) {
				// Start only on a clearly horizontal, non-zoom gesture.
				if (e.ctrlKey || Math.abs(e.deltaX) < 2 || Math.abs(e.deltaX) <= Math.abs(e.deltaY)) {
					return;
				}
				wheeling = true;
				wheelDx = 0;
				armed = '';
			}
			e.preventDefault(); // no sideways scroll or browser back/forward swipe
			const limit = node.offsetWidth * 0.6;
			wheelDx = Math.max(-limit, Math.min(limit, wheelDx - e.deltaX));
			render(wheelDx);
			clearTimeout(wheelEnd);
			wheelEnd = setTimeout(() => {
				wheeling = false;
				commit();
			}, 140);
		};

		node.addEventListener('pointerdown', down);
		node.addEventListener('pointermove', move);
		node.addEventListener('pointerup', up);
		node.addEventListener('pointercancel', cancel);
		node.addEventListener('wheel', wheel, { passive: false });
		return {
			update(next: { right: () => void; left: () => void }) {
				h = next;
			},
			destroy() {
				clearTimeout(wheelEnd);
				node.removeEventListener('pointerdown', down);
				node.removeEventListener('pointermove', move);
				node.removeEventListener('pointerup', up);
				node.removeEventListener('pointercancel', cancel);
				node.removeEventListener('wheel', wheel);
			}
		};
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

	function thumbUrl(a: Article): string | undefined {
		return safeUrl(a.image_url) || safeUrl(sourceFavicon(a.source_id));
	}

	function hideImg(e: Event) {
		const el = e.currentTarget;
		if (el instanceof HTMLElement) el.style.display = 'none';
	}

	let showOnboarding = $state(false);
	let onboardingChecked = $state(false); // the install banner waits for this
	function onboarded(): boolean {
		try {
			return localStorage.getItem('onboarded') === '1';
		} catch {
			return false;
		}
	}
	function finishOnboarding() {
		try {
			localStorage.setItem('onboarded', '1');
		} catch {
			/* ignore */
		}
		showOnboarding = false;
		loadSidebar();
		loadArticles(true);
		loadInsights();
	}

	onMount(async () => {
		initOutbox();
		setFolderLookup((sourceId) => subs.find((x) => x.source.id === sourceId)?.folder_id ?? null);
		const snap = await readSnapshot();
		if (snap) {
			folders = snap.folders;
			subs = snap.subs;
			articles = withPending(snap.articles);
			cursor = snap.cursor;
			hasMore = !!snap.cursor;
			fromSnapshot = true;
		}
		// Push changes made offline first (bounded, so a slow network can't hold
		// the list back; anything still queued is overlaid on the fresh data).
		await Promise.race([syncOutbox(), new Promise((r) => setTimeout(r, 3000))]);
		await loadSidebar().catch(() => {});
		await loadArticles(true);
		loadInsights();
		// First run: no feeds yet and never onboarded → show the starter flow.
		if (!onboarded() && subs.length === 0) showOnboarding = true;
		onboardingChecked = true;
		syncOnOpen();
		warmOffline();
		if (isCurator)
			api
				.hiddenIds()
				.then((r) => (hiddenIds = new Set(r.ids)))
				.catch(() => {});
		window.addEventListener('offline', () => (offline = true));
		window.addEventListener('online', async () => {
			offline = false;
			await syncOutbox();
			loadArticles(true);
			warmOffline();
		});
		// iOS has no background sync: retry when the app comes back to the
		// foreground, and every minute while something is still queued.
		document.addEventListener('visibilitychange', () => {
			if (document.visibilityState === 'visible') syncOutbox();
		});
		outboxTimer = setInterval(() => {
			if (navigator.onLine) syncOutbox();
		}, 60000);
	});

	// Plan features (AI, server voice); resolved once per page load.
	const siteReady: Promise<void> = api
		.site()
		.then((c) => {
			const role = ($user?.role ?? 'free') as keyof typeof c.plan_limits;
			aiAllowed = c.plan_limits[role]?.ai_features ?? true;
			ttsServerAllowed = c.plan_limits[role]?.tts_server ?? false;
			radioAllowed = c.plan_limits[role]?.post_radio ?? false;
			radioPlan = {
				posts: c.plan_limits[role]?.radio_max_posts ?? null,
				minutes: c.plan_limits[role]?.radio_max_minutes ?? null
			};
		})
		.catch(() => {});

	let outboxTimer: ReturnType<typeof setInterval> | undefined;
	onDestroy(() => clearInterval(outboxTimer));

	// Feeds are fetched on demand while people use the app (the worker only
	// polls feeds of recently active users), so pull ours when the app opens.
	let pendingNew = $state(0);
	async function syncOnOpen() {
		try {
			const r = await api.sync();
			if (r.new_articles <= 0) return;
			subs = await api.listSources();
			const atTop = !listEl || listEl.scrollTop < 40;
			if (atTop && !openArticle) {
				await loadArticles(true);
				refreshMsg = `+${r.new_articles} ${$t('new_items')}`;
				setTimeout(() => (refreshMsg = ''), 5000);
			} else {
				pendingNew = r.new_articles; // don't yank the list while reading
			}
		} catch {
			/* offline or cooling down: nothing to do */
		}
	}

	// Keep saved articles (and their main images) available offline: the
	// service worker stores this response and the images we hand it.
	async function warmOffline() {
		if (!navigator.onLine || !navigator.serviceWorker?.controller) return;
		try {
			const page = await api.listArticles({ saved: 'true', limit: '100', offline: '1' });
			const urls = new Set<string>();
			for (const a of page.items) {
				const thumb = safeUrl(a.image_url);
				if (thumb) urls.add(thumb);
				for (const m of (a.content_html ?? '').matchAll(/<img[^>]+src="([^"]+)"/g)) {
					const u = safeUrl(m[1]);
					if (u) urls.add(u);
					if (urls.size > 150) break;
				}
			}
			navigator.serviceWorker.controller.postMessage({ type: 'cache-images', urls: [...urls] });
			// Server-voice recordings of saved articles, if asked for in Settings.
			await siteReady;
			if ($speechPrefs.offlineAudio && ttsServerAllowed) warmAudio(page.items, audioOpts());
		} catch {
			/* best effort */
		}
	}

	async function showPending() {
		pendingNew = 0;
		scrollListTop();
		await loadArticles(true);
	}

	onDestroy(() => flushReadEvent());
</script>

<svelte:window
	onkeydown={onKey}
	onclick={(e) => {
		const el = e.target as Element | null;
		if (viewOpen && !el?.closest('.viewtrigger, .viewpop')) viewOpen = false;
		if (moreOpen && !el?.closest('.morebtn, .morepop')) moreOpen = false;
	}}
/>

{#if viewOpen}
	<div class="viewpop" role="menu" style="top: {viewPos.top}px; left: {viewPos.left}px">
		{#each VIEWS as v (v)}
			<button
				role="menuitemradio"
				aria-checked={view === v}
				class:active={view === v}
				onclick={() => {
					setView(v);
					viewOpen = false;
				}}
			>
				<span class="vico" aria-hidden="true">{VIEW_ICONS[v]}</span>
				{$t(`view_${v}` as 'view_list')}
				{#if view === v}<span class="vcheck">✓</span>{/if}
			</button>
		{/each}
	</div>
{/if}

<InstallPrompt hold={!onboardingChecked || showOnboarding} />
{#if showOnboarding}
	<Onboarding oncomplete={finishOnboarding} />
{/if}

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
				{#if aiAllowed}
					<button
						class:active={searchMode === 'ai'}
						onclick={() => {
							searchMode = 'ai';
							loadArticles(true);
						}}>✨ {$t('search_ai')}</button
					>
				{/if}
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
			{#if aiAllowed}
				<button
					class="nav"
					class:active={filter.kind === 'foryou'}
					onclick={() => setFilter({ kind: 'foryou' })}
				>
					✨ {$t('for_you')}
				</button>
			{/if}
		</nav>

		{#snippet feedRow(s: Subscription)}
			<li class:active={filter.kind === 'source' && filter.id === s.source.id} class:muted={s.muted}>
				<button class="feed" onclick={() => setFilter({ kind: 'source', id: s.source.id })}>
					{#if s.source.favicon_url}
						<img class="favicon" src={safeUrl(s.source.favicon_url)} alt="" loading="lazy" onerror={hideImg} />
					{:else}
						<span class="favicon dot"></span>
					{/if}
					<span class="ellipsis">{s.custom_title || s.source.title || s.source.feed_url}</span>
					{#if s.source.error_count >= 3}
						<span class="feedwarn" title={$t('feed_problem')} aria-label={$t('feed_problem')}>⚠</span>
					{/if}
					{#if s.muted}<span class="mutedicon" title={$t('muted')}>🔇</span>
					{:else if s.unread_count}<span class="badge">{s.unread_count}</span>{/if}
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
				<button class="x" title={s.muted ? $t('unmute') : $t('mute')} onclick={() => toggleMute(s)}>
					{s.muted ? '🔊' : '🔇'}
				</button>
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

	<main class="list" bind:this={listEl}>
		{#if fromSnapshot && loading}
			<div class="updating" role="progressbar" aria-label={$t('loading')}></div>
		{/if}
		{#if offline}
			<p class="offlinebanner">📴 {$t('offline_banner')}</p>
		{/if}
		{#if $pendingCount > 0}
			<p class="offlinebanner">
				⟳ {$pendingCount} {$t($pendingCount === 1 ? 'pending_sync_one' : 'pending_sync')}
			</p>
		{/if}
		{#if $user?.must_change_password}
			<a class="tempbanner" href="/settings#password">
				🔑 {$t('temp_password_banner')} <strong>{$t('change_it_now')} →</strong>
			</a>
		{/if}
		<header>
			<button
				class="hamburger"
				onclick={() => (sidebarOpen = !sidebarOpen)}
				aria-label={$t('menu')}
				title={$t('menu')}
			>☰</button>
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions, a11y_click_events_have_key_events -->
			<h2 class="htitle" onclick={scrollListTop} title={$t('back_to_top')}>
				{#if filter.kind === 'source'}{sourceName(filter.id)}
				{:else if filter.kind === 'folder'}{folderName(filter.id)}
				{:else}{$t(filter.kind)}{/if}
			</h2>
			<div class="actions labels-{$toolbarLabels}">
				{#if refreshMsg}<span class="refresh-msg muted">{refreshMsg}</span>{/if}
				{#if pendingNew > 0}
					<button class="newpill" onclick={showPending}>+{pendingNew} {$t('new_items')}</button>
				{/if}
				<button
					class="viewtrigger"
					class:active={viewOpen}
					onclick={toggleViewMenu}
					title={$t('view')}
					aria-haspopup="menu"
					aria-expanded={viewOpen}
				>
					<span class="ico" aria-hidden="true">▦</span><span class="lbl">{$t('view')}</span>
				</button>
				<button
					class:active={showTrending}
					onclick={toggleTrending}
					title="{$t('trending_bar')} — {showTrending ? $t('hide') : $t('show')}"
				>
					<span class="ico" aria-hidden="true">🔥</span><span class="lbl">{$t('trending_bar')}</span>
				</button>
				{#if radioAllowed && articles.length}
					<button onclick={startRadio} title={$t('post_radio_start')} aria-label={$t('post_radio_start')}>
						<span class="ico" aria-hidden="true">📻</span><span class="lbl">{$t('post_radio')}</span>
					</button>
				{/if}
				<button onclick={refresh} disabled={refreshing} title={$t('refresh')}>
					<span class="ico" class:spin={refreshing} aria-hidden="true">↻</span><span class="lbl">{$t('refresh')}</span>
				</button>
				<button class="markall" onclick={markAllRead} title={$t('mark_all_read')}>
					<span class="ico" aria-hidden="true">✓✓</span><span class="lbl">{$t('mark_all_read')}</span>
				</button>
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
						oncontextmenu={(e) => e.preventDefault()}
						use:longpress={() => markRead(a, !a.is_read)}
						use:swipe={{ right: () => markRead(a, !a.is_read), left: () => toggleSave(a) }}
						data-right={a.is_read ? $t('swipe_unread') : $t('swipe_read')}
						data-left={a.is_saved ? $t('swipe_unsave') : $t('swipe_save')}
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
						oncontextmenu={(e) => e.preventDefault()}
						use:longpress={() => markRead(a, !a.is_read)}
						use:swipe={{ right: () => markRead(a, !a.is_read), left: () => toggleSave(a) }}
						data-right={a.is_read ? $t('swipe_unread') : $t('swipe_read')}
						data-left={a.is_saved ? $t('swipe_unsave') : $t('swipe_save')}
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

		{#if loading && !fromSnapshot}<p class="muted center">{$t('loading')}</p>{/if}
		{#if hasMore}<div use:sentinel></div>{/if}
		<p class="hint muted">{$t('shortcuts')}</p>
	</main>

	{#if openArticle}
		{@const a = openArticle}
		<!-- The toolbar sits above the scrolling body, not sticky inside it: on iOS
		     a sticky bar in a fixed scroller stops repainting after a long scroll,
		     so taps work but the screen looks frozen until the next gesture. -->
		<article class="reader">
			<div class="reader-head">
				<button class="close" onclick={closeReader} aria-label="close">×</button>
				<div class="reader-actions labels-{$toolbarLabels}">
					{#snippet act(ico: string, lbl: string)}
						<span class="ico" aria-hidden="true">{ico}</span><span class="lbl">{lbl}</span>
					{/snippet}
					<button
						onclick={() => markRead(a, !a.is_read)}
						title={a.is_read ? $t('mark_unread') : $t('mark_read')}
						aria-label={a.is_read ? $t('mark_unread') : $t('mark_read')}
					>
						{@render act(a.is_read ? '↺' : '✓', a.is_read ? $t('mark_unread') : $t('mark_read'))}
					</button>
					<button
						class:active={a.is_saved}
						onclick={() => toggleSave(a)}
						title={a.is_saved ? $t('unsave') : $t('save')}
						aria-label={a.is_saved ? $t('unsave') : $t('save')}
					>
						{@render act('🔖', a.is_saved ? $t('unsave') : $t('save'))}
					</button>
					<button
						class:active={a.is_favorite}
						onclick={() => toggleFavorite(a)}
						title={a.is_favorite ? $t('unfavorite') : $t('favorite')}
						aria-label={a.is_favorite ? $t('unfavorite') : $t('favorite')}
					>
						{@render act(a.is_favorite ? '★' : '☆', a.is_favorite ? $t('unfavorite') : $t('favorite'))}
					</button>
					{#if canTranslate(a)}
						{@const trOn = showTr && tr?.id === a.id}
						{@const trLbl = trLoading ? $t('translating') : trOn ? $t('show_original') : $t('translate')}
						<button
							class:active={trOn}
							onclick={() => toggleTranslation(a)}
							disabled={trLoading}
							title={trLbl}
							aria-label={trLbl}
						>
							{@render act(trLoading ? '⏳' : trOn ? '📄' : '🌐', trLbl)}
						</button>
					{/if}
					<button
						class:active={listenOpen || $speechPrefs.autoRead}
						onclick={() => (listenOpen = !listenOpen)}
						title={$t('listen')}
						aria-label={$t('listen')}
					>
						{@render act('🔊', $t('listen'))}
					</button>
					{#if safeUrl(a.url)}
						{@const fOn = !!fullShown[a.id]}
						<button
							class="secondary"
							class:active={fOn}
							onclick={() => toggleFull(a)}
							disabled={fullBusy === a.id}
							title={fOn ? $t('show_excerpt') : $t('full_article')}
							aria-label={fOn ? $t('show_excerpt') : $t('full_article')}
						>
							{@render act(fullBusy === a.id ? '⏳' : '📰', fOn ? $t('show_excerpt') : $t('full_article'))}
						</button>
						<button class="secondary" onclick={() => shareArticle(a)} title={$t('share')} aria-label={$t('share')}>
							{@render act(copiedId === a.id ? '✓' : '📤', copiedId === a.id ? $t('link_copied') : $t('share'))}
						</button>
					{/if}
					{#if isCurator}
						{@const hid = hiddenIds.has(a.id)}
						<button
							class="secondary"
							class:active={hid}
							onclick={() => toggleHidden(a)}
							title={hid ? $t('show_in_trending') : $t('hide_from_trending')}
							aria-label={hid ? $t('show_in_trending') : $t('hide_from_trending')}
						>
							{@render act(hid ? '👁' : '🚫', hid ? $t('show_in_trending') : $t('hide_from_trending'))}
						</button>
					{/if}
					{#if safeUrl(a.url)}
						<a
							class="btn secondary"
							href={safeUrl(a.url)}
							target="_blank"
							rel="noopener noreferrer"
							onclick={() => openOriginal(a)}
							title={$t('open_original')}
							aria-label={$t('open_original')}
						>
							{@render act('🔗', $t('open_original'))}
						</a>
					{/if}
					<button class="morebtn" class:active={moreOpen} onclick={toggleMore} aria-label={$t('more')} aria-expanded={moreOpen}>
						<span aria-hidden="true">⋯</span>
					</button>
				</div>
				{#if moreOpen}
					<div class="morepop" role="menu" style="top: {morePos.top}px; right: {morePos.right}px">
						{#if safeUrl(a.url)}
							<button role="menuitem" onclick={() => toggleFull(a)} disabled={fullBusy === a.id}>
								{fullBusy === a.id ? '⏳' : '📰'}
								{fullShown[a.id] ? $t('show_excerpt') : $t('full_article')}
							</button>
							<button role="menuitem" onclick={() => shareArticle(a)}>
								📤 {copiedId === a.id ? $t('link_copied') : $t('share')}
							</button>
							<a
								role="menuitem"
								href={safeUrl(a.url)}
								target="_blank"
								rel="noopener noreferrer"
								onclick={() => {
									openOriginal(a);
									moreOpen = false;
								}}
							>
								🔗 {$t('open_original')}
							</a>
						{/if}
						{#if isCurator}
							<button
								role="menuitem"
								onclick={() => {
									toggleHidden(a);
									moreOpen = false;
								}}
							>
								{hiddenIds.has(a.id) ? `👁 ${$t('show_in_trending')}` : `🚫 ${$t('hide_from_trending')}`}
							</button>
						{/if}
					</div>
				{/if}
				{#if listenOpen || $speechPrefs.autoRead}
					<!-- Keyed by radio session too: starting the radio on the open post
					     restarts its player instead of leaving it idle after the jingle. -->
					{#key `${a.id}:${radio?.startedAt ?? ''}`}
						<ListenBar
							article={a}
							title={title(a)}
							sourceName={sourceName(a.source_id)}
							contentEl={readerContentEl}
							serverAllowed={ttsServerAllowed}
							autostart={$speechPrefs.autoRead}
							myLang={$speechPrefs.myLanguage && canTranslate(a) ? $locale : null}
							getTranslation={() => loadTranslation(a)}
							prepare={() => fullPending.get(a.id) ?? Promise.resolve()}
							onradio={radioAllowed && !radio ? startRadio : undefined}
							radio={radio && radio.queue[radio.pos]?.id === a.id
								? {
										position: radio.pos + 1,
										limit: Math.min(radio.limit ?? Infinity, radio.queue.length),
										url: radioUrls.get(a.id),
										onfinish: radioAdvance,
										onskip: radioAdvance,
										onstop: radioStop
									}
								: null}
						/>
					{/key}
				{/if}
			</div>
			<div class="reader-body" bind:this={readerEl}>
				<h1>{showTr && tr?.id === a.id && tr.title ? tr.title : title(a)}</h1>
				{#if llm?.id === a.id && llm.title}
					<p class="trtitle">🌐 {llm.title}</p>
				{/if}
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
				{#if a.ai_summary || aiAllowed}
					{@const gen = llm?.id === a.id ? llm : null}
					<div class="ai-summary" class:folded={!summaryOpen}>
						<div class="ai-summary-head">
							<button class="ai-summary-label" onclick={toggleSummary} aria-expanded={summaryOpen}>
								✨ {gen?.summary ? `${$t('ai_summary_llm')} · ${gen.model}` : $t('summary_label')}
								<span class="chev" aria-hidden="true">{summaryOpen ? '▾' : '▸'}</span>
							</button>
							<!-- Folded: the AI summary stays one tap away. -->
							{#if !summaryOpen && aiAllowed && !gen?.summary}
								<button class="llm-mini" onclick={() => generateLLM(a)} disabled={gen?.loading}>
									{gen?.loading ? `⏳ ${llmSecs} s` : `✨ ${$t('ai_generate_short')}`}
								</button>
							{/if}
						</div>
						{#if summaryOpen}
							{gen?.summary ?? a.ai_summary ?? ''}
						{/if}
						{#if summaryOpen && aiAllowed && !gen?.summary}
							<div class="llm-row">
								<button class="llm-btn" onclick={() => generateLLM(a)} disabled={gen?.loading}>
									{gen?.loading ? `${$t('ai_generating')} ${llmSecs} s` : $t('ai_generate')}
								</button>
								{#if gen?.error}<span class="llm-err">{gen.error}</span>{/if}
							</div>
						{/if}
					</div>
				{/if}
				{#if trError}<p class="muted small">{trError}</p>{/if}
				{#if showTr && tr?.id === a.id}
					<div class="content translated" bind:this={readerContentEl}>
						<p class="trnote">🌐 {$t('machine_translation')}</p>
						{#each tr.paragraphs as para, i (i)}<p>{para}</p>{/each}
					</div>
				{:else}
					{#if fullBusy === a.id}<p class="fullnote">⏳ {$t('full_loading')}</p>{/if}
					{#if fullMsg}<p class="muted small">{fullMsg}</p>{/if}
					{#if fullShown[a.id] && fullHtml.has(a.id)}
						<p class="fullnote">📰 {$t('full_note')}</p>
					{/if}
					<div class="content" use:embeds={`${a.id}:${fullShown[a.id] ? 'full' : 'feed'}`} bind:this={readerContentEl}>
						{@html safeHtml(fullShown[a.id] && fullHtml.get(a.id) ? fullHtml.get(a.id) : a.content_html || a.summary, a.url)}
					</div>
				{/if}
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
			</div>
		</article>
	{/if}
</div>

<style>
	.shell {
		display: grid;
		grid-template-columns: 260px minmax(320px, 1fr) minmax(0, 1.4fr);
		height: 100%; /* body's box, inside the safe areas */
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
		/* Long-press to mark read: don't select text or pop the callout. */
		user-select: none;
		-webkit-user-select: none;
		-webkit-touch-callout: none;
		touch-action: pan-y; /* vertical scroll native; horizontal = swipe */
		position: relative;
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
		overflow-wrap: anywhere;
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
		overflow-x: hidden; /* a swiped row must not scroll the list sideways */
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
	.htitle {
		cursor: pointer;
	}
	.offlinebanner {
		margin: 0.5rem 0.25rem 0;
		padding: 0.45rem 0.75rem;
		border-radius: var(--radius);
		background: var(--surface);
		border: 1px dashed var(--border);
		font-size: 0.85rem;
	}
	.fullnote {
		font-size: 0.78rem;
		color: var(--muted);
		border-left: 3px solid var(--border);
		padding-left: 0.5rem;
	}
	.trnote {
		font-size: 0.78rem;
		color: var(--muted);
		border-left: 3px solid var(--accent);
		padding-left: 0.5rem;
	}
	.content :global(video),
	.content :global(audio) {
		width: 100%;
		max-width: 100%;
	}
	.content :global(.embed) {
		margin: 1rem 0;
	}
	.content :global(.embed-play),
	.content :global(.embed iframe) {
		position: relative;
		display: block;
		width: 100%;
		aspect-ratio: 16 / 9;
		border: none;
		border-radius: 10px;
		padding: 0;
		overflow: hidden;
		background: #111;
		cursor: pointer;
	}
	.content :global(.embed-play img) {
		width: 100%;
		height: 100%;
		object-fit: cover;
		margin: 0;
		opacity: 0.85;
	}
	.content :global(.embed-icon) {
		position: absolute;
		inset: 0;
		margin: auto;
		width: 64px;
		height: 44px;
		border-radius: 12px;
		background: rgba(0, 0, 0, 0.7);
		color: #fff;
		font-size: 1.4rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.content :global(.embed-youtube .embed-icon) {
		background: #e62117;
	}
	.content :global(.embed-link) {
		display: inline-block;
		margin-top: 0.3rem;
		font-size: 0.8rem;
	}
	/* Thin bar while the cached snapshot is being refreshed. */
	.updating {
		position: sticky;
		top: 0;
		z-index: 5;
		height: 2px;
		margin-bottom: -2px;
		overflow: hidden;
	}
	.updating::after {
		content: '';
		display: block;
		width: 35%;
		height: 100%;
		background: var(--accent);
		animation: updating-slide 1.1s ease-in-out infinite;
	}
	@keyframes updating-slide {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(300%);
		}
	}
	.viewpop {
		position: fixed;
		z-index: 30;
		display: flex;
		flex-direction: column;
		width: 200px;
		padding: 0.3rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 8px 28px rgba(0, 0, 0, 0.25);
	}
	.viewpop button {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		border: none;
		background: none;
		text-align: left;
		padding: 0.5rem 0.6rem;
		border-radius: 7px;
		font-size: 0.9rem;
	}
	.viewpop button:hover,
	.viewpop button.active {
		background: var(--accent-soft);
	}
	.vico {
		width: 1.2rem;
		text-align: center;
	}
	.vcheck {
		margin-left: auto;
		color: var(--accent);
	}
	.newpill {
		flex: none;
		border-radius: 999px;
		background: var(--accent);
		border-color: var(--accent);
		color: #fff;
		font-size: 0.8rem;
		padding: 0.25rem 0.7rem;
	}
	/* A swiped row is clipped by its list (clip, unlike hidden, can't be
	   scrolled sideways even programmatically). */
	.grid,
	.list ul {
		overflow-x: clip;
	}
	/* Swipe hints travel with the row and appear in the gap it reveals. */
	:global([data-swipe]::before) {
		position: absolute;
		top: 50%;
		transform: translateY(-50%);
		padding: 0.3rem 0.65rem;
		border-radius: 999px;
		font-size: 0.8rem;
		font-weight: 600;
		white-space: nowrap;
		color: #fff;
		opacity: 0.45;
		pointer-events: none;
	}
	:global([data-swipe='right']::before) {
		content: attr(data-right);
		right: calc(100% + 12px);
		background: var(--accent);
	}
	:global([data-swipe='left']::before) {
		content: attr(data-left);
		left: calc(100% + 12px);
		background: #d97706;
	}
	:global([data-armed='1']::before) {
		opacity: 1;
	}
	.feeds li.muted .feed {
		opacity: 0.55;
	}
	.mutedicon {
		flex: none;
		font-size: 0.75rem;
	}
	.feedwarn {
		flex: none;
		color: var(--danger);
		font-size: 0.8rem;
	}
	.tempbanner {
		display: block;
		margin: 0.5rem 0.25rem 0;
		padding: 0.5rem 0.75rem;
		border-radius: var(--radius);
		background: var(--accent-soft);
		border: 1px solid var(--accent);
		font-size: 0.85rem;
		color: inherit;
		text-decoration: none;
	}
	/* Toolbar buttons pair an icon with a label; the `labels-*` class on
	   .actions decides which parts show (icon+text builds visual memory so the
	   mobile icon-only mode stays legible). */
	.actions button {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.actions.labels-icons .lbl {
		display: none;
	}
	.actions.labels-text .ico {
		display: none;
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
		/* Long-press to mark read: don't select text or pop the callout. */
		user-select: none;
		-webkit-user-select: none;
		-webkit-touch-callout: none;
		touch-action: pan-y; /* vertical scroll native; horizontal = swipe */
		position: relative;
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
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}
	.reader-head {
		flex: none;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.4rem;
		position: relative;
		z-index: 4;
		background: var(--bg);
		padding: 1.25rem 1.5rem 0.5rem;
	}
	.reader-body {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		overscroll-behavior: contain;
		padding: 0 1.5rem 3rem;
	}
	.morebtn {
		display: none;
	}
	.morepop {
		position: fixed;
		z-index: 30;
		display: flex;
		flex-direction: column;
		min-width: 210px;
		padding: 0.3rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 8px 28px rgba(0, 0, 0, 0.25);
	}
	.morepop button,
	.morepop a {
		border: none;
		background: none;
		text-align: left;
		padding: 0.55rem 0.6rem;
		border-radius: 7px;
		color: var(--text);
		font-size: 0.95rem;
	}
	.morepop button:hover,
	.morepop a:hover {
		background: var(--accent-soft);
	}
	.ai-summary-label .chev {
		margin-left: auto;
	}
	.ai-summary.folded {
		padding-top: 0.45rem;
		padding-bottom: 0.45rem;
	}
	/* Same icon/text setting as the toolbar (Settings > Appearance). */
	.reader-actions button,
	.reader-actions .btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		white-space: nowrap;
	}
	.reader-actions.labels-icons .lbl {
		display: none;
	}
	.reader-actions.labels-text .ico {
		display: none;
	}
	.reader-actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		flex: 1 1 0;
		min-width: 0;
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
	.trtitle {
		margin: -0.25rem 0 0.5rem;
		color: var(--muted);
		font-size: 0.95rem;
	}
	.llm-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-top: 0.5rem;
	}
	.llm-btn {
		font-size: 0.82rem;
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		border-color: var(--accent);
		color: var(--accent);
		background: transparent;
	}
	.llm-err {
		font-size: 0.8rem;
		color: var(--danger);
	}
	/* The label doubles as the fold/unfold button. */
	.ai-summary-label {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex: 1;
		min-width: 0;
		background: none;
		border: none;
		padding: 0;
		text-align: left;
		cursor: pointer;
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--accent);
		margin-bottom: 0.25rem;
	}
	.ai-summary-head {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.llm-mini {
		flex: none;
		font-size: 0.75rem;
		padding: 0.15rem 0.55rem;
		border-radius: 999px;
		border-color: var(--accent);
		color: var(--accent);
		background: none;
	}
	.ai-summary.folded .ai-summary-label {
		margin-bottom: 0;
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
			padding-top: env(safe-area-inset-top);
			padding-bottom: env(safe-area-inset-bottom);
			width: min(84vw, 320px);
			z-index: 20;
			transform: translateX(-100%);
			transition: transform 0.2s ease;
			box-shadow: 0 0 24px rgba(0, 0, 0, 0.25);
		}
		.sidebar.open {
			transform: translateX(0);
		}
		/* The drawer only scrolls vertically: nothing inside may pan it
		   sideways (iOS lets wide rows/selects drag the whole panel). */
		.sidebar {
			overflow-x: hidden;
			overscroll-behavior: contain;
			touch-action: pan-y;
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
		/* Auto mode: icon-only on narrow screens (labels-both/text still win). */
		.actions.labels-auto .lbl {
			display: none;
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
		/* Cards/masonry on phones: two narrow columns can't fit "image left,
		   text right", so each card stacks image on top, text below. */
		.grid:not(.cardlist) .acard {
			flex-direction: column;
			gap: 0.4rem;
			padding: 0.45rem;
		}
		.grid:not(.cardlist) .thumb {
			width: 100%;
			height: auto;
			aspect-ratio: 16 / 10;
		}
		.grid:not(.cardlist) .atitle {
			font-size: 0.9rem;
			line-height: 1.25;
			display: -webkit-box;
			-webkit-line-clamp: 4;
			line-clamp: 4;
			-webkit-box-orient: vertical;
			overflow: hidden;
		}
		.grid:not(.cardlist) .excerpt {
			font-size: 0.8rem;
			-webkit-line-clamp: 3;
			line-clamp: 3;
		}
		.grid:not(.cardlist) .meta {
			flex-wrap: wrap;
			font-size: 0.72rem;
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
			/* Toolbar below the status bar; text scrolls down to the home bar. */
			padding: env(safe-area-inset-top) env(safe-area-inset-right) 0 env(safe-area-inset-left);
		}
		/* Action bar must not exceed the right edge: wrap onto more rows and use
		   compact buttons instead of spilling off-screen. */
		.reader-head {
			flex-wrap: wrap;
			gap: 0.4rem;
			padding: 1rem 1rem 0.5rem;
		}
		.reader-body {
			padding: 0 1rem calc(3rem + env(safe-area-inset-bottom));
			/* No sideways scroll: content is clipped to the viewport so vertical
			   scrolling can't wobble the page left-right ("flan"). */
			overflow-x: hidden;
		}
		.reader-actions {
			flex-wrap: wrap;
		}
		/* Auto: icons only on phones, icon + text on wider screens. */
		.reader-actions.labels-auto .lbl {
			display: none;
		}
		/* One row on phones: secondary actions go to the "⋯" menu. */
		.reader-actions .secondary {
			display: none !important;
		}
		.reader-actions .morebtn {
			display: inline-flex;
		}
		.reader-actions {
			flex-wrap: nowrap;
			gap: 0.3rem;
		}
		.reader-actions button,
		.reader-actions .btn {
			padding: 0.4rem 0.55rem;
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
