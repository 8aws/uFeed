<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { api } from '$lib/api';
	import { authed, user } from '$lib/auth';
	import { setLocale } from '$lib/i18n';

	let { children } = $props();
	let ready = $state(false);

	onMount(async () => {
		if ($authed) {
			try {
				const me = await api.me();
				user.set(me);
				setLocale(me.locale);
			} catch {
				/* token invalid; guard will send to /login */
			}
		}
		ready = true;
	});

	// Route guard.
	$effect(() => {
		if (!ready) return;
		const path = $page.url.pathname;
		if (!$authed && path !== '/login') goto('/login');
		if ($authed && path === '/login') goto('/');
	});
</script>

{#if ready}
	{@render children()}
{/if}
