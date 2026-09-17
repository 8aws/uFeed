export type Locale = 'en' | 'es';

export interface User {
	id: string;
	email: string;
	display_name: string | null;
	locale: Locale;
	is_active: boolean;
	created_at: string;
}

export interface Tokens {
	access_token: string;
	refresh_token: string;
	token_type: string;
}

export interface AuthResponse {
	user: User;
	tokens: Tokens;
}

export interface Folder {
	id: string;
	name: string;
	position: number;
}

export interface Source {
	id: string;
	feed_url: string;
	site_url: string | null;
	title: string | null;
	favicon_url: string | null;
}

export interface Subscription {
	id: string;
	source: Source;
	folder_id: string | null;
	custom_title: string | null;
	unread_count: number;
}

export interface Article {
	id: string;
	source_id: string;
	url: string | null;
	title: string | null;
	author: string | null;
	summary: string | null;
	ai_summary: string | null;
	content_html: string | null;
	image_url: string | null;
	lang: string | null;
	word_count: number | null;
	tags: string[];
	published_at: string | null;
	is_read: boolean;
	is_saved: boolean;
	is_favorite: boolean;
}

export interface TrendingItem {
	article: Article;
	readers: number;
	avg_completion: number;
	avg_dwell_ms: number;
	score: number;
}

export interface RankedArticle {
	article: Article;
	readers: number;
	quality: number;
	saves: number;
	favorites: number;
	opens: number;
	score: number;
}

export interface Insights {
	trending_now: RankedArticle[];
	top: RankedArticle[];
	most_saved: RankedArticle[];
	deep_reads: RankedArticle[];
	hidden_gems: RankedArticle[];
}

export interface Page<T> {
	items: T[];
	next_cursor: string | null;
}

export interface DiscoveredFeed {
	feed_url: string;
	title: string | null;
}

export interface ApiError {
	error: { code: string; message: string };
}
