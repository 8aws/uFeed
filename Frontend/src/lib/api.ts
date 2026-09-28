import { get } from 'svelte/store';
import { clearTokens, getAccess, getRefresh, setTokens } from '$lib/auth';
import { locale } from '$lib/i18n';
import type {
	AISummary,
	Ban,
	SourceHealth,
	AdminSettings,
	AdminUser,
	ApiKey,
	ApiKeyCreated,
	Article,
	AuthResponse,
	DiscoveredFeed,
	Folder,
	Insights,
	Locale,
	Maintenance,
	MutedKeyword,
	Page,
	PlanLimits,
	Role,
	SiteConfig,
	Subscription,
	Tokens,
	TrendingItem,
	User
} from '$lib/types';

const BASE = '/api';

export class ApiError extends Error {
	code: string;
	status: number;
	/** Seconds to wait (from Retry-After), e.g. for plan refresh cooldowns. */
	retryAfter: number | null;
	constructor(status: number, code: string, message: string, retryAfter: number | null = null) {
		super(message);
		this.code = code;
		this.status = status;
		this.retryAfter = retryAfter;
	}
}

interface Options {
	method?: string;
	body?: unknown;
	auth?: boolean;
	retry?: boolean;
}

async function raw(path: string, opts: Options): Promise<Response> {
	const headers: Record<string, string> = { 'Accept-Language': get(locale) };
	if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
	if (opts.auth !== false) {
		const token = getAccess();
		if (token) headers['Authorization'] = `Bearer ${token}`;
	}
	return fetch(BASE + path, {
		method: opts.method ?? 'GET',
		headers,
		body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
	});
}

async function tryRefresh(): Promise<boolean> {
	const refresh_token = getRefresh();
	if (!refresh_token) return false;
	const resp = await raw('/auth/refresh', { method: 'POST', body: { refresh_token }, auth: false });
	if (!resp.ok) return false;
	const tokens = (await resp.json()) as Tokens;
	setTokens(tokens.access_token, tokens.refresh_token);
	return true;
}

async function request<T>(path: string, opts: Options = {}): Promise<T> {
	let resp = await raw(path, opts);
	if (resp.status === 401 && opts.auth !== false && opts.retry !== false) {
		if (await tryRefresh()) {
			resp = await raw(path, { ...opts, retry: false });
		} else {
			clearTokens();
		}
	}
	if (!resp.ok) {
		let code = `http_${resp.status}`;
		let message = resp.statusText;
		try {
			const data = await resp.json();
			if (data?.error) {
				code = data.error.code;
				message = data.error.message;
			}
		} catch {
			/* non-JSON error body */
		}
		const ra = Number(resp.headers.get('Retry-After'));
		throw new ApiError(resp.status, code, message, Number.isFinite(ra) && ra > 0 ? ra : null);
	}
	if (resp.status === 204) return undefined as T;
	return (await resp.json()) as T;
}

export const api = {
	// auth
	register: (email: string, password: string, locale?: Locale) =>
		request<AuthResponse>('/auth/register', {
			method: 'POST',
			body: { email, password, locale },
			auth: false
		}),
	login: (email: string, password: string) =>
		request<Tokens>('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
	me: () => request<User>('/me'),
	updateMe: (body: { locale?: Locale; display_name?: string | null }) =>
		request<User>('/me', { method: 'PATCH', body }),
	// Returns fresh tokens: other sessions are signed out.
	changePassword: (current_password: string, new_password: string) =>
		request<Tokens>('/me/password', { method: 'POST', body: { current_password, new_password } }),

	// API keys (for the public /api/v1 read-only API)
	listKeys: () => request<ApiKey[]>('/keys'),
	// "read" lists articles/sources; "state" lets the app mark articles read.
	createKey: (name: string, scopes: string[] = ['read', 'state']) =>
		request<ApiKeyCreated>('/keys', { method: 'POST', body: { name, scopes } }),
	revokeKey: (id: string) => request<unknown>(`/keys/${id}`, { method: 'DELETE' }),

	// site + admin
	site: () => request<SiteConfig>('/site', { auth: false }),
	adminSettings: () => request<AdminSettings>('/admin/settings'),
	updateAdminSettings: (body: {
		registration_open?: boolean;
		default_role?: Role;
		retention_days?: number;
		inactivity_days?: number;
		dormant_delete_days?: number;
	}) =>
		request<AdminSettings>('/admin/settings', { method: 'PATCH', body }),
	adminUsers: () => request<AdminUser[]>('/admin/users'),
	updatePlans: (plans: Partial<Record<Role, PlanLimits>>) =>
		request<AdminSettings>('/admin/plans', { method: 'PUT', body: plans }),
	updateAdminUser: (id: string, body: { role?: Role; is_active?: boolean }) =>
		request<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body }),
	adminResetPassword: (id: string) =>
		request<{ temporary_password: string }>(`/admin/users/${id}/reset-password`, {
			method: 'POST'
		}),
	adminMaintenance: () => request<Maintenance>('/admin/maintenance'),
	runRetention: () => request<Maintenance>('/admin/retention/run', { method: 'POST' }),
	runInactivity: () => request<Maintenance>('/admin/inactivity/run', { method: 'POST' }),
	// moderation
	suspendUser: (id: string, days: number) =>
		request<AdminUser>(`/admin/users/${id}/suspend`, { method: 'POST', body: { days } }),
	unsuspendUser: (id: string) =>
		request<AdminUser>(`/admin/users/${id}/suspend`, { method: 'DELETE' }),
	banUser: (id: string, days: number | null, reason?: string) =>
		request<AdminUser>(`/admin/users/${id}/ban`, { method: 'POST', body: { days, reason } }),
	reactivateUser: (id: string) =>
		request<AdminUser>(`/admin/users/${id}/reactivate`, { method: 'POST' }),
	unbanUser: (id: string) => request<AdminUser>(`/admin/users/${id}/ban`, { method: 'DELETE' }),
	deleteUser: (id: string) => request<unknown>(`/admin/users/${id}`, { method: 'DELETE' }),
	listBans: () => request<Ban[]>('/admin/bans'),
	createBan: (email: string, days: number | null, reason?: string) =>
		request<Ban>('/admin/bans', { method: 'POST', body: { email, days, reason } }),
	deleteBan: (id: string) => request<unknown>(`/admin/bans/${id}`, { method: 'DELETE' }),
	// feed health
	adminSources: () => request<SourceHealth[]>('/admin/sources'),
	pauseSource: (id: string, paused: boolean) =>
		request<unknown>(`/admin/sources/${id}`, { method: 'PATCH', body: { paused } }),
	deleteOrphanSources: () =>
		request<{ deleted: number }>('/admin/sources/delete-orphans', { method: 'POST' }),

	// folders
	listFolders: () => request<Folder[]>('/folders'),
	createFolder: (name: string) => request<Folder>('/folders', { method: 'POST', body: { name } }),
	deleteFolder: (id: string) => request<unknown>(`/folders/${id}`, { method: 'DELETE' }),

	// sources
	listSources: () => request<Subscription[]>('/sources'),
	aiSummary: (id: string, lang: string, generate = false) =>
		request<AISummary>(
			`/articles/${id}/ai-summary?lang=${encodeURIComponent(lang)}&generate=${generate}`
		),
	// muted keywords (hide matching articles)
	listKeywords: () => request<MutedKeyword[]>('/filters/keywords'),
	addKeyword: (keyword: string) =>
		request<MutedKeyword>('/filters/keywords', { method: 'POST', body: { keyword } }),
	removeKeyword: (id: string) => request<unknown>(`/filters/keywords/${id}`, { method: 'DELETE' }),
	sourcesHealth: () => request<SourceHealth[]>('/sources/health'),
	subscribe: (url: string, folder_id?: string | null) =>
		request<Subscription>('/sources', { method: 'POST', body: { url, folder_id } }),
	updateSubscription: (
		id: string,
		body: { folder_id?: string | null; custom_title?: string; muted?: boolean }
	) =>
		request<Subscription>(`/sources/${id}`, { method: 'PATCH', body }),
	unsubscribe: (id: string) => request<unknown>(`/sources/${id}`, { method: 'DELETE' }),
	// Opportunistic fetch of this user's due feeds when the app opens.
	sync: () =>
		request<{ checked: number; new_articles: number; errors: number; skipped: boolean }>(
			'/sync',
			{ method: 'POST' }
		),
	refresh: (source?: string) =>
		request<{ checked: number; new_articles: number; errors: number }>(
			`/refresh${source ? `?source=${source}` : ''}`,
			{ method: 'POST' }
		),
	discover: (url: string) =>
		request<DiscoveredFeed[]>('/discover', { method: 'POST', body: { url } }),

	// articles
	listArticles: (params: Record<string, string>) => {
		const qs = new URLSearchParams(params).toString();
		return request<Page<Article>>(`/articles${qs ? `?${qs}` : ''}`);
	},
	setRead: (id: string, read: boolean) =>
		request<unknown>(`/articles/${id}/read`, { method: read ? 'POST' : 'DELETE' }),
	setSaved: (id: string, saved: boolean) =>
		request<unknown>(`/articles/${id}/save`, { method: saved ? 'POST' : 'DELETE' }),
	setFavorite: (id: string, favorite: boolean) =>
		request<unknown>(`/articles/${id}/favorite`, { method: favorite ? 'POST' : 'DELETE' }),
	markAllRead: (folder_id?: string | null, source_id?: string | null) =>
		request<unknown>('/articles/mark-all-read', {
			method: 'POST',
			body: { folder_id, source_id }
		}),
	readEvent: (id: string, dwell_ms: number, completion: number) =>
		request<unknown>(`/articles/${id}/read-event`, {
			method: 'POST',
			body: { dwell_ms, completion }
		}),
	engage: (id: string, kind: 'open' | 'share' | 'skip') =>
		request<unknown>(`/articles/${id}/engage`, { method: 'POST', body: { kind } }),
	trending: (window_hours = 720, limit = 8) =>
		request<TrendingItem[]>(`/trending?window_hours=${window_hours}&limit=${limit}`),
	insights: (window_hours = 720, limit = 12) =>
		request<Insights>(`/insights?window_hours=${window_hours}&limit=${limit}`),
	forYou: (limit = 30) => request<Article[]>(`/foryou?limit=${limit}`),
	similar: (id: string, limit = 6) => request<Article[]>(`/articles/${id}/similar?limit=${limit}`)
};

/** OPML export needs the auth header, so fetch as a blob and trigger a download. */
export async function downloadOpml() {
	const resp = await raw('/opml/export', {});
	if (!resp.ok) throw new ApiError(resp.status, 'export_failed', 'Export failed');
	const blob = await resp.blob();
	const href = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = href;
	a.download = 'ufeed.opml';
	a.click();
	URL.revokeObjectURL(href);
}

export async function importOpml(file: File): Promise<{ imported: number; skipped: number }> {
	const form = new FormData();
	form.append('file', file);
	const headers: Record<string, string> = {};
	const token = getAccess();
	if (token) headers['Authorization'] = `Bearer ${token}`;
	const resp = await fetch(`${BASE}/opml/import`, { method: 'POST', headers, body: form });
	if (!resp.ok) throw new ApiError(resp.status, 'import_failed', 'Import failed');
	return resp.json();
}
