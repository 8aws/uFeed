import { writable } from 'svelte/store';
import type { User } from '$lib/types';

const ACCESS = 'ufeed_access';
const REFRESH = 'ufeed_refresh';

const USER = 'ufeed_user';

// Last known profile, so the app can paint at once on a cold start and
// refresh it from the server in the background.
function cachedUser(): User | null {
	try {
		const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(USER) : null;
		return raw ? (JSON.parse(raw) as User) : null;
	} catch {
		return null;
	}
}

export const user = writable<User | null>(cachedUser());
user.subscribe((u) => {
	if (typeof localStorage === 'undefined') return;
	try {
		if (u) localStorage.setItem(USER, JSON.stringify(u));
		else localStorage.removeItem(USER);
	} catch {
		/* storage full or blocked: the cache is optional */
	}
});
export const authed = writable<boolean>(
	typeof localStorage !== 'undefined' && !!localStorage.getItem(ACCESS)
);

export function getAccess(): string | null {
	return typeof localStorage !== 'undefined' ? localStorage.getItem(ACCESS) : null;
}

export function getRefresh(): string | null {
	return typeof localStorage !== 'undefined' ? localStorage.getItem(REFRESH) : null;
}

export function setTokens(access: string, refresh: string) {
	localStorage.setItem(ACCESS, access);
	localStorage.setItem(REFRESH, refresh);
	authed.set(true);
}

export function clearTokens() {
	localStorage.removeItem(ACCESS);
	localStorage.removeItem(REFRESH);
	localStorage.removeItem('ufeed_outbox'); // unsynced changes of this session
	// Offline copies (saved articles, images) belong to this session only.
	if (typeof caches !== 'undefined') {
		caches
			.keys()
			.then((keys) => keys.filter((k) => k.startsWith('ufeed-offline')).forEach((k) => caches.delete(k)))
			.catch(() => {});
	}
	user.set(null);
	authed.set(false);
}

export function isAuthed(): boolean {
	return !!getAccess();
}
