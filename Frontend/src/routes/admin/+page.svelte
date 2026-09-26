<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime } from '$lib/format';
	import type { AdminSettings, AdminUser, Maintenance, Role } from '$lib/types';

	let settings = $state<AdminSettings | null>(null);
	let maint = $state<Maintenance | null>(null);
	let purging = $state(false);
	let tempPw = $state<{ id: string; pw: string } | null>(null);
	const RETENTION_PRESETS = [30, 60, 90, 180, 365, 0];
	const retentionOptions = $derived(
		settings && !RETENTION_PRESETS.includes(settings.retention_days)
			? [...RETENTION_PRESETS, settings.retention_days]
			: RETENTION_PRESETS
	);

	function bytes(n: number): string {
		return n >= 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${(n / 1e6).toFixed(1)} MB`;
	}
	function stale(iso: string): boolean {
		return Date.now() - new Date(iso).getTime() > 36 * 3600 * 1000;
	}

	async function loadMaint() {
		try {
			maint = await api.adminMaintenance();
		} catch (e) {
			fail(e);
		}
	}

	async function setRetention(days: number) {
		await saveSettings({ retention_days: days });
		await loadMaint();
	}

	async function purgeNow() {
		purging = true;
		try {
			maint = await api.runRetention();
			saved();
		} catch (e) {
			fail(e);
		} finally {
			purging = false;
		}
	}

	async function resetPw(u: AdminUser) {
		if (!confirm($t('confirm_reset_password'))) return;
		try {
			const r = await api.adminResetPassword(u.id);
			tempPw = { id: u.id, pw: r.temporary_password };
		} catch (e) {
			fail(e);
		}
	}
	let users = $state<AdminUser[]>([]);
	let flash = $state('');
	let error = $state('');

	function roleName(r: Role): string {
		return $t(`role_${r}` as 'role_free');
	}
	function limit(secs: number): string {
		return secs > 0 ? `${Math.round(secs / 60)} min` : $t('immediate');
	}
	function saved() {
		flash = $t('saved_ok');
		setTimeout(() => (flash = ''), 1500);
	}
	function fail(e: unknown) {
		error = e instanceof ApiError ? e.message : '⚠';
		setTimeout(() => (error = ''), 4000);
	}

	async function load() {
		try {
			[settings, users, maint] = await Promise.all([
				api.adminSettings(),
				api.adminUsers(),
				api.adminMaintenance()
			]);
		} catch (e) {
			fail(e);
		}
	}

	async function saveSettings(body: {
		registration_open?: boolean;
		default_role?: Role;
		retention_days?: number;
	}) {
		try {
			settings = await api.updateAdminSettings(body);
			saved();
		} catch (e) {
			fail(e);
			await load();
		}
	}

	async function saveUser(u: AdminUser, body: { role?: Role; is_active?: boolean }) {
		try {
			const updated = await api.updateAdminUser(u.id, body);
			users = users.map((x) => (x.id === u.id ? updated : x));
			saved();
		} catch (e) {
			fail(e);
			await load();
		}
	}

	onMount(() => {
		if ($user && $user.role !== 'admin') {
			goto('/');
			return;
		}
		load();
	});
</script>

<div class="page">
	<a class="back" href="/settings">← {$t('settings')}</a>
	<h1>🛡 {$t('admin')}</h1>
	{#if flash}<p class="flash">✓ {flash}</p>{/if}
	{#if error}<p class="err">{error}</p>{/if}

	{#if settings}
		<section>
			<h2>{$t('registration')}</h2>
			<label class="check">
				<input
					type="checkbox"
					checked={settings.registration_open}
					onchange={(e) => saveSettings({ registration_open: e.currentTarget.checked })}
				/>
				{$t('registration_open_label')}
			</label>
			<label class="field">
				{$t('default_role')}
				<select
					value={settings.default_role}
					onchange={(e) => saveSettings({ default_role: e.currentTarget.value as Role })}
				>
					{#each settings.roles as r (r)}<option value={r}>{roleName(r)}</option>{/each}
				</select>
			</label>
		</section>

		<section>
			<h2>{$t('plans_limits')}</h2>
			<table>
				<tbody>
					{#each settings.roles as r (r)}
						<tr>
							<td>{roleName(r)}</td>
							<td class="muted">{$t('refresh_every')} {limit(settings.refresh_cooldown_s[r])}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</section>
	{/if}

	{#if settings && maint}
		<section>
			<h2>{$t('maintenance')}</h2>
			<div class="row">
				<label class="field inline">
					{$t('retention')}
					<select
						value={settings.retention_days}
						onchange={(e) => setRetention(Number(e.currentTarget.value))}
					>
						{#each retentionOptions as d (d)}
							<option value={d}>{d === 0 ? $t('forever') : `${d} ${$t('days')}`}</option>
						{/each}
					</select>
				</label>
				<button onclick={purgeNow} disabled={purging || settings.retention_days === 0}>
					{purging ? '…' : $t('run_now')}
				</button>
			</div>
			<p class="muted small">{$t('retention_hint')}</p>
			<ul class="facts">
				<li>{$t('db_size')}: <strong>{bytes(maint.db_size_bytes)}</strong> · {maint.articles} {$t('articles_count')}</li>
				{#if maint.last_purge}
					<li>
						{$t('last_purge')}: {relativeTime(maint.last_purge.at, $locale)} ·
						{maint.last_purge.deleted_articles} {$t('articles_count')} {$t('deleted')}
					</li>
				{/if}
			</ul>
		</section>

		<section>
			<h2>{$t('backups')}</h2>
			{#if maint.backups}
				{@const b = maint.backups}
				<ul class="facts">
					<li class:bad={!b.ok || stale(b.at)}>
						{b.ok ? '✓' : '✗'} {$t('last_backup')}: {relativeTime(b.at, $locale)}
						{#if b.ok}· {bytes(b.size_bytes)} · {b.local_count}/{b.keep} {$t('local_copies')}{/if}
						{#if b.error}· {b.error}{/if}
					</li>
					{#if stale(b.at)}<li class="bad">⚠ {$t('backup_stale')}</li>{/if}
					<li class:bad={b.mirror.enabled && !b.mirror.ok}>
						{$t('mirror')}:
						{#if !b.mirror.enabled}
							<span class="muted">{$t('mirror_off')}</span>
						{:else if b.mirror.ok}
							✓ {b.mirror.count}/{b.mirror.keep} · <code>{b.mirror.dir}</code>
						{:else}
							✗ {b.mirror.error}
						{/if}
					</li>
				</ul>
			{:else}
				<p class="muted">{$t('no_backup_info')}</p>
			{/if}
		</section>
	{/if}

	<section>
		<h2>{$t('users')} ({users.length})</h2>
		<ul class="users">
			{#each users as u (u.id)}
				{@const self = u.id === $user?.id}
				<li class:inactive={!u.is_active}>
					<div class="uinfo">
						<strong class="ellipsis">{u.display_name || u.email}</strong>
						{#if self}<span class="muted small">({$t('you')})</span>{/if}
						<span class="muted small ellipsis">
							{#if u.display_name}{u.email} · {/if}{relativeTime(u.created_at, $locale)} · {u.feeds}
							{$t('feeds_count')}
						</span>
					</div>
					<div class="uctl">
						<select
							value={u.role}
							disabled={self}
							onchange={(e) => saveUser(u, { role: e.currentTarget.value as Role })}
						>
							{#each settings?.roles ?? [] as r (r)}<option value={r}>{roleName(r)}</option>{/each}
						</select>
						<label class="check small">
							<input
								type="checkbox"
								checked={u.is_active}
								disabled={self}
								onchange={(e) => saveUser(u, { is_active: e.currentTarget.checked })}
							/>
							{$t('active')}
						</label>
						{#if !self}
							<button class="small-btn" onclick={() => resetPw(u)}>🔑 {$t('reset_password')}</button>
						{/if}
					</div>
				</li>
				{#if tempPw?.id === u.id}
					<li class="temp">
						<span>{$t('temp_password_once')}</span>
						<code class="secret">{tempPw.pw}</code>
						<button class="small-btn" onclick={() => navigator.clipboard?.writeText(tempPw!.pw)}>
							{$t('copy')}
						</button>
					</li>
				{/if}
			{/each}
		</ul>
	</section>
</div>

<style>
	.page {
		max-width: 720px;
		margin: 0 auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
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
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		font-size: 0.85rem;
		color: var(--muted);
		max-width: 260px;
	}
	.check {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.9rem;
		margin-bottom: 0.75rem;
	}
	.check.small {
		font-size: 0.8rem;
		margin: 0;
	}
	table {
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	td {
		padding: 0.25rem 1rem 0.25rem 0;
	}
	.users {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}
	.users li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.6rem 0;
		border-top: 1px solid var(--border);
	}
	.users li.inactive {
		opacity: 0.55;
	}
	.uinfo {
		display: flex;
		flex-direction: column;
		min-width: 0;
		gap: 0.1rem;
	}
	.uctl {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex: none;
	}
	.ellipsis {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.small {
		font-size: 0.78rem;
	}
	.row {
		display: flex;
		align-items: flex-end;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	.field.inline {
		margin: 0;
	}
	.facts {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		font-size: 0.88rem;
	}
	.facts .bad {
		color: var(--danger);
	}
	.facts code {
		font-size: 0.78rem;
	}
	.small-btn {
		padding: 0.25rem 0.6rem;
		font-size: 0.8rem;
	}
	.users li.temp {
		justify-content: flex-start;
		flex-wrap: wrap;
		gap: 0.5rem;
		border-top: none;
		padding-top: 0;
		font-size: 0.85rem;
	}
	.secret {
		user-select: all;
		-webkit-user-select: all;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		background: var(--accent-soft);
		border: 1px solid var(--accent);
		border-radius: 6px;
		padding: 0.2rem 0.5rem;
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
</style>
