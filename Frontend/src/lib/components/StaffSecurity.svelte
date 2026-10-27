<script lang="ts">
	import { onMount } from 'svelte';
	import { api, ApiError, askStepUp, stepUpAsk } from '$lib/api';
	import { t } from '$lib/i18n';
	import type { TotpStatus } from '$lib/types';

	// "Two-step verification" card for editors and admins: state, new recovery
	// codes, and turning it off (to enrol a new phone).

	let status = $state<TotpStatus | null>(null);
	let mode = $state<'idle' | 'recovery' | 'off'>('idle');
	let code = $state('');
	let password = $state('');
	let error = $state('');
	let info = $state('');
	let codes = $state<string[]>([]);
	let busy = $state(false);

	async function load() {
		try {
			status = await api.totpStatus();
		} catch {
			status = null;
		}
	}
	onMount(load);
	// The code window closing (set up, or a new proof) can change what this shows.
	let wasOpen = false;
	$effect(() => {
		const open = !!$stepUpAsk;
		if (wasOpen && !open) load();
		wasOpen = open;
	});

	function fail(e: unknown) {
		if (e instanceof ApiError && e.code === 'invalid_code') error = $t('totp_invalid');
		else if (e instanceof ApiError && e.status === 429) error = $t('totp_too_many');
		else error = e instanceof Error ? e.message : String(e);
	}

	async function newCodes(ev: Event) {
		ev.preventDefault();
		busy = true;
		error = '';
		try {
			codes = (await api.totpRecoveryCodes(code)).recovery_codes;
			code = '';
			await load();
		} catch (e) {
			fail(e);
		} finally {
			busy = false;
		}
	}

	async function turnOff(ev: Event) {
		ev.preventDefault();
		busy = true;
		error = '';
		try {
			await api.totpDisable(code, password);
			code = password = '';
			mode = 'idle';
			info = $t('totp_turned_off');
			await load();
		} catch (e) {
			fail(e);
		} finally {
			busy = false;
		}
	}

	function open(next: 'recovery' | 'off') {
		mode = mode === next ? 'idle' : next;
		code = password = error = info = '';
		codes = [];
	}
</script>

{#if status}
	<section class="card">
		<h3>{$t('totp_card_title')}</h3>
		{#if !status.required}
			<p class="muted">{$t('totp_card_not_required')}</p>
		{/if}
		<p>
			<strong class:ok={status.enabled}>{status.enabled ? $t('totp_card_on') : $t('totp_card_off')}</strong>
			{#if status.enabled}
				· {status.recovery_left} {$t('totp_card_left')}
			{/if}
		</p>
		{#if info}<p class="muted">{info}</p>{/if}
		{#if status.enabled}
			<div class="row">
				<button type="button" class="ghost" onclick={() => open('recovery')}>{$t('totp_new_recovery')}</button>
				<button type="button" class="ghost" onclick={() => open('off')}>{$t('totp_turn_off')}</button>
			</div>
		{:else}
			<button type="button" onclick={() => askStepUp('enrol').then(load)}>{$t('totp_set_up')}</button>
		{/if}

		{#if mode === 'recovery'}
			{#if codes.length}
				<pre class="codes">{codes.join('\n')}</pre>
				<p class="muted">{$t('totp_recovery_intro')}</p>
			{:else}
				<form onsubmit={newCodes}>
					<label for="sec-code">{$t('totp_code')}</label>
					<input id="sec-code" bind:value={code} inputmode="text" autocomplete="one-time-code" maxlength="16" />
					{#if error}<p class="err">{error}</p>{/if}
					<button type="submit" disabled={busy || !code.trim()}>{$t('totp_new_recovery')}</button>
				</form>
			{/if}
		{:else if mode === 'off'}
			<form onsubmit={turnOff}>
				<p class="muted">{$t('totp_turn_off_intro')}</p>
				<label for="sec-code2">{$t('totp_code')}</label>
				<input id="sec-code2" bind:value={code} inputmode="text" autocomplete="one-time-code" maxlength="16" />
				<label for="sec-pw">{$t('totp_password')}</label>
				<input id="sec-pw" type="password" bind:value={password} autocomplete="current-password" />
				{#if error}<p class="err">{error}</p>{/if}
				<button type="submit" disabled={busy || !code.trim() || !password}>{$t('totp_turn_off')}</button>
			</form>
		{/if}
	</section>
{/if}

<style>
	.card {
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.8rem 1rem;
		margin: 0 0 1rem;
		background: var(--surface);
	}
	h3 {
		margin: 0 0 0.3rem;
		font-size: 1rem;
	}
	.muted {
		color: var(--muted);
		margin: 0.3rem 0;
	}
	.ok {
		color: #1e8e3e;
	}
	.row {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	label {
		display: block;
		font-weight: 600;
		margin: 0.6rem 0 0.2rem;
	}
	input {
		width: min(280px, 100%);
		box-sizing: border-box;
		padding: 0.45rem 0.55rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
	}
	button {
		margin-top: 0.6rem;
		padding: 0.45rem 0.8rem;
		border-radius: 8px;
		border: 1px solid transparent;
		background: var(--accent, #2563eb);
		color: #fff;
		cursor: pointer;
	}
	button.ghost {
		background: none;
		color: inherit;
		border-color: var(--border);
	}
	button:disabled {
		opacity: 0.5;
	}
	.err {
		color: #c0392b;
	}
	.codes {
		background: rgba(127, 127, 127, 0.12);
		border-radius: 8px;
		padding: 0.6rem 0.8rem;
		user-select: all;
	}
</style>
