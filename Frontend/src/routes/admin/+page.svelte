<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime } from '$lib/format';
	import type { AdminSettings, AdminUser, Role } from '$lib/types';

	let settings = $state<AdminSettings | null>(null);
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
			[settings, users] = await Promise.all([api.adminSettings(), api.adminUsers()]);
		} catch (e) {
			fail(e);
		}
	}

	async function saveSettings(body: { registration_open?: boolean; default_role?: Role }) {
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
					</div>
				</li>
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
