import { writable } from 'svelte/store';
import type { User } from '$lib/types';

const ACCESS = 'ufeed_access';
const REFRESH = 'ufeed_refresh';

export const user = writable<User | null>(null);
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
