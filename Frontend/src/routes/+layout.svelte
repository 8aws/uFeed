<script lang="ts">
	import '../app.css';
	// Only downloaded when Accessibility > Font selects it.
	import '@fontsource/atkinson-hyperlegible/400.css';
	import '@fontsource/atkinson-hyperlegible/700.css';
	import '$lib/prefs'; // applies the display preferences (text size, font)
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { api } from '$lib/api';
	import { authed, user } from '$lib/auth';
	import { get } from 'svelte/store';
	import { setLocale } from '$lib/i18n';

	let { children } = $props();
	let ready = $state(false);

	async function refreshMe() {
		try {
			const me = await api.me();
			user.set(me);
			setLocale(me.locale);
		} catch {
			/* token invalid; guard will send to /login */
		}
	}

	onMount(async () => {
		const cached = get(user);
		if ($authed && cached) {
			// Paint immediately with the last known profile; refresh behind it.
			setLocale(cached.locale);
			ready = true;
			refreshMe();
		} else {
			if ($authed) await refreshMe();
			ready = true;
		}
	});

	// Fade out the boot splash from app.html once the interface is up.
	$effect(() => {
		if (!ready) return;
		const boot = document.getElementById('boot');
		if (!boot) return;
		boot.classList.add('gone');
		setTimeout(() => boot.remove(), 300);
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
