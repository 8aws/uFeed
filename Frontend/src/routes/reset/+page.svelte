<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api';
	import { setTokens } from '$lib/auth';
	import { t } from '$lib/i18n';

	// Opened from the emailed link: /reset?token=…
	let token = $state('');
	let password = $state('');
	let again = $state('');
	let error = $state('');
	let busy = $state(false);

	onMount(() => {
		token = new URLSearchParams(location.search).get('token') ?? '';
		if (!token) error = $t('reset_invalid');
	});

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (password !== again) {
			error = $t('password_mismatch');
			return;
		}
		busy = true;
		try {
			const tokens = await api.resetPassword(token, password);
			setTokens(tokens.access_token, tokens.refresh_token);
			await goto('/');
		} catch (err) {
			error = err instanceof ApiError && err.code === 'invalid_reset' ? $t('reset_invalid') : $t('reset_failed');
		} finally {
			busy = false;
		}
	}
</script>

<div class="wrap">
	<form class="card" onsubmit={submit}>
		<div class="brand">
			<img src="/logo.png" alt="" width="48" height="48" />
			<h1>{$t('app_name')}</h1>
		</div>
		<p class="muted">{$t('reset_title')}</p>
		<label>
			{$t('new_password')}
			<input type="password" bind:value={password} required minlength="8" autocomplete="new-password" />
		</label>
		<label>
			{$t('confirm_password')}
			<input type="password" bind:value={again} required minlength="8" autocomplete="new-password" />
		</label>
		{#if error}<p class="err">{error}</p>{/if}
		<button class="primary" type="submit" disabled={busy || !token}>{$t('change_password')}</button>
		<p class="muted switch"><a href="/login">← {$t('login')}</a></p>
	</form>
</div>

<style>
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
	p {
		margin: 0;
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
		font-size: 0.9rem;
	}
	.switch {
		text-align: center;
		font-size: 0.85rem;
	}
</style>
