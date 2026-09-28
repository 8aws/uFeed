// Starter catalogue for new users: topical sections with language parity —
// three English and three Spanish sources each. Every URL was validated from
// the production backend (same fetcher/User-Agent as ingest) as returning a
// live feed with recent entries; very high-volume feeds were avoided so a new
// account's Unread view isn't flooded. Titles are curated and applied as the
// subscription's display name.

import { api } from '$lib/api';

export type FeedLang = 'en' | 'es';

export interface CatalogFeed {
	title: string;
	url: string;
	lang: FeedLang;
}
export interface CatalogSection {
	id: string;
	name_en: string;
	name_es: string;
	feeds: CatalogFeed[];
}

export const LANG_FLAG: Record<FeedLang, string> = { en: '🇬🇧', es: '🇪🇸' };

export const CATALOG: CatalogSection[] = [
	{
		id: 'tech',
		name_en: 'Technology',
		name_es: 'Tecnología',
		feeds: [
			{ lang: 'en', title: 'The Verge', url: 'https://www.theverge.com/rss/index.xml' },
			{ lang: 'en', title: 'Ars Technica', url: 'https://feeds.arstechnica.com/arstechnica/index' },
			{ lang: 'en', title: 'TechCrunch', url: 'https://techcrunch.com/feed/' },
			{ lang: 'es', title: 'Xataka', url: 'https://www.xataka.com/feedburner.xml' },
			{ lang: 'es', title: 'Hipertextual', url: 'https://hipertextual.com/feed' },
			{
				lang: 'es',
				title: 'El País · Tecnología',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada'
			}
		]
	},
	{
		id: 'ai',
		name_en: 'AI & Machine Learning',
		name_es: 'IA y Machine Learning',
		feeds: [
			{ lang: 'en', title: 'MIT Technology Review', url: 'https://www.technologyreview.com/feed/' },
			{ lang: 'en', title: 'Google AI Blog', url: 'https://blog.google/technology/ai/rss/' },
			{ lang: 'en', title: 'Simon Willison', url: 'https://simonwillison.net/atom/everything/' },
			{ lang: 'es', title: "WWWhat's new", url: 'https://wwwhatsnew.com/feed/' },
			{
				lang: 'es',
				title: 'Xataka · IA',
				url: 'https://www.xataka.com/tag/inteligencia-artificial/rss2.xml'
			},
			{
				lang: 'es',
				title: 'Xataka Móvil · IA',
				url: 'https://www.xatakamovil.com/tag/inteligencia-artificial/rss2.xml'
			}
		]
	},
	{
		id: 'dev',
		name_en: 'Software Development',
		name_es: 'Desarrollo de software',
		feeds: [
			{ lang: 'en', title: 'The GitHub Blog', url: 'https://github.blog/feed/' },
			{ lang: 'en', title: 'Stack Overflow Blog', url: 'https://stackoverflow.blog/feed/' },
			{ lang: 'en', title: 'Martin Fowler', url: 'https://martinfowler.com/feed.atom' },
			{ lang: 'es', title: 'Xataka · Programación', url: 'https://www.xataka.com/tag/programacion/rss2.xml' },
			{ lang: 'es', title: 'Paradigma Digital', url: 'https://www.paradigmadigital.com/feed/' },
			{ lang: 'es', title: 'Javier Garzás', url: 'https://www.javiergarzas.com/feed' }
		]
	},
	{
		id: 'science',
		name_en: 'Science',
		name_es: 'Ciencia',
		feeds: [
			{ lang: 'en', title: 'NASA', url: 'https://www.nasa.gov/news-release/feed/' },
			{ lang: 'en', title: 'Quanta Magazine', url: 'https://api.quantamagazine.org/feed/' },
			{ lang: 'en', title: 'New Scientist', url: 'https://www.newscientist.com/feed/home/' },
			{ lang: 'es', title: 'Naukas', url: 'https://naukas.com/feed/' },
			{
				lang: 'es',
				title: 'El País · Ciencia',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/ciencia/portada'
			},
			{ lang: 'es', title: 'Muy Interesante', url: 'https://www.muyinteresante.com/feed/' }
		]
	},
	{
		id: 'world',
		name_en: 'World News',
		name_es: 'Noticias del mundo',
		feeds: [
			{ lang: 'en', title: 'BBC World', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
			{ lang: 'en', title: 'The Guardian · World', url: 'https://www.theguardian.com/world/rss' },
			{ lang: 'en', title: 'Al Jazeera', url: 'https://www.aljazeera.com/xml/rss/all.xml' },
			{
				lang: 'es',
				title: 'El País · Internacional',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada'
			},
			{ lang: 'es', title: 'BBC Mundo', url: 'https://feeds.bbci.co.uk/mundo/rss.xml' },
			{ lang: 'es', title: 'DW Español', url: 'https://rss.dw.com/xml/rss-sp-all' }
		]
	},
	{
		id: 'business',
		name_en: 'Business & Economy',
		name_es: 'Negocios y economía',
		feeds: [
			{ lang: 'en', title: 'Financial Times', url: 'https://www.ft.com/rss/home' },
			{ lang: 'en', title: 'The Guardian · Business', url: 'https://www.theguardian.com/uk/business/rss' },
			{ lang: 'en', title: 'MarketWatch', url: 'https://feeds.marketwatch.com/marketwatch/topstories/' },
			{ lang: 'es', title: 'Expansión', url: 'https://e00-expansion.uecdn.es/rss/portada.xml' },
			{
				lang: 'es',
				title: 'Cinco Días',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/cincodias.elpais.com/portada'
			},
			{ lang: 'es', title: 'El Confidencial · Economía', url: 'https://rss.elconfidencial.com/economia/' }
		]
	},
	{
		id: 'design',
		name_en: 'Design & UX',
		name_es: 'Diseño y UX',
		feeds: [
			{ lang: 'en', title: 'Smashing Magazine', url: 'https://www.smashingmagazine.com/feed/' },
			{ lang: 'en', title: 'Nielsen Norman Group', url: 'https://www.nngroup.com/feed/rss/' },
			{ lang: 'en', title: 'UX Collective', url: 'https://uxdesign.cc/feed' },
			{ lang: 'es', title: 'Gràffica', url: 'https://graffica.info/feed/' },
			{ lang: 'es', title: 'uiFromMars', url: 'https://www.uifrommars.com/feed/' },
			{ lang: 'es', title: 'Torresburriel Estudio', url: 'https://www.torresburriel.com/weblog/feed/' }
		]
	},
	{
		id: 'gaming',
		name_en: 'Gaming',
		name_es: 'Videojuegos',
		feeds: [
			{ lang: 'en', title: 'Polygon', url: 'https://www.polygon.com/rss/index.xml' },
			{ lang: 'en', title: 'Kotaku', url: 'https://kotaku.com/rss' },
			{ lang: 'en', title: 'IGN', url: 'https://feeds.feedburner.com/ign/all' },
			{ lang: 'es', title: 'Vandal', url: 'https://vandal.elespanol.com/xml.cgi' },
			{ lang: 'es', title: '3DJuegos', url: 'https://www.3djuegos.com/feedburner.xml' },
			{ lang: 'es', title: 'Vida Extra', url: 'https://www.vidaextra.com/feedburner.xml' }
		]
	},
	{
		id: 'space',
		name_en: 'Space & Physics',
		name_es: 'Espacio y física',
		feeds: [
			{ lang: 'en', title: 'ESA', url: 'https://www.esa.int/rssfeed/Our_Activities/Space_News' },
			{ lang: 'en', title: 'Universe Today', url: 'https://www.universetoday.com/feed/' },
			{ lang: 'en', title: 'Phys.org', url: 'https://phys.org/rss-feed/' },
			{ lang: 'es', title: 'Eureka (Daniel Marín)', url: 'https://danielmarin.naukas.com/feed/' },
			{ lang: 'es', title: 'La Ciencia de la Mula Francis', url: 'https://francis.naukas.com/feed/' },
			{ lang: 'es', title: 'Sondas Espaciales', url: 'https://www.sondasespaciales.com/feed/' }
		]
	},
	{
		id: 'culture',
		name_en: 'Culture & Ideas',
		name_es: 'Cultura e ideas',
		feeds: [
			{ lang: 'en', title: 'NPR · Culture', url: 'https://feeds.npr.org/1008/rss.xml' },
			{ lang: 'en', title: 'The New Yorker · Culture', url: 'https://www.newyorker.com/feed/culture' },
			{ lang: 'en', title: 'Aeon', url: 'https://aeon.co/feed.rss' },
			{
				lang: 'es',
				title: 'El País · Cultura',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/cultura/portada'
			},
			{ lang: 'es', title: 'Jot Down', url: 'https://www.jotdown.es/feed/' },
			{ lang: 'es', title: 'El Confidencial · Cultura', url: 'https://rss.elconfidencial.com/cultura/' }
		]
	},
	{
		id: 'security',
		name_en: 'Cybersecurity',
		name_es: 'Ciberseguridad',
		feeds: [
			{ lang: 'en', title: 'Krebs on Security', url: 'https://krebsonsecurity.com/feed/' },
			{ lang: 'en', title: 'The Hacker News', url: 'https://feeds.feedburner.com/TheHackersNews' },
			{ lang: 'en', title: 'BleepingComputer', url: 'https://www.bleepingcomputer.com/feed/' },
			{ lang: 'es', title: 'Una al Día (Hispasec)', url: 'https://unaaldia.hispasec.com/feed' },
			{
				lang: 'es',
				title: 'Un informático en el lado del mal',
				url: 'https://www.elladodelmal.com/feeds/posts/default?alt=rss'
			},
			{
				lang: 'es',
				title: 'Segu-Info',
				url: 'https://blog.segu-info.com.ar/feeds/posts/default?alt=rss'
			}
		]
	},
	{
		id: 'sports',
		name_en: 'Sports',
		name_es: 'Deportes',
		feeds: [
			{ lang: 'en', title: 'BBC Sport', url: 'https://feeds.bbci.co.uk/sport/rss.xml' },
			{ lang: 'en', title: 'ESPN', url: 'https://www.espn.com/espn/rss/news' },
			{ lang: 'en', title: 'Sky Sports', url: 'https://www.skysports.com/rss/12040' },
			{ lang: 'es', title: 'Marca', url: 'https://e00-marca.uecdn.es/rss/portada.xml' },
			{ lang: 'es', title: 'AS', url: 'https://feeds.as.com/mrss-s/pages/as/site/as.com/portada' },
			{
				lang: 'es',
				title: 'El País · Deportes',
				url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/deportes/portada'
			}
		]
	}
];

/** The starter list editors curated on this server, or the built-in one. */
export async function fetchCatalog(): Promise<CatalogSection[]> {
	try {
		return (await api.catalog()).sections ?? CATALOG;
	} catch {
		return CATALOG;
	}
}
