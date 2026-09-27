export type Locale = 'en' | 'es';

export type Role = 'free' | 'general' | 'vip' | 'editor' | 'admin';

export interface User {
	id: string;
	email: string;
	display_name: string | null;
	locale: Locale;
	role: Role;
	is_active: boolean;
	must_change_password: boolean;
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
	error_count: number;
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
	dup_count: number;
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

/** API key metadata (the secret is never returned after creation). */
export interface ApiKey {
	id: string;
	name: string;
	prefix: string;
	scopes: string[];
	last_used_at: string | null;
	created_at: string;
	revoked_at: string | null;
}

/** Returned once, at creation, with the plaintext key. */
export interface ApiKeyCreated extends ApiKey {
	key: string;
}

/** Unauthenticated instance info. */
export interface SiteConfig {
	registration_open: boolean;
	refresh_cooldown_s: Record<Role, number>;
}

export interface AdminSettings {
	registration_open: boolean;
	default_role: Role;
	retention_days: number;
	inactivity_days: number;
	roles: Role[];
	refresh_cooldown_s: Record<Role, number>;
}

export interface AdminUser {
	id: string;
	email: string;
	display_name: string | null;
	role: Role;
	is_active: boolean;
	created_at: string;
	feeds: number;
	suspended_until: string | null;
	last_activity_at: string | null;
	banned: boolean;
	ban_until: string | null;
}

export interface BackupStatus {
	at: string;
	ok: boolean;
	error: string | null;
	file: string | null;
	size_bytes: number;
	local_count: number;
	keep: number;
	mirror: {
		enabled: boolean;
		dir?: string;
		ok?: boolean;
		error?: string | null;
		count?: number;
		keep?: number;
	};
}

export interface Maintenance {
	retention_days: number;
	last_purge: {
		at: string;
		days: number;
		deleted_articles: number;
		deleted_events: number;
	} | null;
	db_size_bytes: number;
	articles: number;
	backups: BackupStatus | null;
	inactivity_days: number;
	last_inactive_cleanup: { at: string; days: number; deleted_users: number } | null;
}

export type HealthStatus = 'ok' | 'retrying' | 'failing' | 'stale' | 'pending' | 'paused';

export interface SourceHealth {
	source_id: string;
	subscription_id: string | null;
	title: string | null;
	feed_url: string;
	site_url: string | null;
	status: HealthStatus;
	error_count: number;
	last_error: string | null;
	last_error_at: string | null;
	last_fetch_at: string | null;
	last_article_at: string | null;
	subscribers: number;
}

export interface Ban {
	id: string;
	email: string;
	until: string | null;
	reason: string | null;
	created_at: string;
}
