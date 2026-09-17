import { get } from 'svelte/store';
import { clearTokens, getAccess, getRefresh, setTokens } from '$lib/auth';
import { locale } from '$lib/i18n';
import type {
	Article,
	AuthResponse,
	DiscoveredFeed,
	Folder,
	Locale,
	Page,
	Subscription,
	Tokens,
	TrendingItem,
	User
} from '$lib/types';

const BASE = '/api';

export class ApiError extends Error {
	code: string;
	status: number;
	constructor(status: number, code: string, message: string) {
		super(message);
		this.code = code;
		this.status = status;
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
		throw new ApiError(resp.status, code, message);
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
	updateMe: (locale: Locale) => request<User>('/me', { method: 'PATCH', body: { locale } }),

	// folders
	listFolders: () => request<Folder[]>('/folders'),
	createFolder: (name: string) => request<Folder>('/folders', { method: 'POST', body: { name } }),
	deleteFolder: (id: string) => request<unknown>(`/folders/${id}`, { method: 'DELETE' }),

	// sources
	listSources: () => request<Subscription[]>('/sources'),
	subscribe: (url: string, folder_id?: string | null) =>
		request<Subscription>('/sources', { method: 'POST', body: { url, folder_id } }),
	unsubscribe: (id: string) => request<unknown>(`/sources/${id}`, { method: 'DELETE' }),
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
	trending: (window_hours = 48, limit = 8) =>
		request<TrendingItem[]>(`/trending?window_hours=${window_hours}&limit=${limit}`)
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
