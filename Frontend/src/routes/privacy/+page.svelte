<script lang="ts">
	import LegalPage from '$lib/components/LegalPage.svelte';
	import { locale, t } from '$lib/i18n';
</script>

<svelte:head><title>{$t('privacy')} · uFeed</title></svelte:head>

<LegalPage title={$t('privacy')}>
	{#snippet children(contact: string)}
		{#if $locale === 'es'}
			<p>
				uFeed es un lector de noticias (RSS) autoalojado: todo funciona en un servidor propio, sin
				publicidad, sin analítica de terceros y sin rastreo. Esta página explica qué datos guarda y para qué.
			</p>
			<h2>Qué datos guardamos</h2>
			<ul>
				<li><strong>Cuenta:</strong> email, contraseña (solo su huella cifrada, nunca el texto), nombre visible opcional e idioma.</li>
				<li><strong>Tu lectura:</strong> las fuentes y carpetas que sigues, qué artículos has leído, guardado o marcado como favoritos, tus filtros y tus claves API.</li>
				<li><strong>Actividad de lectura:</strong> tiempo y porcentaje leído de cada artículo y si lo abres, compartes o saltas. Se usa, agregada y sin identificarte, para las Tendencias y para recomendarte artículos.</li>
				<li><strong>Última actividad</strong>, para desactivar cuentas abandonadas.</li>
			</ul>
			<h2>Inteligencia artificial</h2>
			<p>
				Los resúmenes, traducciones y la voz del servidor se generan en el propio servidor de uFeed: el texto de
				los artículos no se envía a ningún servicio externo. Lo generado se guarda asociado al artículo, no a ti.
			</p>
			<h2>Terceros</h2>
			<ul>
				<li>El servidor descarga los feeds que sigues desde sus webs de origen.</li>
				<li>Las imágenes de los artículos se cargan desde esas webs, y al abrir un enlace vas a la web del medio.</li>
				<li>Los vídeos de YouTube o Vimeo solo se cargan si pulsas su tarjeta (YouTube en su modo sin cookies).</li>
			</ul>
			<h2>Cuánto tiempo</h2>
			<ul>
				<li>Los artículos se conservan 90 días (los guardados y favoritos, siempre).</li>
				<li>Las cuentas sin uso durante 180 días se desactivan y, si nadie las recupera, se borran 180 días después.</li>
				<li>Las copias de seguridad están cifradas y rotan en 30 días.</li>
			</ul>
			<h2>En tu dispositivo</h2>
			<p>
				Se guardan tus preferencias y, si lo activas, una copia sin conexión de tus guardados y de su audio. Se
				borran al cerrar sesión.
			</p>
			<h2>Tus derechos</h2>
			<ul>
				<li>Exportar tus fuentes (OPML) desde Ajustes.</li>
				<li>
					<strong>Borrar tu cuenta</strong> en Ajustes → Cuenta → Eliminar mi cuenta: se borran al momento tus
					datos; de las copias de seguridad desaparecen en un máximo de 30 días.
				</li>
			</ul>
			<h2>Contacto</h2>
			<p>{#if contact}<a href="mailto:{contact}">{contact}</a>{:else}El administrador de este servidor.{/if}</p>
		{:else}
			<p>
				uFeed is a self-hosted news (RSS) reader: everything runs on its own server, with no ads, no third-party
				analytics and no tracking. This page explains what data it keeps and why.
			</p>
			<h2>What we store</h2>
			<ul>
				<li><strong>Account:</strong> email, password (only its hash, never the text), optional display name and language.</li>
				<li><strong>Your reading:</strong> the feeds and folders you follow, which articles you read, saved or favourited, your filters and API keys.</li>
				<li><strong>Reading activity:</strong> time and share read of each article and whether you open, share or skip it. Used in aggregate, without identifying you, for Trending and to recommend articles.</li>
				<li><strong>Last activity</strong>, to deactivate abandoned accounts.</li>
			</ul>
			<h2>Artificial intelligence</h2>
			<p>
				Summaries, translations and the server voice are generated on uFeed's own server: article text is not
				sent to any outside service. What's generated is stored with the article, not with you.
			</p>
			<h2>Third parties</h2>
			<ul>
				<li>The server downloads the feeds you follow from their websites.</li>
				<li>Article images load from those websites, and links take you to the publisher's site.</li>
				<li>YouTube or Vimeo videos only load when you tap their card (YouTube in its no-cookie mode).</li>
			</ul>
			<h2>How long</h2>
			<ul>
				<li>Articles are kept for 90 days (saved and favourites, always).</li>
				<li>Accounts unused for 180 days are deactivated and, if nobody reclaims them, deleted 180 days later.</li>
				<li>Backups are encrypted and rotate within 30 days.</li>
			</ul>
			<h2>On your device</h2>
			<p>
				Your preferences and, if you turn it on, an offline copy of your saved articles and their audio. They're
				removed when you log out.
			</p>
			<h2>Your rights</h2>
			<ul>
				<li>Export your feeds (OPML) from Settings.</li>
				<li>
					<strong>Delete your account</strong> in Settings → Account → Delete my account: your data is removed
					at once; from backups it disappears within 30 days.
				</li>
			</ul>
			<h2>Contact</h2>
			<p>{#if contact}<a href="mailto:{contact}">{contact}</a>{:else}The administrator of this server.{/if}</p>
		{/if}
	{/snippet}
</LegalPage>
