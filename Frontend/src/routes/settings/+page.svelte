<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, downloadOpml, importOpml } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import type { Locale } from '$lib/types';

	let importMsg = $state('');
	let fileInput: HTMLInputElement;

	async function changeLanguage(value: Locale) {
		setLocale(value);
		try {
			await api.updateMe(value);
		} catch {
			/* not fatal */
		}
	}

	async function onImport(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		importMsg = '';
		try {
			const res = await importOpml(file);
			importMsg = `+${res.imported} / ${res.skipped} skipped`;
		} catch {
			importMsg = '⚠';
		}
		input.value = '';
	}

	function logout() {
		clearTokens();
		goto('/login');
	}
</script>

<div class="page">
	<a class="back" href="/">← {$t('app_name')}</a>
	<h1>{$t('settings')}</h1>

	<section>
		<h2>{$t('language')}</h2>
		<div class="row">
			<button class:active={$locale === 'en'} onclick={() => changeLanguage('en')}>English</button>
			<button class:active={$locale === 'es'} onclick={() => changeLanguage('es')}>Español</button>
		</div>
	</section>

	<section>
		<h2>{$t('feeds')}</h2>
		<div class="row">
			<button onclick={() => fileInput.click()}>{$t('import_opml')}</button>
			<button onclick={downloadOpml}>{$t('export_opml')}</button>
			<input
				type="file"
				accept=".opml,.xml,text/xml,application/xml"
				bind:this={fileInput}
				onchange={onImport}
				hidden
			/>
			{#if importMsg}<span class="muted">{importMsg}</span>{/if}
		</div>
	</section>

	<section>
		<h2>{$t('account')}</h2>
		{#if $user}<p class="muted">{$user.email}</p>{/if}
		<button onclick={logout}>{$t('logout')}</button>
	</section>
</div>

<style>
	.page {
		max-width: 640px;
		margin: 0 auto;
		padding: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}
	.back {
		font-size: 0.9rem;
	}
	h1 {
		margin: 0;
	}
	section {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1rem 1.25rem;
	}
	h2 {
		margin: 0 0 0.75rem;
		font-size: 0.95rem;
	}
	.row {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
</style>
