<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/auth';
	import { locale, t } from '$lib/i18n';
	import { relativeTime } from '$lib/format';
	import type {
		AdminSettings,
		AdminUser,
		Ban,
		Maintenance,
		PlanLimits,
		Role
	} from '$lib/types';

	let settings = $state<AdminSettings | null>(null);
	let maint = $state<Maintenance | null>(null);
	let purging = $state(false);
	let tempPw = $state<{ id: string; pw: string } | null>(null);
	let bans = $state<Ban[]>([]);
	// Editable copy of the plan limits (minutes and blank = unlimited in the UI).
	type Draft = {
		refresh_min: number;
		max_feeds: string;
		max_api_keys: string;
		ai_features: boolean;
		tts_server: boolean;
	};
	let plansDraft = $state<Record<string, Draft>>({});
	let savingPlans = $state(false);

	function initDraft(plans: Record<string, PlanLimits>) {
		plansDraft = Object.fromEntries(
			Object.entries(plans).map(([role, p]) => [
				role,
				{
					refresh_min: Math.round(p.refresh_cooldown_s / 60),
					max_feeds: p.max_feeds === null ? '' : String(p.max_feeds),
					max_api_keys: p.max_api_keys === null ? '' : String(p.max_api_keys),
					ai_features: p.ai_features,
					tts_server: p.tts_server ?? false
				}
			])
		);
	}

	function num(v: string | number): number | null {
		const t = String(v).trim();
		if (t === '') return null;
		const n = Math.max(0, Math.floor(Number(t)));
		return Number.isFinite(n) ? n : null;
	}

	async function savePlans() {
		savingPlans = true;
		try {
			const body = Object.fromEntries(
				Object.entries(plansDraft).map(([role, d]) => [
					role,
					{
						refresh_cooldown_s: Math.max(0, Math.round(Number(d.refresh_min) || 0) * 60),
						max_feeds: num(d.max_feeds),
						max_api_keys: num(d.max_api_keys),
						ai_features: d.ai_features,
						tts_server: d.tts_server
					}
				])
			);
			settings = await api.updatePlans(body);
			initDraft(settings.plan_limits);
			saved();
		} catch (e) {
			fail(e);
		} finally {
			savingPlans = false;
		}
	}
	let banEmail = $state('');
	let banDays = $state(0); // 0 = permanent
	let cleaning = $state(false);
	const INACTIVITY_PRESETS = [90, 180, 365, 730, 0];

	function daysSince(iso: string | null): number {
		return iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86400000) : 0;
	}
	function fmtDate(iso: string): string {
		return new Date(iso).toLocaleDateString($locale);
	}
	// Days until an idle account is deactivated (stage 1), or null if exempt.
	function deactivatesIn(u: AdminUser): number | null {
		const lim = settings?.inactivity_days ?? 0;
		if (!lim || u.role === 'admin' || u.dormant_since) return null;
		return Math.max(0, lim - daysSince(u.last_activity_at));
	}
	// Days until a deactivated account is deleted (stage 2), or null.
	function deletesIn(u: AdminUser): number | null {
		const lim = settings?.dormant_delete_days ?? 0;
		if (!lim || !u.dormant_since) return null;
		return Math.max(0, lim - daysSince(u.dormant_since));
	}
	function suspended(u: AdminUser): boolean {
		return !!u.suspended_until && new Date(u.suspended_until).getTime() > Date.now();
	}

	async function moderate(u: AdminUser, action: string) {
		try {
			if (action === 'delete') {
				if (!confirm($t('confirm_delete_user'))) return;
				await api.deleteUser(u.id);
				users = users.filter((x) => x.id !== u.id);
			} else {
				let updated: AdminUser;
				if (action.startsWith('suspend:')) updated = await api.suspendUser(u.id, Number(action.slice(8)));
				else if (action === 'lift') updated = await api.unsuspendUser(u.id);
				else if (action === 'ban:perm') {
					if (!confirm($t('confirm_ban_permanent'))) return;
					updated = await api.banUser(u.id, null);
				} else if (action.startsWith('ban:')) updated = await api.banUser(u.id, Number(action.slice(4)));
				else if (action === 'unban') updated = await api.unbanUser(u.id);
				else if (action === 'reactivate') updated = await api.reactivateUser(u.id);
				else return;
				users = users.map((x) => (x.id === u.id ? updated : x));
			}
			bans = await api.listBans();
			saved();
		} catch (e) {
			fail(e);
			await load();
		}
	}

	async function addBan(e: SubmitEvent) {
		e.preventDefault();
		try {
			await api.createBan(banEmail.trim(), banDays === 0 ? null : banDays);
			banEmail = '';
			[bans, users] = await Promise.all([api.listBans(), api.adminUsers()]);
			saved();
		} catch (err) {
			fail(err);
		}
	}

	async function removeBan(b: Ban) {
		try {
			await api.deleteBan(b.id);
			[bans, users] = await Promise.all([api.listBans(), api.adminUsers()]);
			saved();
		} catch (e) {
			fail(e);
		}
	}

	async function setInactivity(days: number) {
		await saveSettings({ inactivity_days: days });
		await loadMaint();
	}

	async function cleanupInactive() {
		cleaning = true;
		try {
			maint = await api.runInactivity();
			users = await api.adminUsers();
			saved();
		} catch (e) {
			fail(e);
		} finally {
			cleaning = false;
		}
	}

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
			[settings, users, maint, bans] = await Promise.all([
				api.adminSettings(),
				api.adminUsers(),
				api.adminMaintenance(),
				api.listBans()
			]);
			if (settings) initDraft(settings.plan_limits);
		} catch (e) {
			fail(e);
		}
	}

	async function saveSettings(body: {
		registration_open?: boolean;
		default_role?: Role;
		retention_days?: number;
		inactivity_days?: number;
		dormant_delete_days?: number;
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

	onMount(async () => {
		// Check the live role (the cached profile may predate a role change).
		const me = await api.me().catch(() => null);
		if (me) user.set(me);
		if (me && me.role !== 'admin') {
			goto('/');
			return;
		}
		load();
	});
</script>

<div class="page">
	<a class="back" href="/settings">← {$t('settings')}</a>
	<h1>🛡 {$t('admin')}</h1>
	<a class="pill" href="/curation">✎ {$t('curation')} →</a>
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
			<p class="muted small">{$t('plans_hint')}</p>
			<div class="plans">
				{#each settings.roles as r (r)}
					{#if plansDraft[r]}
						<div class="plan">
							<strong>{roleName(r)}</strong>
							<label>
								{$t('refresh_minutes')}
								<input type="number" min="0" max="1440" bind:value={plansDraft[r].refresh_min} />
							</label>
							<label>
								{$t('max_feeds')}
								<input type="number" min="0" placeholder="∞" bind:value={plansDraft[r].max_feeds} />
							</label>
							<label>
								{$t('max_api_keys')}
								<input type="number" min="0" placeholder="∞" bind:value={plansDraft[r].max_api_keys} />
							</label>
							<label class="check small">
								<input type="checkbox" bind:checked={plansDraft[r].ai_features} />
								{$t('ai_features')}
							</label>
							<label class="check small">
								<input type="checkbox" bind:checked={plansDraft[r].tts_server} />
								🔊 {$t('tts_server_plan')}
							</label>
						</div>
					{/if}
				{/each}
			</div>
			<button class="spaced" onclick={savePlans} disabled={savingPlans}>
				{savingPlans ? '…' : $t('save_plans')}
			</button>
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
			<div class="row spaced">
				<label class="field inline">
					{$t('deactivate_after')}
					<select
						value={settings.inactivity_days}
						onchange={(e) => setInactivity(Number(e.currentTarget.value))}
					>
						{#each INACTIVITY_PRESETS.includes(settings.inactivity_days) ? INACTIVITY_PRESETS : [...INACTIVITY_PRESETS, settings.inactivity_days] as d (d)}
							<option value={d}>{d === 0 ? $t('never') : `${d} ${$t('days')}`}</option>
						{/each}
					</select>
				</label>
				<label class="field inline">
					{$t('delete_deactivated_after')}
					<select
						value={settings.dormant_delete_days}
						onchange={(e) => saveSettings({ dormant_delete_days: Number(e.currentTarget.value) })}
					>
						{#each [90, 180, 365, 0].includes(settings.dormant_delete_days) ? [90, 180, 365, 0] : [90, 180, 365, 0, settings.dormant_delete_days] as d (d)}
							<option value={d}>{d === 0 ? $t('never') : `${d} ${$t('days')}`}</option>
						{/each}
					</select>
				</label>
				<button onclick={cleanupInactive} disabled={cleaning || settings.inactivity_days === 0}>
					{cleaning ? '…' : $t('run_now')}
				</button>
			</div>
			<p class="muted small">{$t('inactivity_hint2')}</p>
			{#if maint.last_inactive_cleanup}
				<ul class="facts">
					<li>
						{$t('last_inactive_cleanup')}: {relativeTime(maint.last_inactive_cleanup.at, $locale)} ·
						{maint.last_inactive_cleanup.deactivated_users ?? 0} {$t('accounts_deactivated')} ·
						{maint.last_inactive_cleanup.deleted_users} {$t('accounts_deleted')}
					</li>
				</ul>
			{/if}
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
							✓ {b.mirror.count}/{b.mirror.keep} ·
							{b.mirror.encrypted ? `🔒 ${$t('mirror_encrypted')}` : `⚠ ${$t('mirror_plain')}`} ·
							<code>{b.mirror.dir}</code>
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
						<span class="badges small">
							{#if u.banned}
								<span class="badge bad">⛔ {$t('banned')} {u.ban_until ? `${$t('until')} ${fmtDate(u.ban_until)}` : `(${$t('permanent')})`}</span>
							{:else if suspended(u)}
								<span class="badge warn">⏸ {$t('suspended_until')} {fmtDate(u.suspended_until!)}</span>
							{/if}
							{#if u.dormant_since}
								<span class="badge warn">💤 {$t('dormant_since')} {fmtDate(u.dormant_since)}{#if deletesIn(u) !== null} · {$t('deletes_in')} {deletesIn(u)} {$t('days')}{/if}</span>
							{:else if !self && deactivatesIn(u) !== null && daysSince(u.last_activity_at) > 30}
								<span class="badge">💤 {$t('inactive_for')} {daysSince(u.last_activity_at)} {$t('days')} · {$t('deactivates_in')} {deactivatesIn(u)} {$t('days')}</span>
							{/if}
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
							<select
								class="actions-sel"
								value=""
								onchange={(e) => {
									const v = e.currentTarget.value;
									e.currentTarget.value = '';
									moderate(u, v);
								}}
							>
								<option value="" disabled>{$t('moderation')}…</option>
								{#if u.dormant_since}
									<option value="reactivate">▶ {$t('reactivate')}</option>
								{/if}
								{#if suspended(u)}
									<option value="lift">▶ {$t('lift_suspension')}</option>
								{:else}
									<option value="suspend:1">⏸ {$t('suspend')} 1 {$t('days')}</option>
									<option value="suspend:7">⏸ {$t('suspend')} 7 {$t('days')}</option>
									<option value="suspend:30">⏸ {$t('suspend')} 30 {$t('days')}</option>
								{/if}
								{#if u.banned}
									<option value="unban">✅ {$t('unban')}</option>
								{:else}
									<option value="ban:7">⛔ {$t('ban')} 7 {$t('days')}</option>
									<option value="ban:30">⛔ {$t('ban')} 30 {$t('days')}</option>
									<option value="ban:perm">⛔ {$t('ban')} ({$t('permanent')})</option>
								{/if}
								{#if u.role !== 'admin'}
									<option value="delete">🗑 {$t('delete_account')}</option>
								{/if}
							</select>
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

	<section>
		<h2>{$t('bans')} ({bans.length})</h2>
		<form class="row" onsubmit={addBan}>
			<input type="email" bind:value={banEmail} placeholder={$t('ban_email')} required />
			<select bind:value={banDays}>
				<option value={7}>7 {$t('days')}</option>
				<option value={30}>30 {$t('days')}</option>
				<option value={0}>{$t('permanent')}</option>
			</select>
			<button type="submit">⛔ {$t('add_ban')}</button>
		</form>
		{#if bans.length === 0}
			<p class="muted small">{$t('no_bans')}</p>
		{:else}
			<ul class="facts">
				{#each bans as b (b.id)}
					<li class="banrow">
						<span class="ellipsis">
							{b.email} — {b.until ? `${$t('until')} ${fmtDate(b.until)}` : $t('permanent')}
							{#if b.reason}<span class="muted">· {b.reason}</span>{/if}
						</span>
						<button class="small-btn" onclick={() => removeBan(b)}>{$t('unban')}</button>
					</li>
				{/each}
			</ul>
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
	.plans {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: 0.6rem;
		margin-top: 0.5rem;
	}
	.plan {
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.8rem;
	}
	.plan label:not(.check) {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		color: var(--muted);
	}
	.plan input[type='number'] {
		padding: 0.25rem 0.4rem;
	}
	.spaced {
		margin-top: 0.75rem;
	}
	.badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.badge {
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0 0.45rem;
	}
	.badge.bad {
		border-color: var(--danger);
		color: var(--danger);
	}
	.badge.warn {
		border-color: var(--accent);
		color: var(--accent);
	}
	.actions-sel {
		font-size: 0.8rem;
		max-width: 9rem;
	}
	.uctl {
		flex-wrap: wrap;
		justify-content: flex-end;
	}
	.banrow {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		min-width: 0;
	}
	/* Narrow screens: user controls wrap under the name instead of pushing
	   the page wider than the viewport. */
	@media (max-width: 640px) {
		.users li {
			flex-wrap: wrap;
		}
		.uctl {
			width: 100%;
			justify-content: flex-start;
		}
		.row input[type='email'] {
			flex: 1 1 100%;
		}
	}
	.pill {
		align-self: flex-start;
		font-size: 0.9rem;
		border: 1px solid var(--accent);
		border-radius: 999px;
		padding: 0.3rem 0.8rem;
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
