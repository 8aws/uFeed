<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { setTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import type { Locale } from '$lib/types';

	let mode = $state<'login' | 'register'>('login');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);
	// An explicit choice here is saved to the profile (on register it's sent
	// with the account; on login it overrides the stored preference).
	let langTouched = false;
	// Admins can close sign-ups; hide the register path when they do.
	let registrationOpen = $state(true);
	onMount(async () => {
		try {
			registrationOpen = (await api.site()).registration_open;
			if (!registrationOpen) mode = 'login';
		} catch {
			/* keep the default */
		}
	});

	function pickLang(value: Locale) {
		setLocale(value);
		langTouched = true;
	}

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		busy = true;
		try {
			if (mode === 'login') {
				const tokens = await api.login(email, password);
				setTokens(tokens.access_token, tokens.refresh_token);
				if (langTouched) await api.updateMe({ locale: $locale }).catch(() => {});
			} else {
				const res = await api.register(email, password, $locale);
				setTokens(res.tokens.access_token, res.tokens.refresh_token);
				user.set(res.user);
				setLocale(res.user.locale);
			}
			await goto('/');
		} catch (e) {
			const known = ['account_suspended', 'account_disabled', 'registration_banned'] as const;
			if (e instanceof ApiError && e.code === 'registration_closed') {
				registrationOpen = false;
				mode = 'login';
				error = $t('registration_closed');
			} else if (e instanceof ApiError && (known as readonly string[]).includes(e.code)) {
				error = $t(e.code as (typeof known)[number]);
			} else {
				error = mode === 'login' ? $t('login_failed') : $t('register_failed');
			}
		} finally {
			busy = false;
		}
	}
</script>

<div class="wrap">
	<form class="card" onsubmit={submit}>
		<div class="langsel" role="group" aria-label={$t('language')}>
			<button type="button" class:active={$locale === 'es'} onclick={() => pickLang('es')}>🇪🇸 Español</button>
			<button type="button" class:active={$locale === 'en'} onclick={() => pickLang('en')}>🇬🇧 English</button>
		</div>
		<div class="brand">
			<img src="/logo.png" alt="" width="48" height="48" />
			<h1>{$t('app_name')}</h1>
		</div>
		<label>
			{$t('email')}
			<input type="email" bind:value={email} required autocomplete="email" />
		</label>
		<label>
			{$t('password')}
			<input
				type="password"
				bind:value={password}
				required
				minlength="8"
				autocomplete="current-password"
			/>
		</label>
		{#if error}<p class="err">{error}</p>{/if}
		<button class="primary" type="submit" disabled={busy}>
			{mode === 'login' ? $t('login') : $t('register')}
		</button>
		{#if registrationOpen}
			<p class="muted switch">
				{mode === 'login' ? $t('need_account') : $t('have_account')}
				<button
					type="button"
					class="link"
					onclick={() => {
						mode = mode === 'login' ? 'register' : 'login';
						error = '';
					}}
				>
					{mode === 'login' ? $t('register') : $t('login')}
				</button>
			</p>
		{:else}
			<p class="muted switch">{$t('registration_closed')}</p>
		{/if}
		<p class="legal">
			<a href="/info">{$t('about_app')}</a> · <a href="/privacy">{$t('privacy')}</a> ·
			<a href="/support">{$t('support')}</a>
		</p>
	</form>
</div>

<style>
	.legal {
		margin: 0.5rem 0 0;
		text-align: center;
		font-size: 0.8rem;
	}
	.wrap {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 1rem;
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 2rem;
		width: 100%;
		max-width: 360px;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	h1 {
		margin: 0;
		text-align: center;
	}
	.brand {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.6rem;
	}
	.brand img {
		border-radius: 10px;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.err {
		color: var(--danger);
		margin: 0;
		font-size: 0.9rem;
	}
	.switch {
		text-align: center;
		font-size: 0.85rem;
	}
	.langsel {
		display: flex;
		justify-content: center;
		gap: 0.4rem;
	}
	.langsel button {
		border-radius: 999px;
		padding: 0.3rem 0.8rem;
		font-size: 0.85rem;
	}
	.langsel button.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	button.link {
		border: none;
		background: none;
		color: var(--accent);
		padding: 0;
		display: inline;
	}
</style>
