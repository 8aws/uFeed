<script lang="ts">
	import { onMount } from 'svelte';
	import { t } from '$lib/i18n';

	interface BIPEvent extends Event {
		prompt: () => Promise<void>;
		userChoice: Promise<{ outcome: string }>;
	}

	// While `hold` is set (onboarding on screen) the banner waits: it would
	// cover the onboarding's buttons. It appears once onboarding is done.
	let { hold = false }: { hold?: boolean } = $props();
	let ready = $state(false);
	const show = $derived(ready && !hold);
	let isIOS = $state(false);
	let deferred: BIPEvent | null = null;

	function dismissed(): boolean {
		try {
			return localStorage.getItem('pwa_prompt_dismissed') === '1';
		} catch {
			return false;
		}
	}
	function remember() {
		try {
			localStorage.setItem('pwa_prompt_dismissed', '1');
		} catch {
			/* ignore */
		}
	}

	function standalone(): boolean {
		return (
			window.matchMedia?.('(display-mode: standalone)').matches ||
			// iOS Safari exposes navigator.standalone
			(navigator as unknown as { standalone?: boolean }).standalone === true
		);
	}

	onMount(() => {
		if (dismissed() || standalone()) return;

		const ua = navigator.userAgent || '';
		// iOS (incl. iPadOS reporting as Mac with touch) has no beforeinstallprompt.
		isIOS =
			/iphone|ipad|ipod/i.test(ua) ||
			(/Macintosh/.test(ua) && 'ontouchend' in document);

		const onBIP = (e: Event) => {
			e.preventDefault();
			deferred = e as BIPEvent;
			ready = true;
		};
		window.addEventListener('beforeinstallprompt', onBIP);
		window.addEventListener('appinstalled', () => {
			remember();
			ready = false;
		});

		// On iOS there's no event — offer the manual instructions after a beat.
		if (isIOS) {
			const id = setTimeout(() => (ready = true), 1500);
			return () => {
				clearTimeout(id);
				window.removeEventListener('beforeinstallprompt', onBIP);
			};
		}
		return () => window.removeEventListener('beforeinstallprompt', onBIP);
	});

	async function install() {
		if (!deferred) return;
		await deferred.prompt();
		await deferred.userChoice.catch(() => ({ outcome: 'dismissed' }));
		deferred = null;
		remember();
		ready = false;
	}

	function close() {
		remember();
		ready = false;
	}
</script>

{#if show}
	<div class="banner" role="dialog" aria-label={$t('install_title')}>
		<img class="logo" src="/logo.png" alt="" width="32" height="32" />
		<div class="text">
			<strong>{$t('install_title')}</strong>
			<span class="muted">{isIOS ? $t('install_ios') : $t('install_generic')}</span>
		</div>
		<div class="btns">
			{#if !isIOS}
				<button class="primary" onclick={install}>{$t('install_app')}</button>
			{/if}
			<button class="ghost" onclick={close}>{$t('later')}</button>
		</div>
	</div>
{/if}

<style>
	.banner {
		position: fixed;
		left: 50%;
		transform: translateX(-50%);
		bottom: max(1rem, env(safe-area-inset-bottom));
		z-index: 45;
		width: min(560px, calc(100% - 2rem));
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 0.9rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
	}
	.logo {
		border-radius: 8px;
		flex: none;
	}
	.text {
		display: flex;
		flex-direction: column;
		min-width: 0;
		line-height: 1.3;
		font-size: 0.85rem;
	}
	.text .muted {
		font-size: 0.8rem;
	}
	.btns {
		display: flex;
		gap: 0.4rem;
		margin-left: auto;
		flex: none;
	}
	.primary {
		background: var(--accent);
		color: #fff;
		border-color: var(--accent);
	}
</style>
