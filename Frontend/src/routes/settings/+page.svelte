<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, downloadOpml, importOpml } from '$lib/api';
	import { clearTokens, user } from '$lib/auth';
	import { locale, setLocale, t } from '$lib/i18n';
	import { toolbarLabels, type ToolbarLabels } from '$lib/prefs';
	import { relativeTime } from '$lib/format';
	import type { ApiKey, ApiKeyCreated, Locale } from '$lib/types';

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

	// --- API keys (read-only access for external apps such as OneDay) ---
	let keys = $state<ApiKey[]>([]);
	let newKeyName = $state('OneDay');
	let created = $state<ApiKeyCreated | null>(null);
	let copied = $state<'url' | 'key' | null>(null);
	let serverUrl = $state('');

	async function loadKeys() {
		try {
			keys = (await api.listKeys()).filter((k) => !k.revoked_at);
		} catch {
			/* ignore */
		}
	}

	async function createKey() {
		const name = newKeyName.trim();
		if (!name) return;
		try {
			created = await api.createKey(name);
			await loadKeys();
		} catch {
			/* ignore */
		}
	}

	async function revokeKey(k: ApiKey) {
		if (!confirm($t('confirm_revoke'))) return;
		try {
			await api.revokeKey(k.id);
			if (created?.id === k.id) created = null;
			await loadKeys();
		} catch {
			/* ignore */
		}
	}

	async function copy(text: string, what: 'url' | 'key') {
		try {
			await navigator.clipboard.writeText(text);
			copied = what;
			setTimeout(() => (copied = null), 1500);
		} catch {
			/* clipboard unavailable: the value is selectable on screen */
		}
	}

	onMount(() => {
		serverUrl = window.location.origin;
		loadKeys();
	});

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
		<h2>{$t('api_access')}</h2>
		<p class="muted hint">{$t('api_access_hint')}</p>
		<div class="field">
			{$t('server_url')}
			<div class="row">
				<code class="mono">{serverUrl}</code>
				<button onclick={() => copy(serverUrl, 'url')}>{copied === 'url' ? '✓ ' + $t('copied') : $t('copy')}</button>
			</div>
		</div>
		<label class="field">
			{$t('key_name')}
			<div class="row">
				<input bind:value={newKeyName} maxlength="120" />
				<button class="primary" onclick={createKey} disabled={!newKeyName.trim()}>{$t('generate_key')}</button>
			</div>
		</label>
		{#if created}
			<div class="newkey">
				<p><strong>{created.name}</strong> — {$t('key_created_once')}</p>
				<div class="row">
					<code class="mono secret">{created.key}</code>
					<button onclick={() => copy(created!.key, 'key')}>{copied === 'key' ? '✓ ' + $t('copied') : $t('copy')}</button>
				</div>
			</div>
		{/if}
		{#if keys.length === 0}
			<p class="muted">{$t('no_keys')}</p>
		{:else}
			<ul class="keys">
				{#each keys as k (k.id)}
					<li>
						<div class="kinfo">
							<strong>{k.name}</strong> <code class="mono">{k.prefix}…</code>
							<span class="muted small">
								{$t('created')} {relativeTime(k.created_at, $locale)} ·
								{k.last_used_at ? `${$t('last_used')} ${relativeTime(k.last_used_at, $locale)}` : $t('never_used')}
							</span>
						</div>
						<button onclick={() => revokeKey(k)}>{$t('revoke')}</button>
					</li>
				{/each}
			</ul>
		{/if}
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
	.hint {
		margin: 0 0 0.75rem;
		font-size: 0.85rem;
	}
	.mono {
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 0.8rem;
		background: var(--bg);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.3rem 0.5rem;
		overflow-wrap: anywhere;
		color: var(--text, inherit);
	}
	.secret {
		user-select: all;
		-webkit-user-select: all;
		flex: 1;
		min-width: 0;
	}
	.newkey {
		border: 1px solid var(--accent);
		background: var(--accent-soft);
		border-radius: 10px;
		padding: 0.6rem 0.75rem;
		margin-bottom: 0.9rem;
		font-size: 0.85rem;
	}
	.newkey p {
		margin: 0 0 0.4rem;
	}
	.keys {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.keys li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		border-top: 1px solid var(--border);
		padding-top: 0.5rem;
	}
	.kinfo {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.small {
		font-size: 0.78rem;
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
</style>
