import { writable } from 'svelte/store';
import type { User } from '$lib/types';

const ACCESS = 'ufeed_access';
const REFRESH = 'ufeed_refresh';

const USER = 'ufeed_user';
const STEP_UP = 'ufeed_stepup';

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

/** Proof of the last one-time code (editors/admins). Per tab session on purpose:
 * closing the browser asks for a code again. */
export function getStepUp(): string | null {
	try {
		return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(STEP_UP) : null;
	} catch {
		return null;
	}
}

export function setStepUp(token: string | null) {
	try {
		if (token) sessionStorage.setItem(STEP_UP, token);
		else sessionStorage.removeItem(STEP_UP);
	} catch {
		/* blocked storage: the code is asked for on every reload */
	}
}

export function setTokens(access: string, refresh: string) {
	localStorage.setItem(ACCESS, access);
	localStorage.setItem(REFRESH, refresh);
	authed.set(true);
}

export function clearTokens() {
	setStepUp(null);
	localStorage.removeItem(ACCESS);
	localStorage.removeItem(REFRESH);
	// Unsynced offline changes belong to this session.
	localStorage.removeItem('ufeed_outbox');
	localStorage.removeItem('ufeed_outbox_ops');
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
