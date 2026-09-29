<script lang="ts">
	import { authed } from '$lib/auth';
	import { locale, setLocale } from '$lib/i18n';

	// Public presentation of the app (/info, /features): what uFeed does, for
	// visitors and the app store listing. No account needed.
	const es = $derived($locale === 'es');
	const F = {
		es: [
			['📰', 'Artículo completo', 'Si una fuente solo publica un extracto, uFeed trae el artículo entero de la web: texto, imágenes y listas.'],
			['🔊', 'Escucha tus noticias', 'Voz neuronal natural, masculina o femenina, que sigue sonando con la pantalla bloqueada. O la voz de tu dispositivo, sin conexión.'],
			['📻', 'Post radio', 'Tus noticias una tras otra, como un podcast, con un sonido entre posts. Solo marca como leído lo que escuchas.'],
			['🌐', 'En tu idioma', 'Traduce al instante entre español e inglés, y escucha cada artículo en tu idioma.'],
			['✨', 'Resúmenes con IA', 'Resúmenes en tu idioma generados en nuestro propio servidor: tu lectura no sale a servicios de IA externos.'],
			['📴', 'Sin conexión', 'Tus guardados, sus imágenes y su audio, disponibles sin red. Lo que marques se sincroniza al volver.'],
			['🔥', 'Tendencias', 'Lo más leído de verdad, medido por lectura real y de forma anónima.'],
			['♿', 'Accesible', 'Lectura automática al abrir, frase resaltada mientras escuchas, texto grande y tipografía Atkinson Hyperlegible.'],
			['🔒', 'Privado', 'Sin anuncios, sin rastreadores, sin analítica de terceros. Borra tu cuenta cuando quieras.']
		],
		en: [
			['📰', 'Full article', 'When a feed only publishes an excerpt, uFeed brings the whole article from the website: text, images and lists.'],
			['🔊', 'Listen to your news', 'A natural neural voice, male or female, that keeps playing with the screen locked. Or your device voice, offline.'],
			['📻', 'Post radio', 'Your news one after another, like a podcast, with a chime between posts. Only what you hear is marked read.'],
			['🌐', 'In your language', 'Instant Spanish ↔ English translation, and every article read aloud in your language.'],
			['✨', 'AI summaries', 'Summaries in your language made on our own server: your reading never goes to outside AI services.'],
			['📴', 'Offline', 'Your saved articles, their images and audio, without a connection. What you mark syncs when you are back.'],
			['🔥', 'Trending', 'What people really read, measured by actual reading, anonymously.'],
			['♿', 'Accessible', 'Read aloud on open, sentence highlighting while you listen, large text and the Atkinson Hyperlegible font.'],
			['🔒', 'Private', 'No ads, no trackers, no third-party analytics. Delete your account whenever you want.']
		]
	};
</script>

<svelte:head>
	<title>uFeed — {es ? 'Tus noticias, para leer y escuchar' : 'Your news, to read and to listen'}</title>
	<meta
		name="description"
		content={es
			? 'Lector de noticias RSS con artículo completo, voz neuronal, Post radio, traducción y resúmenes IA. Sin anuncios ni rastreo.'
			: 'RSS news reader with full articles, neural voice, Post radio, translation and AI summaries. No ads, no tracking.'}
	/>
</svelte:head>

<div class="landing">
	<header>
		<span class="brand"><img src="/icon-192.png?v=2" alt="" width="36" height="36" /> uFeed</span>
		<span class="langs">
			<button class:active={es} onclick={() => setLocale('es')}>ES</button>
			<button class:active={!es} onclick={() => setLocale('en')}>EN</button>
		</span>
	</header>

	<section class="hero">
		<img class="logo" src="/icon-512.png?v=2" alt="uFeed" width="112" height="112" />
		<h1>{es ? 'Tus noticias, para leer y escuchar' : 'Your news, to read and to listen'}</h1>
		<p class="lead">
			{es
				? 'Un lector RSS rápido y limpio que trae el artículo completo, te lo lee con voz natural y lo traduce a tu idioma. Sin anuncios y sin rastreo.'
				: 'A fast, clean RSS reader that fetches the full article, reads it to you with a natural voice and translates it into your language. No ads, no tracking.'}
		</p>
		<a class="cta" href={$authed ? '/' : '/login'}>{es ? 'Abrir uFeed' : 'Open uFeed'} →</a>
	</section>

	<section class="grid">
		{#each F[es ? 'es' : 'en'] as [ico, title, text] (title)}
			<article>
				<span class="ico" aria-hidden="true">{ico}</span>
				<h2>{title}</h2>
				<p>{text}</p>
			</article>
		{/each}
	</section>

	<section class="more">
		<h2>{es ? 'Y además' : 'And also'}</h2>
		<p>
			{es
				? 'Carpetas, filtros por palabras, fuentes silenciadas, vistas de lista, tarjetas y mosaico, gestos para marcar y guardar, importación y exportación OPML, sugerencias iniciales por temas y una API para conectar otras apps.'
				: 'Folders, keyword filters, muted sources, list, card and masonry views, gestures to mark and save, OPML import and export, curated starter suggestions and an API to connect other apps.'}
		</p>
	</section>

	<footer>
		<a href="/privacy">{es ? 'Privacidad' : 'Privacy'}</a> · <a href="/support">{es ? 'Soporte' : 'Support'}</a>
		· <a href={$authed ? '/' : '/login'}>{es ? 'Entrar' : 'Sign in'}</a>
	</footer>
</div>

<style>
	.landing {
		max-width: 1040px;
		margin: 0 auto;
		padding: 1rem 1.25rem 3rem;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 700;
		font-size: 1.1rem;
	}
	.brand img {
		border-radius: 9px;
	}
	.langs {
		display: flex;
		gap: 0.3rem;
	}
	.langs button {
		padding: 0.2rem 0.55rem;
		font-size: 0.8rem;
	}
	.langs button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	.hero {
		text-align: center;
		padding: 3rem 0 2.5rem;
	}
	.logo {
		border-radius: 26px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
	}
	h1 {
		font-size: clamp(1.7rem, 5vw, 2.6rem);
		line-height: 1.15;
		margin: 1.25rem auto 0.75rem;
		max-width: 18ch;
	}
	.lead {
		color: var(--muted);
		font-size: 1.08rem;
		max-width: 44rem;
		margin: 0 auto;
		line-height: 1.55;
	}
	.cta {
		display: inline-block;
		margin-top: 1.5rem;
		padding: 0.75rem 1.4rem;
		border-radius: 999px;
		background: #e8551f;
		color: #fff;
		font-weight: 600;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
		gap: 0.9rem;
	}
	.grid article {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 1rem 1.1rem;
	}
	.ico {
		font-size: 1.6rem;
	}
	.grid h2 {
		font-size: 1.02rem;
		margin: 0.4rem 0 0.3rem;
	}
	.grid p,
	.more p {
		margin: 0;
		color: var(--muted);
		line-height: 1.5;
		font-size: 0.95rem;
	}
	.more {
		margin-top: 2rem;
		text-align: center;
	}
	.more h2 {
		font-size: 1.1rem;
	}
	.more p {
		max-width: 46rem;
		margin: 0 auto;
	}
	footer {
		margin-top: 2.5rem;
		text-align: center;
		font-size: 0.9rem;
	}
</style>
