<script lang="ts">
	import { untrack } from 'svelte';
	import QRCode from 'qrcode';
	import { api, ApiError, stepUpAsk } from '$lib/api';
	import { setStepUp } from '$lib/auth';
	import { copyText } from '$lib/clipboard';
	import { t } from '$lib/i18n';
	import type { TotpSetup } from '$lib/types';

	// The one-time-code window for editors and admins. It opens when a curation or
	// administration request is refused for lack of a (fresh) code: it asks for the
	// code, or walks through the set-up the first time (QR, key as text, otpauth link,
	// recovery codes), then the request is sent again.

	let ask = $derived($stepUpAsk);
	let step = $state<'loading' | 'setup' | 'code' | 'recovery'>('loading');
	let setup = $state<TotpSetup | null>(null);
	let qr = $state('');
	let code = $state('');
	let error = $state('');
	let busy = $state(false);
	let recovery = $state<string[]>([]);
	let saved = $state(false);
	let copied = $state('');

	$effect(() => {
		const current = ask;
		if (!current) return;
		untrack(() => start(current.mode));
	});

	async function start(mode: 'enrol' | 'code' | 'fresh') {
		code = '';
		error = '';
		saved = false;
		recovery = [];
		if (mode !== 'enrol') {
			step = 'code';
			return;
		}
		step = 'loading';
		try {
			setup = await api.totpSetup();
			qr = await QRCode.toString(setup.otpauth_url, { type: 'svg', margin: 1, width: 192 });
			step = 'setup';
		} catch (e) {
			if (e instanceof ApiError && e.code === 'totp_already_enabled') {
				step = 'code'; // it was set up meanwhile (another tab)
			} else {
				error = e instanceof Error ? e.message : String(e);
				step = 'setup';
			}
		}
	}

	function fail(e: unknown) {
		if (e instanceof ApiError && e.code === 'invalid_code') error = $t('totp_invalid');
		else if (e instanceof ApiError && e.status === 429) error = $t('totp_too_many');
		else error = e instanceof Error ? e.message : String(e);
	}

	async function submit(ev: Event) {
		ev.preventDefault();
		if (!code.trim() || busy) return;
		busy = true;
		error = '';
		try {
			if (step === 'setup') {
				const r = await api.totpEnable(code);
				setStepUp(r.step_up_token);
				recovery = r.recovery_codes;
				step = 'recovery';
			} else {
				await api.totpVerify(code);
				ask?.done(true);
			}
		} catch (e) {
			fail(e);
		} finally {
			busy = false;
		}
	}

	async function copy(text: string, what: string) {
		// If copying is blocked the text is on screen to select.
		if (await copyText(text)) {
			copied = what;
			setTimeout(() => (copied = ''), 1500);
		}
	}

	function download() {
		const body = `uFeed\n${$t('totp_recovery_file')}\n\n${recovery.join('\n')}\n`;
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([body], { type: 'text/plain' }));
		a.download = 'ufeed-recovery-codes.txt';
		a.click();
		URL.revokeObjectURL(a.href);
	}

	function cancel() {
		// After the codes were issued the set-up is done: only "Done" closes it.
		if (step === 'recovery') return;
		ask?.done(false);
	}
</script>

{#if ask}
	<div class="back" role="presentation" onclick={cancel}>
		<div
			class="box"
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-label={$t('totp_title')}
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.key === 'Escape' && cancel()}
		>
			{#if step === 'loading'}
				<p class="muted">…</p>
			{:else if step === 'setup'}
				<h3>{$t('totp_setup_title')}</h3>
				<p class="muted">{$t('totp_setup_intro')}</p>
				{#if setup}
					<div class="qr" aria-label={$t('totp_qr')}>{@html qr}</div>
					<p class="small">{$t('totp_or_key')}</p>
					<div class="keyrow">
						<code class="key">{setup.secret}</code>
						<button type="button" class="ghost" onclick={() => copy(setup!.secret, 'key')}>
							{copied === 'key' ? $t('copied') : $t('copy')}
						</button>
					</div>
					<p class="small">
						<a href={setup.otpauth_url}>{$t('totp_open_link')}</a>
						·
						<button type="button" class="linklike" onclick={() => copy(setup!.otpauth_url, 'url')}>
							{copied === 'url' ? $t('copied') : $t('totp_copy_link')}
						</button>
					</p>
					<form onsubmit={submit}>
						<label for="totp-code">{$t('totp_first_code')}</label>
						<input
							id="totp-code"
							bind:value={code}
							inputmode="numeric"
							autocomplete="one-time-code"
							maxlength="7"
							placeholder="123456"
						/>
						{#if error}<p class="err">{error}</p>{/if}
						<div class="btns">
							<button type="button" class="ghost" onclick={cancel}>{$t('totp_cancel')}</button>
							<button type="submit" disabled={busy || !code.trim()}>{$t('totp_activate')}</button>
						</div>
					</form>
				{:else if error}
					<p class="err">{error}</p>
					<div class="btns"><button type="button" onclick={cancel}>{$t('totp_cancel')}</button></div>
				{/if}
			{:else if step === 'code'}
				<h3>{ask.mode === 'fresh' ? $t('totp_fresh_title') : $t('totp_title')}</h3>
				<p class="muted">{ask.mode === 'fresh' ? $t('totp_fresh_intro') : $t('totp_intro')}</p>
				<form onsubmit={submit}>
					<label for="totp-code">{$t('totp_code')}</label>
					<!-- svelte-ignore a11y_autofocus -->
					<input
						id="totp-code"
						bind:value={code}
						inputmode="text"
						autocomplete="one-time-code"
						maxlength="16"
						placeholder="123456"
						autofocus
					/>
					<p class="small">{$t('totp_recovery_hint')}</p>
					{#if error}<p class="err">{error}</p>{/if}
					<div class="btns">
						<button type="button" class="ghost" onclick={cancel}>{$t('totp_cancel')}</button>
						<button type="submit" disabled={busy || !code.trim()}>{$t('totp_verify')}</button>
					</div>
				</form>
			{:else}
				<h3>{$t('totp_recovery_title')}</h3>
				<p class="muted">{$t('totp_recovery_intro')}</p>
				<pre class="codes">{recovery.join('\n')}</pre>
				<div class="btns left">
					<button type="button" class="ghost" onclick={() => copy(recovery.join('\n'), 'codes')}>
						{copied === 'codes' ? $t('copied') : $t('copy')}
					</button>
					<button type="button" class="ghost" onclick={download}>{$t('totp_download')}</button>
				</div>
				<label class="check">
					<input type="checkbox" bind:checked={saved} />
					{$t('totp_saved')}
				</label>
				<div class="btns">
					<button type="button" disabled={!saved} onclick={() => ask?.done(true)}>
						{$t('totp_done')}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.back {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 200;
		padding: 1rem;
	}
	.box {
		background: var(--surface);
		color: var(--text);
		border-radius: 12px;
		width: min(440px, 100%);
		max-height: 90vh;
		overflow-y: auto;
		padding: 1.1rem 1.2rem 1.2rem;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
	}
	h3 {
		margin: 0 0 0.4rem;
	}
	.muted {
		color: var(--muted);
		margin: 0 0 0.8rem;
	}
	.small {
		font-size: 0.85rem;
		color: var(--muted);
		margin: 0.5rem 0;
	}
	.qr {
		display: flex;
		justify-content: center;
		background: #fff;
		border-radius: 8px;
		padding: 0.4rem;
		width: fit-content;
		margin: 0 auto;
	}
	.keyrow {
		display: flex;
		gap: 0.5rem;
		align-items: center;
	}
	.key {
		flex: 1;
		word-break: break-all;
		user-select: all;
		background: var(--bg, rgba(127, 127, 127, 0.12));
		padding: 0.4rem 0.5rem;
		border-radius: 6px;
		font-size: 0.9rem;
	}
	label {
		display: block;
		font-weight: 600;
		margin: 0.8rem 0 0.25rem;
	}
	input:not([type]),
	input[inputmode] {
		width: 100%;
		box-sizing: border-box;
		font-size: 1.2rem;
		letter-spacing: 0.15em;
		padding: 0.5rem 0.6rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: inherit;
	}
	.err {
		color: #c0392b;
		margin: 0.4rem 0;
	}
	.btns {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 1rem;
	}
	.btns.left {
		justify-content: flex-start;
		margin-top: 0.6rem;
	}
	button {
		padding: 0.5rem 0.9rem;
		border-radius: 8px;
		border: 1px solid transparent;
		background: var(--accent, #2563eb);
		color: #fff;
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	button.ghost {
		background: none;
		color: inherit;
		border-color: var(--border);
	}
	button.linklike {
		background: none;
		color: var(--accent, #2563eb);
		padding: 0;
		border: 0;
		text-decoration: underline;
	}
	.codes {
		background: rgba(127, 127, 127, 0.12);
		border-radius: 8px;
		padding: 0.7rem 0.9rem;
		font-size: 1rem;
		letter-spacing: 0.06em;
		user-select: all;
		margin: 0;
	}
	.check {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		font-weight: 500;
	}
</style>
