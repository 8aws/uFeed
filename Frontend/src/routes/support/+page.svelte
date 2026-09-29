<script lang="ts">
	import LegalPage from '$lib/components/LegalPage.svelte';
	import { locale, t } from '$lib/i18n';
</script>

<svelte:head><title>{$t('support')} · uFeed</title></svelte:head>

<LegalPage title={$t('support')}>
	{#snippet children(contact: string)}
		{#if $locale === 'es'}
			<p>¿Dudas o problemas con uFeed? Aquí tienes lo más habitual y cómo contactar.</p>
			<h2>Preguntas frecuentes</h2>
			<ul>
				<li><strong>Añadir fuentes:</strong> pega la dirección de una web o de su feed en «Añadir fuente», o elige entre las sugerencias en Ajustes.</li>
				<li><strong>Marcar como leído:</strong> mantén pulsado un artículo o deslízalo a la derecha.</li>
				<li><strong>Escuchar:</strong> botón 🔊 en el artículo; la voz y el ritmo se eligen en Ajustes → Lectura en voz alta.</li>
				<li><strong>Sin conexión:</strong> tus artículos guardados se pueden leer sin conexión.</li>
				<li><strong>Contraseña:</strong> cámbiala en Ajustes → Contraseña. Si la olvidaste, escribe al contacto.</li>
				<li><strong>Borrar la cuenta:</strong> Ajustes → Cuenta → Eliminar mi cuenta.</li>
			</ul>
			<h2>Contacto</h2>
			<p>{#if contact}Escríbenos a <a href="mailto:{contact}">{contact}</a>.{:else}Contacta con el administrador de este servidor.{/if}</p>
		{:else}
			<p>Questions or problems with uFeed? Here are the usual answers and how to get in touch.</p>
			<h2>FAQ</h2>
			<ul>
				<li><strong>Adding feeds:</strong> paste a website or feed address in "Add feed", or pick from the suggestions in Settings.</li>
				<li><strong>Mark as read:</strong> long-press an article or swipe it right.</li>
				<li><strong>Listening:</strong> the 🔊 button in an article; voice and pace are in Settings → Read aloud.</li>
				<li><strong>Offline:</strong> your saved articles can be read without connection.</li>
				<li><strong>Password:</strong> change it in Settings → Password. If you forgot it, write to the contact below.</li>
				<li><strong>Deleting your account:</strong> Settings → Account → Delete my account.</li>
			</ul>
			<h2>Contact</h2>
			<p>{#if contact}Write to <a href="mailto:{contact}">{contact}</a>.{:else}Contact the administrator of this server.{/if}</p>
		{/if}
	{/snippet}
</LegalPage>
