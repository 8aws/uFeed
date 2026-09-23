<script lang="ts">
	import { api } from '$lib/api';
	import { locale, t } from '$lib/i18n';
	import { CATALOG } from '$lib/catalog';

	let { oncomplete }: { oncomplete: () => void } = $props();

	let step = $state<'welcome' | 'pick'>('welcome');
	let busy = $state(false);
	let progress = $state('');

	// Pre-select the first few sections' feeds so a new user gets content fast.
	const preselected = new Set(CATALOG.slice(0, 3).flatMap((s) => s.feeds.map((f) => f.url)));
	let selected = $state<Set<string>>(new Set(preselected));

	function sectionName(s: (typeof CATALOG)[number]): string {
		return $locale === 'es' ? s.name_es : s.name_en;
	}

	function toggleFeed(url: string) {
		const next = new Set(selected);
		if (next.has(url)) next.delete(url);
		else next.add(url);
		selected = next;
	}

	function sectionState(s: (typeof CATALOG)[number]): 'all' | 'some' | 'none' {
		const n = s.feeds.filter((f) => selected.has(f.url)).length;
		return n === 0 ? 'none' : n === s.feeds.length ? 'all' : 'some';
	}

	function toggleSection(s: (typeof CATALOG)[number]) {
		const next = new Set(selected);
		const on = sectionState(s) !== 'all';
		for (const f of s.feeds) {
			if (on) next.add(f.url);
			else next.delete(f.url);
		}
		selected = next;
	}

	async function finish() {
		if (busy) return;
		busy = true;
		try {
			for (const s of CATALOG) {
				const feeds = s.feeds.filter((f) => selected.has(f.url));
				if (!feeds.length) continue;
				progress = sectionName(s);
				let folderId: string | null = null;
				try {
					folderId = (await api.createFolder(sectionName(s))).id;
				} catch {
					folderId = null; // fall back to top level
				}
				for (const f of feeds) {
					try {
						await api.subscribe(f.url, folderId);
					} catch {
						/* skip feeds that fail to resolve */
					}
				}
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
			<div class="sections">
				{#each CATALOG as s (s.id)}
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
							{#each s.feeds as f (f.url)}
								<label class="feed">
									<input
										type="checkbox"
										checked={selected.has(f.url)}
										onchange={() => toggleFeed(f.url)}
									/>
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
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 40;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.card {
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 14px;
		width: min(640px, 100%);
		max-height: 90vh;
		overflow-y: auto;
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
