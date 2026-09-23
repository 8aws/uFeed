<script lang="ts">
	import { goto } from '$app/navigation';
	import { api, downloadOpml, importOpml } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import { toolbarLabels, type ToolbarLabels } from '$lib/prefs';
	import type { Locale } from '$lib/types';

	const LABEL_MODES: ToolbarLabels[] = ['auto', 'both', 'icons', 'text'];

	let importMsg = $state('');
	let fileInput: HTMLInputElement;
	let displayName = $state($user?.display_name ?? '');
	let nameSaved = $state(false);

	async function changeLanguage(value: Locale) {
		setLocale(value);
		try {
			await api.updateMe({ locale: value });
		} catch {
			/* not fatal */
		}
	}

	async function saveName() {
		try {
			const updated = await api.updateMe({ display_name: displayName.trim() });
			user.set(updated);
			nameSaved = true;
			setTimeout(() => (nameSaved = false), 1500);
		} catch {
			/* ignore */
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
		<h2>{$t('appearance')}</h2>
		<div class="field">
			{$t('toolbar_labels')}
			<div class="row">
				{#each LABEL_MODES as m (m)}
					<button class:active={$toolbarLabels === m} onclick={() => toolbarLabels.set(m)}>
						{$t(`labels_${m}` as 'labels_auto')}
					</button>
				{/each}
			</div>
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
		<label class="field">
			{$t('display_name')}
			<div class="row">
				<input bind:value={displayName} maxlength="60" placeholder={$t('name_placeholder')} />
				<button class="primary" onclick={saveName}>{nameSaved ? '✓' : $t('save')}</button>
			</div>
		</label>
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
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.9rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
</style>
