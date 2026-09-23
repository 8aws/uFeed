// Starter catalogue for new users: topical sections, each with a few reputable
// feeds. Used by the onboarding picker. Titles are shown as-is; section names
// are localised. Keep feeds to stable, well-known RSS/Atom endpoints.

export interface CatalogFeed {
	title: string;
	url: string;
}
export interface CatalogSection {
	id: string;
	name_en: string;
	name_es: string;
	feeds: CatalogFeed[];
}

export const CATALOG: CatalogSection[] = [
	{
		id: 'tech',
		name_en: 'Technology',
		name_es: 'Tecnología',
		feeds: [
			{ title: 'The Verge', url: 'https://www.theverge.com/rss/index.xml' },
			{ title: 'Ars Technica', url: 'https://feeds.arstechnica.com/arstechnica/index' },
			{ title: 'Xataka', url: 'https://www.xataka.com/tag/feeds/rss2.xml' }
		]
	},
	{
		id: 'ai',
		name_en: 'AI & Machine Learning',
		name_es: 'IA y Machine Learning',
		feeds: [
			{ title: 'MIT Technology Review', url: 'https://www.technologyreview.com/feed/' },
			{ title: 'Google AI Blog', url: 'https://blog.google/technology/ai/rss/' },
			{ title: 'Hugging Face Blog', url: 'https://huggingface.co/blog/feed.xml' }
		]
	},
	{
		id: 'dev',
		name_en: 'Software Development',
		name_es: 'Desarrollo de software',
		feeds: [
			{ title: 'Hacker News (front page)', url: 'https://hnrss.org/frontpage' },
			{ title: 'GitHub Blog', url: 'https://github.blog/feed/' },
			{ title: 'Stack Overflow Blog', url: 'https://stackoverflow.blog/feed/' }
		]
	},
	{
		id: 'science',
		name_en: 'Science',
		name_es: 'Ciencia',
		feeds: [
			{ title: 'NASA', url: 'https://www.nasa.gov/rss/dyn/breaking_news.rss' },
			{ title: 'Nature News', url: 'https://www.nature.com/nature.rss' },
			{ title: 'Quanta Magazine', url: 'https://api.quantamagazine.org/feed/' }
		]
	},
	{
		id: 'world',
		name_en: 'World News',
		name_es: 'Noticias del mundo',
		feeds: [
			{ title: 'BBC World', url: 'https://feeds.bbci.co.uk/news/world/rss.xml' },
			{ title: 'Reuters World', url: 'https://www.reutersagency.com/feed/?best-topics=world&post_type=best' },
			{ title: 'El País (Portada)', url: 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada' }
		]
	},
	{
		id: 'business',
		name_en: 'Business & Economy',
		name_es: 'Negocios y economía',
		feeds: [
			{ title: 'The Economist', url: 'https://www.economist.com/finance-and-economics/rss.xml' },
			{ title: 'Financial Times (Home)', url: 'https://www.ft.com/rss/home' },
			{ title: 'Expansión', url: 'https://e00-expansion.uecdn.es/rss/portada.xml' }
		]
	},
	{
		id: 'design',
		name_en: 'Design & UX',
		name_es: 'Diseño y UX',
		feeds: [
			{ title: 'Smashing Magazine', url: 'https://www.smashingmagazine.com/feed/' },
			{ title: 'A List Apart', url: 'https://alistapart.com/main/feed/' },
			{ title: 'Nielsen Norman Group', url: 'https://www.nngroup.com/feed/rss/' }
		]
	},
	{
		id: 'gaming',
		name_en: 'Gaming',
		name_es: 'Videojuegos',
		feeds: [
			{ title: 'Eurogamer', url: 'https://www.eurogamer.net/feed' },
			{ title: 'Polygon', url: 'https://www.polygon.com/rss/index.xml' },
			{ title: 'Vandal', url: 'https://vandal.elespanol.com/xml.cgi' }
		]
	},
	{
		id: 'science_pop',
		name_en: 'Space & Physics',
		name_es: 'Espacio y física',
		feeds: [
			{ title: 'Space.com', url: 'https://www.space.com/feeds/all' },
			{ title: 'Phys.org', url: 'https://phys.org/rss-feed/' },
			{ title: 'ESA', url: 'https://www.esa.int/rssfeed/Our_Activities/Space_News' }
		]
	},
	{
		id: 'culture',
		name_en: 'Culture & Media',
		name_es: 'Cultura y medios',
		feeds: [
			{ title: 'The Guardian (Culture)', url: 'https://www.theguardian.com/culture/rss' },
			{ title: 'NPR Culture', url: 'https://feeds.npr.org/1008/rss.xml' },
			{ title: 'JOT Down', url: 'https://www.jotdown.es/feed/' }
		]
	},
	{
		id: 'security',
		name_en: 'Cybersecurity',
		name_es: 'Ciberseguridad',
		feeds: [
			{ title: 'Krebs on Security', url: 'https://krebsonsecurity.com/feed/' },
			{ title: 'The Hacker News', url: 'https://feeds.feedburner.com/TheHackersNews' },
			{ title: 'Bleeping Computer', url: 'https://www.bleepingcomputer.com/feed/' }
		]
	},
	{
		id: 'sports',
		name_en: 'Sports',
		name_es: 'Deportes',
		feeds: [
			{ title: 'BBC Sport', url: 'https://feeds.bbci.co.uk/sport/rss.xml' },
			{ title: 'ESPN', url: 'https://www.espn.com/espn/rss/news' },
			{ title: 'Marca', url: 'https://e00-marca.uecdn.es/rss/portada.xml' }
		]
	}
];
