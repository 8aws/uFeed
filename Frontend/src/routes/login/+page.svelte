<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { setTokens, user } from '$lib/auth';
	import { setLocale, t } from '$lib/i18n';

	let mode = $state<'login' | 'register'>('login');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		busy = true;
		try {
			if (mode === 'login') {
				const tokens = await api.login(email, password);
				setTokens(tokens.access_token, tokens.refresh_token);
			} else {
				const res = await api.register(email, password);
				setTokens(res.tokens.access_token, res.tokens.refresh_token);
				user.set(res.user);
				setLocale(res.user.locale);
			}
			await goto('/');
		} catch {
			error = mode === 'login' ? $t('login_failed') : $t('register_failed');
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
	button.link {
		border: none;
		background: none;
		color: var(--accent);
		padding: 0;
		display: inline;
	}
</style>
