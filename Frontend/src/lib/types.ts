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
	muted: boolean;
}

/** On-demand LLM summary of an article in one language. */
export interface AISummary {
	lang: string;
	summary: string | null;
	title: string | null; // translated headline (article in another language)
	model: string | null;
	cached: boolean;
}

export interface MutedKeyword {
	id: string;
	keyword: string;
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
	fetched_at?: string | null;
	full_status?: string | null; // "ok": full text from the web page available
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

export interface PlanLimits {
	refresh_cooldown_s: number;
	max_feeds: number | null; // null = unlimited
	max_api_keys: number | null; // null = unlimited
	ai_features: boolean;
	tts_server?: boolean; // "listen" with the server's neural voice
	post_radio?: boolean; // Post radio (posts read one after another)
	radio_max_posts?: number | null; // per session; null = unlimited
	radio_max_minutes?: number | null;
}

/** Unauthenticated instance info. */
export interface SiteConfig {
	registration_open: boolean;
	refresh_cooldown_s: Record<Role, number>;
	plan_limits: Record<Role, PlanLimits>;
	contact_email?: string; // public privacy/support pages
}

export interface AdminSettings {
	registration_open: boolean;
	default_role: Role;
	retention_days: number;
	inactivity_days: number;
	dormant_delete_days: number;
	contact_email?: string;
	roles: Role[];
	refresh_cooldown_s: Record<Role, number>;
	plan_limits: Record<Role, PlanLimits>;
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
	dormant_since: string | null;
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
		encrypted?: boolean;
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
	dormant_delete_days: number;
	last_inactive_cleanup: {
		at: string;
		days: number;
		delete_days: number;
		deactivated_users: number;
		deleted_users: number;
	} | null;
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

export interface CatalogResponse {
	/** null: the app's built-in starter list applies. */
	sections: import('$lib/catalog').CatalogSection[] | null;
	updated_at: string | null;
}

export interface HiddenArticle {
	article: Article;
	hidden_at: string;
	hidden_by: string | null;
}

/** An article machine-translated into the reader's language. */
export interface Translation {
	lang: string;
	source_lang: string;
	title: string | null;
	paragraphs: string[] | null; // null until generated
	cached: boolean;
}

/** Admin resource monitor (samples every 15 min + daily heavy-work usage). */
export interface MetricPoint {
	ts: string;
	cpus?: number;
	load1?: number;
	mem_total_mb?: number;
	mem_used_mb?: number;
	ai_rss_mb?: number | null;
	ai_ok?: boolean;
	db_mb?: number;
	tts_cache_mb?: number;
	users?: number;
	active_24h?: number;
	active_7d?: number;
	articles?: number;
}
export interface UsageDay {
	day: string;
	[key: string]: number | string; // tts_n, tts_ms, tts_bytes, mt_n, mt_ms, llm_n, llm_ms
}
export interface Metrics {
	samples: MetricPoint[];
	daily: UsageDay[];
	now: { cpus?: number; load1?: number; mem_total_mb?: number; mem_used_mb?: number };
}
