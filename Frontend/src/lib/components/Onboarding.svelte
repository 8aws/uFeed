<script lang="ts">
	import { api } from '$lib/api';
	import { locale, t } from '$lib/i18n';
	import { CATALOG, LANG_FLAG, fetchCatalog, type CatalogFeed, type CatalogSection, type FeedLang } from '$lib/catalog';
	import { onMount } from 'svelte';
	import { addCatalogFeed, ensureFolder } from '$lib/catalogActions';

	let { oncomplete }: { oncomplete: () => void } = $props();

	let step = $state<'welcome' | 'pick'>('welcome');
	let busy = $state(false);
	let progress = $state('');

	// Pre-select the first few sections' feeds in the user's language so a new
	// account gets readable content fast; the other language is one tap away.
	const userLang: FeedLang = $locale === 'es' ? 'es' : 'en';
	const defaults = (cat: CatalogSection[]) =>
		new Set(cat.slice(0, 3).flatMap((s) => s.feeds.filter((f) => f.lang === userLang).map((f) => f.url)));
	let catalog = $state<CatalogSection[]>(CATALOG);
	let selected = $state<Set<string>>(defaults(CATALOG));
	let touched = false;

	// Use the list editors curated on this server (falls back to the built-in one).
	onMount(async () => {
		const cat = await fetchCatalog();
		if (cat === catalog) return;
		catalog = cat;
		if (!touched) selected = defaults(cat);
	});

	// Within each section, list the user's language first.
	function ordered(feeds: CatalogFeed[]): CatalogFeed[] {
		return [...feeds].sort((a, b) => Number(b.lang === userLang) - Number(a.lang === userLang));
	}

	function langSelected(lang: FeedLang): boolean {
		return catalog.every((s) => s.feeds.filter((f) => f.lang === lang).every((f) => selected.has(f.url)));
	}

	function toggleLang(lang: FeedLang) {
		const next = new Set(selected);
		const on = !langSelected(lang);
		for (const s of catalog) {
			for (const f of s.feeds) {
				if (f.lang !== lang) continue;
				if (on) next.add(f.url);
				else next.delete(f.url);
			}
		}
		selected = next;
		touched = true;
	}

	function sectionName(s: CatalogSection): string {
		return $locale === 'es' ? s.name_es : s.name_en;
	}

	function toggleFeed(url: string) {
		const next = new Set(selected);
		if (next.has(url)) next.delete(url);
		else next.add(url);
		selected = next;
		touched = true;
	}

	function sectionState(s: CatalogSection): 'all' | 'some' | 'none' {
		const n = s.feeds.filter((f) => selected.has(f.url)).length;
		return n === 0 ? 'none' : n === s.feeds.length ? 'all' : 'some';
	}

	function toggleSection(s: CatalogSection) {
		const next = new Set(selected);
		const on = sectionState(s) !== 'all';
		for (const f of s.feeds) {
			if (on) next.add(f.url);
			else next.delete(f.url);
		}
		selected = next;
		touched = true;
	}

	async function finish() {
		if (busy) return;
		busy = true;
		try {
			const folders = await api.listFolders().catch(() => []);
			try {
				for (const s of catalog) {
					const feeds = s.feeds.filter((f) => selected.has(f.url));
					if (!feeds.length) continue;
					progress = sectionName(s);
					const folder = await ensureFolder(sectionName(s), folders);
					for (const f of feeds) await addCatalogFeed(f, folder?.id ?? null);
				}
			} catch {
				/* plan's feed limit reached: keep what was added */
			}
			// Kick off a first fetch so there's something to read immediately.
			try {
				await api.refresh();
			} catch {
				/* ignore */
			}
		} finally {
			busy = false;
			oncomplete();
		}
	}

	const TIPS = ['tip_add', 'tip_longpress', 'tip_views', 'tip_trending', 'tip_install'] as const;
</script>

<div class="overlay" role="dialog" aria-modal="true" aria-label="onboarding">
	<div class="card">
		{#if step === 'welcome'}
			<img class="logo" src="/logo.png" alt="" width="48" height="48" />
			<h1>{$t('onboarding_welcome_title')}</h1>
			<p class="lead">{$t('onboarding_welcome_body')}</p>
			<ul class="tips">
				{#each TIPS as tip (tip)}
					<li>{$t(tip)}</li>
				{/each}
			</ul>
			<div class="actions">
				<button class="ghost" onclick={oncomplete}>{$t('skip')}</button>
				<button class="primary" onclick={() => (step = 'pick')}>{$t('start')}</button>
			</div>
		{:else}
			<h1>{$t('onboarding_pick_title')}</h1>
			<p class="lead">{$t('onboarding_pick_hint')}</p>
			<div class="langbar">
				{#each ['es', 'en'] as const as lang (lang)}
					<button class="chip" class:on={langSelected(lang)} onclick={() => toggleLang(lang)}>
						{LANG_FLAG[lang]} {$t(lang === 'es' ? 'lang_es' : 'lang_en')}
					</button>
				{/each}
				<button class="chip" onclick={() => (selected = new Set())}>{$t('select_none')}</button>
			</div>
			<div class="sections">
				{#each catalog as s (s.id)}
					<div class="section">
						<button
							class="sechead"
							class:on={sectionState(s) !== 'none'}
							onclick={() => toggleSection(s)}
						>
							<span class="box" data-state={sectionState(s)} aria-hidden="true"></span>
							{sectionName(s)}
						</button>
						<div class="feeds">
							{#each ordered(s.feeds) as f (f.url)}
								<label class="feed">
									<input
										type="checkbox"
										checked={selected.has(f.url)}
										onchange={() => toggleFeed(f.url)}
									/>
									<span
										class="flag"
										title={$t(f.lang === 'es' ? 'lang_es' : 'lang_en')}
										aria-label={$t(f.lang === 'es' ? 'lang_es' : 'lang_en')}
									>{LANG_FLAG[f.lang]}</span>
									<span>{f.title}</span>
								</label>
							{/each}
						</div>
					</div>
				{/each}
			</div>
			<div class="actions">
				<span class="count muted">{selected.size} {$t('selected_count')}</span>
				<button class="ghost" onclick={oncomplete} disabled={busy}>{$t('skip')}</button>
				<button class="primary" onclick={finish} disabled={busy || selected.size === 0}>
					{busy ? `${$t('adding_feeds')} ${progress}` : $t('finish')}
				</button>
			</div>
		{/if}
	</div>
</div>

<style>
	/* Fixed in place: the dim backdrop can't be dragged, and the card only
	   scrolls vertically (on iOS it used to slide sideways). */
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 40;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		overflow: hidden;
		touch-action: none;
		overscroll-behavior: contain;
	}
	.card {
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 14px;
		width: min(640px, 100%);
		max-height: 90vh;
		max-height: 90dvh;
		max-width: 100%;
		overflow-y: auto;
		overflow-x: hidden;
		touch-action: pan-y;
		overscroll-behavior: contain;
		overflow-wrap: anywhere;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.logo {
		border-radius: 10px;
	}
	h1 {
		margin: 0;
		font-size: 1.3rem;
	}
	.lead {
		margin: 0;
		color: var(--muted);
	}
	.tips {
		margin: 0.25rem 0 0;
		padding-left: 1.1rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		line-height: 1.4;
	}
	.sections {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
		gap: 0.6rem;
		margin: 0.25rem 0;
	}
	.section {
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.5rem 0.65rem;
	}
	.sechead {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		font-weight: 600;
		background: none;
		border: none;
		padding: 0.15rem 0;
		cursor: pointer;
	}
	.sechead.on {
		color: var(--accent);
	}
	.box {
		width: 16px;
		height: 16px;
		border: 2px solid var(--border);
		border-radius: 4px;
		flex: none;
	}
	.box[data-state='all'] {
		background: var(--accent);
		border-color: var(--accent);
	}
	.box[data-state='some'] {
		background: var(--accent-soft);
		border-color: var(--accent);
	}
	.langbar {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.chip {
		border-radius: 999px;
		padding: 0.3rem 0.75rem;
		font-size: 0.85rem;
	}
	.chip.on {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	.flag {
		flex: none;
		font-size: 1rem;
		line-height: 1;
	}
	.feeds {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-top: 0.35rem;
	}
	.feed {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.85rem;
		cursor: pointer;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		justify-content: flex-end;
		margin-top: 0.5rem;
		position: sticky;
		bottom: 0;
		background: var(--bg);
		padding-top: 0.5rem;
	}
	.count {
		margin-right: auto;
		font-size: 0.85rem;
	}
	.primary {
		background: var(--accent);
		color: #fff;
		border-color: var(--accent);
	}
</style>
