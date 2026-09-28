// Offline outbox for article state (read / saved / favourite).
//
// A change is applied to the UI at once and sent to the server; if the network
// is down (or the server hiccups) it is kept here, in localStorage, and sent
// later: when the connection comes back, when the app is opened again or
// returns to the foreground. Only the latest value per article+field is kept,
// so toggling back and forth offline sends a single request (or none).

import { writable } from 'svelte/store';
import { api, ApiError } from '$lib/api';
import type { Article } from '$lib/types';

export type Field = 'read' | 'saved' | 'favorite';
interface Entry {
	id: string;
	field: Field;
	value: boolean;
	at: number;
}

const KEY = 'ufeed_outbox';
const MAX_AGE_MS = 30 * 24 * 3600 * 1000; // older changes are dropped

/** Number of changes waiting to be sent (for a small indicator). */
export const pendingCount = writable(0);

function load(): Record<string, Entry> {
	try {
		const raw = localStorage.getItem(KEY);
		return raw ? (JSON.parse(raw) as Record<string, Entry>) : {};
	} catch {
		return {};
	}
}

function store(q: Record<string, Entry>) {
	try {
		if (Object.keys(q).length) localStorage.setItem(KEY, JSON.stringify(q));
		else localStorage.removeItem(KEY);
	} catch {
		/* storage blocked: changes just won't survive a reload */
	}
	pendingCount.set(Object.keys(q).length);
}

const key = (id: string, field: Field) => `${id}:${field}`;

function send(e: Pick<Entry, 'id' | 'field' | 'value'>): Promise<unknown> {
	if (e.field === 'read') return api.setRead(e.id, e.value);
	if (e.field === 'saved') return api.setSaved(e.id, e.value);
	return api.setFavorite(e.id, e.value);
}

/** Worth retrying later: no network, offline reply, rate limit or server error.
 *  Anything else (e.g. 404: the article was purged) will never succeed. */
function retriable(err: unknown): boolean {
	if (!(err instanceof ApiError)) return true; // fetch threw: no connection
	return err.code === 'offline' || err.status === 429 || err.status >= 500;
}

/** Send a change now, or queue it if that isn't possible right now.
 *  Throws only for permanent failures (the caller may undo the UI change). */
export async function setState(id: string, field: Field, value: boolean): Promise<'sent' | 'queued'> {
	const q = load();
	delete q[key(id, field)]; // a newer value supersedes anything queued
	store(q);
	try {
		await send({ id, field, value });
		return 'sent';
	} catch (err) {
		if (!retriable(err)) throw err;
		const q2 = load();
		q2[key(id, field)] = { id, field, value, at: Date.now() };
		store(q2);
		return 'queued';
	}
}

let flushing: Promise<number> | null = null;

/** Send everything queued, oldest first. Stops at the first failure that is
 *  worth retrying (the network is probably still down). Returns how many
 *  changes reached the server. */
export function flush(): Promise<number> {
	flushing ??= (async () => {
		let sent = 0;
		try {
			const entries = Object.values(load()).sort((a, b) => a.at - b.at);
			for (const e of entries) {
				if (Date.now() - e.at > MAX_AGE_MS) {
					drop(e);
					continue;
				}
				try {
					await send(e);
					sent++;
					drop(e);
				} catch (err) {
					if (retriable(err)) break;
					drop(e);
				}
			}
		} finally {
			flushing = null;
		}
		return sent;
	})();
	return flushing;
}

function drop(e: Entry) {
	const q = load();
	// Only if it wasn't replaced by a newer change meanwhile.
	if (q[key(e.id, e.field)]?.at === e.at) {
		delete q[key(e.id, e.field)];
		store(q);
	}
}

/** Overlay queued changes on articles fetched from the server, so a post read
 *  offline doesn't come back as unread before the change is synced. */
export function applyPending(items: Article[]): Article[] {
	const q = load();
	if (!Object.keys(q).length) return items;
	for (const a of items) {
		const r = q[key(a.id, 'read')];
		const s = q[key(a.id, 'saved')];
		const f = q[key(a.id, 'favorite')];
		if (r) a.is_read = r.value;
		if (s) a.is_saved = s.value;
		if (f) a.is_favorite = f.value;
	}
	return items;
}

/** Forget queued changes (on logout: they belong to that session). */
export function clearOutbox() {
	store({});
}

/** Initialise the counter from what's stored (e.g. after a reload). */
export function initOutbox() {
	pendingCount.set(Object.keys(load()).length);
}
