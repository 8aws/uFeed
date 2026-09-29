<script lang="ts">
	import { onMount, type Snippet } from 'svelte';
	import { api } from '$lib/api';
	import { authed } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';

	// Shared frame of the public pages (privacy, support): readable without an
	// account, in both languages, with the instance's contact address.
	let { title, children }: { title: string; children: Snippet<[string]> } = $props();
	let contact = $state('');
	onMount(() => {
		api.site().then((c) => (contact = c.contact_email ?? '')).catch(() => {});
	});
</script>

<div class="page">
	<nav>
		<a href={$authed ? '/settings' : '/login'}>← uFeed</a>
		<span class="langs">
			<button class:active={$locale === 'es'} onclick={() => setLocale('es')}>ES</button>
			<button class:active={$locale === 'en'} onclick={() => setLocale('en')}>EN</button>
		</span>
	</nav>
	<h1>{title}</h1>
	{@render children(contact)}
	<p class="links">
		<a href="/privacy">{$t('privacy')}</a> · <a href="/support">{$t('support')}</a>
	</p>
</div>

<style>
	.page {
		max-width: 720px;
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
	.page :global(h2) {
		font-size: 1.05rem;
		margin: 1.5rem 0 0.4rem;
	}
	.page :global(ul) {
		padding-left: 1.2rem;
	}
	.links {
		margin-top: 2rem;
		font-size: 0.9rem;
	}
</style>
