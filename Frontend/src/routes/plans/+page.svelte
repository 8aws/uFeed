<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { authed, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import type { PlanLimits, Role, SiteConfig } from '$lib/types';

	// Public page: what each option offers and where its limits are. The numbers
	// come from the server's live settings (admins can change them), so this
	// page never drifts from what the app enforces.
	const es = $derived($locale === 'es');
	let site = $state<SiteConfig | null>(null);
	let failed = $state(false);
	onMount(() => {
		api.site().then((s) => (site = s)).catch(() => (failed = true));
	});

	const ORDER: Role[] = ['guest', 'free', 'general', 'vip'];
	const roles = $derived(ORDER.filter((r) => site?.plan_limits?.[r]));
	const mine = $derived($authed && $user ? ($user.is_guest ? 'guest' : $user.role) : null);

	const n = (v: number | null | undefined) => (v === null || v === undefined ? (es ? 'sin límite' : 'unlimited') : String(v));
	const yes = '✓';
	const no = '—';

	function feeds(p: PlanLimits) {
		return p.max_feeds === null ? n(null) : String(p.max_feeds);
	}
	function refresh(p: PlanLimits) {
		if (p.refresh_cooldown_s <= 0) return es ? 'inmediata' : 'immediate';
		return `${es ? 'cada' : 'every'} ${Math.round(p.refresh_cooldown_s / 60)} min`;
	}
	function summaries(p: PlanLimits) {
		if (!p.ai_features || p.ai_summaries_per_day === 0) return no;
		return p.ai_summaries_per_day === null || p.ai_summaries_per_day === undefined
			? n(null)
			: `${p.ai_summaries_per_day} ${es ? 'al día' : 'a day'}`;
	}
	function radio(p: PlanLimits) {
		if (!p.post_radio) return no;
		const posts = `${p.radio_max_posts === null || p.radio_max_posts === undefined ? n(null) : p.radio_max_posts} posts`;
		const mins =
			p.radio_max_minutes === null || p.radio_max_minutes === undefined ? '' : `, ${p.radio_max_minutes} min`;
		return `${es ? 'hasta' : 'up to'} ${posts}${mins} ${es ? 'por sesión' : 'per session'}`;
	}
	function keys(p: PlanLimits) {
		return p.max_api_keys === 0 ? no : n(p.max_api_keys);
	}
	function priority(p: PlanLimits) {
		if (!p.ai_features) return no;
		return [es ? 'máxima' : 'highest', es ? 'alta' : 'high', es ? 'normal' : 'normal', es ? 'baja' : 'low'][
			Math.min(p.ai_priority ?? 2, 3)
		];
	}

	type Row = { label: string; cell: (r: Role, p: PlanLimits) => string };
	const rows = $derived<Row[]>([
		{
			label: es ? 'Registro' : 'Sign-up',
			cell: (r) => (r === 'guest' ? (es ? 'no hace falta' : 'not needed') : es ? 'correo y contraseña' : 'email and password')
		},
		{
			label: es ? 'Tus datos' : 'Your data',
			cell: (r) =>
				r === 'guest'
					? es
						? 'solo en este dispositivo'
						: 'only on this device'
					: es
						? 'en todos tus dispositivos'
						: 'on all your devices'
		},
		{ label: es ? 'Fuentes que puedes seguir' : 'Feeds you can follow', cell: (_, p) => feeds(p) },
		{ label: es ? 'Actualización manual' : 'Manual refresh', cell: (_, p) => refresh(p) },
		{
			label: es ? 'IA: traducción, «Para ti» y similares' : 'AI: translation, “For you” and similar',
			cell: (_, p) => (p.ai_features ? yes : no)
		},
		{ label: es ? 'Resúmenes IA nuevos' : 'New AI summaries', cell: (_, p) => summaries(p) },
		{ label: es ? 'Voz neuronal del servidor' : 'Server neural voice', cell: (_, p) => (p.tts_server ? yes : no) },
		{ label: es ? 'Post radio' : 'Post radio', cell: (_, p) => radio(p) },
		{ label: es ? 'Claves de API' : 'API keys', cell: (_, p) => keys(p) },
		{ label: es ? 'Prioridad en la cola de IA' : 'AI queue priority', cell: (_, p) => priority(p) }
	]);
</script>

<svelte:head><title>{es ? 'Planes y límites' : 'Plans and limits'} · uFeed</title></svelte:head>

<div class="page">
	<nav>
		<a href={$authed ? '/settings' : '/login'}>← uFeed</a>
		<span class="langs">
			<button class:active={$locale === 'es'} onclick={() => setLocale('es')}>ES</button>
			<button class:active={$locale === 'en'} onclick={() => setLocale('en')}>EN</button>
		</span>
	</nav>

	<h1>{es ? 'Planes y límites' : 'Plans and limits'}</h1>
	<p class="lead">
		{es
			? 'uFeed se puede usar sin cuenta. Crear una cuenta (gratis) guarda tus datos en todos tus dispositivos y activa la IA; los planes General y VIP amplían los límites.'
			: 'You can use uFeed without an account. Creating a (free) account keeps your data on all your devices and turns on AI; the General and VIP plans raise the limits.'}
	</p>

	{#if failed}
		<p class="muted">{es ? 'No se han podido cargar los planes. Inténtalo de nuevo más tarde.' : 'The plans could not be loaded. Try again later.'}</p>
	{:else if !site}
		<p class="muted">…</p>
	{:else}
		<div class="scroll">
			<table>
				<thead>
					<tr>
						<th></th>
						{#each roles as r (r)}
							<th class:mine={mine === r}>
								{$t(`role_${r}` as 'role_free')}
								{#if mine === r}<small>{es ? 'tu plan' : 'your plan'}</small>{/if}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each rows as row (row.label)}
						<tr>
							<th scope="row">{row.label}</th>
							{#each roles as r (r)}
								<td class:mine={mine === r} class:off={row.cell(r, site.plan_limits[r]) === no}>
									{row.cell(r, site.plan_limits[r])}
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<h2>{es ? 'En todos los planes' : 'In every plan'}</h2>
	<p>
		{es
			? 'Lectura de artículos completos, carpetas, filtros y fuentes silenciadas, guardados y favoritos, voz del dispositivo, tamaños de letra y tipografía accesible, importar y exportar OPML, y borrar tus datos cuando quieras.'
			: 'Full-article reading, folders, filters and muted sources, saved and favourites, the device voice, text sizes and accessible font, OPML import and export, and deleting your data whenever you want.'}
	</p>

	<h2>{es ? 'Cómo se consigue cada plan' : 'How you get each plan'}</h2>
	<ul>
		<li>
			<strong>{$t('role_guest')}:</strong>
			{es
				? 'toca «Continuar sin cuenta» en la app. Es un perfil anónimo, sin correo ni contraseña, que se borra tras 30 días sin usarlo. Más adelante puedes crear una cuenta y conservar tus fuentes y guardados.'
				: 'tap “Continue without an account” in the app. It is an anonymous profile, with no email or password, deleted after 30 days unused. Later you can create an account and keep your feeds and saved articles.'}
		</li>
		<li>
			<strong>{$t('role_free')}:</strong>
			{es ? 'es el plan de toda cuenta nueva.' : 'every new account starts here.'}
		</li>
		<li>
			<strong>{$t('role_general')} / {$t('role_vip')}:</strong>
			{es
				? 'los asigna la administración de este servidor. Escríbenos desde Soporte si los necesitas.'
				: 'assigned by this server’s administrators. Write to us from Support if you need them.'}
		</li>
	</ul>
	<p class="small muted">
		{es
			? 'Los límites son los de este servidor y pueden cambiar. Las cuentas de Editor y Administrador (gestión del servidor) no tienen límites.'
			: 'The limits are this server’s and can change. Editor and Administrator accounts (server management) have no limits.'}
	</p>

	<p class="links">
		<a href="/privacy">{$t('privacy')}</a> · <a href="/support">{$t('support')}</a>
	</p>
</div>

<style>
	.page {
		max-width: 860px;
		margin: 0 auto;
		padding: 1.5rem 1.25rem 3rem;
		line-height: 1.6;
	}
	nav {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.langs {
		display: flex;
		gap: 0.3rem;
	}
	.langs button {
		padding: 0.2rem 0.55rem;
		font-size: 0.8rem;
	}
	.langs button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	h1 {
		margin: 1rem 0 0.5rem;
	}
	h2 {
		font-size: 1.05rem;
		margin: 1.75rem 0 0.4rem;
	}
	.lead {
		margin-bottom: 1.25rem;
	}
	.scroll {
		background: var(--surface);
		overflow-x: auto;
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		min-width: 560px;
		font-size: 0.92rem;
	}
	th,
	td {
		padding: 0.55rem 0.7rem;
		text-align: left;
		border-bottom: 1px solid var(--border);
		vertical-align: top;
	}
	tbody tr:last-child th,
	tbody tr:last-child td {
		border-bottom: 0;
	}
	thead th {
		white-space: nowrap;
	}
	thead small {
		display: block;
		font-weight: 400;
		color: var(--accent);
		font-size: 0.72rem;
	}
	tbody th,
	thead th:first-child {
		position: sticky;
		left: 0;
		background: var(--surface);
		z-index: 1;
	}
	tbody th {
		font-weight: 600;
		min-width: 9rem;
	}
	td.off {
		color: var(--muted);
	}
	.mine {
		background: var(--accent-soft, rgba(37, 99, 235, 0.08));
	}
	ul {
		padding-left: 1.2rem;
	}
	.links {
		margin-top: 2rem;
		font-size: 0.9rem;
	}
</style>
