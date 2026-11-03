<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { locale, t } from '$lib/i18n';
	import type { Dict } from '$lib/i18n/en';
	import type { AuditEntry } from '$lib/types';

	// "Activity log": who did what to whom, newest first (admins only).

	const LIMIT = 25;
	const KINDS = ['user', 'settings', 'ban', 'maintenance', 'staff', 'curation'] as const;

	let items = $state<AuditEntry[]>([]);
	let total = $state(0);
	let offset = $state(0);
	let kind = $state('');
	let q = $state('');
	let busy = $state(false);
	let error = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;

	const pages = $derived(Math.max(1, Math.ceil(total / LIMIT)));
	const pageNo = $derived(Math.floor(offset / LIMIT));

	async function load() {
		busy = true;
		error = '';
		try {
			const page = await api.adminAudit({ kind, q: q.trim(), limit: LIMIT, offset });
			items = page.items;
			total = page.total;
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			busy = false;
		}
	}

	onMount(load);

	function refilter() {
		offset = 0;
		clearTimeout(timer);
		timer = setTimeout(load, 250);
	}

	function go(n: number) {
		offset = n * LIMIT;
		load();
	}

	function label(action: string): string {
		const key = `aud_${action.replace('.', '_')}` as keyof Dict;
		return $t(key);
	}

	function when(iso: string): string {
		return new Date(iso).toLocaleString($locale, { dateStyle: 'short', timeStyle: 'medium' });
	}

	/** "days: 7 · reason: spam" — the facts the entry carries, without code names. */
	function facts(e: AuditEntry): string {
		return Object.entries(e.detail)
			.map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
			.join(' · ');
	}
</script>

<section>
	<h2>{$t('aud_title')} ({total})</h2>
	<div class="filters">
		<select bind:value={kind} onchange={refilter} aria-label={$t('aud_title')}>
			<option value="">{$t('aud_all')}</option>
			{#each KINDS as k (k)}
				<option value={k}>{$t(`aud_k_${k}` as keyof Dict)}</option>
			{/each}
		</select>
		<input type="search" bind:value={q} oninput={refilter} placeholder={$t('aud_search')} />
	</div>
	{#if error}<p class="err">{error}</p>{/if}
	{#if !busy && items.length === 0 && !error}
		<p class="muted small">{$t('aud_none')}</p>
	{:else}
		<ul class="log" class:busy>
			{#each items as e (e.id)}
				<li>
					<span class="when">{when(e.created_at)}</span>
					<span class="what">
						<strong>{e.actor_email}</strong>
						{label(e.action)}
						{#if e.target_email}<strong>{e.target_email}</strong>{/if}
					</span>
					{#if facts(e) || e.ip}
						<span class="muted small">{facts(e)}{facts(e) && e.ip ? ' · ' : ''}{e.ip ?? ''}</span>
					{/if}
				</li>
			{/each}
		</ul>
		{#if pages > 1}
			<div class="pager">
				<button class="small-btn" disabled={pageNo === 0 || busy} onclick={() => go(pageNo - 1)}>← {$t('adm_prev')}</button>
				<span class="muted small">{$t('adm_page')} {pageNo + 1} / {pages}</span>
				<button class="small-btn" disabled={pageNo >= pages - 1 || busy} onclick={() => go(pageNo + 1)}>{$t('adm_next')} →</button>
			</div>
		{/if}
	{/if}
</section>

<style>
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
	.filters {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.6rem;
	}
	.filters input,
	.filters select {
		padding: 0.4rem 0.5rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
	}
	.filters input {
		flex: 1;
		min-width: 12rem;
	}
	.log {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.log.busy {
		opacity: 0.6;
	}
	.log li {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}
	.when {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.what {
		word-break: break-word;
	}
	.muted {
		color: var(--muted);
	}
	.small {
		font-size: 0.82rem;
	}
	.err {
		color: #c0392b;
	}
	.pager {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-top: 0.6rem;
	}
	.small-btn {
		padding: 0.3rem 0.6rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: none;
		color: inherit;
		cursor: pointer;
	}
	.small-btn:disabled {
		opacity: 0.5;
	}
</style>
