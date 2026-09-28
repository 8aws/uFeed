// Offline outbox.
//
// Two kinds of changes are applied to the UI at once and sent to the server;
// if the network is down (or the server hiccups) they are kept here, in
// localStorage, and sent later: when the connection comes back, when the app
// is opened again or returns to the foreground.
//
// - Article state (read / saved / favourite): only the latest value per
//   article+field is kept, so toggling offline sends one request (or none).
// - Operations (mark all read, reading stats: dwell/completion, open, share,
//   skip): kept in order, each with the moment it happened, which the server
//   uses (a late "mark all" doesn't swallow newer posts; late stats don't
//   inflate "trending now").
// Both queues are sent together in chronological order, so "mark all read"
// followed by "mark this one unread" ends up right.

import { writable } from 'svelte/store';
import { api, ApiError } from '$lib/api';
import type { Article } from '$lib/types';

export type Field = 'read' | 'saved' | 'favorite';
interface StateEntry {
	id: string;
	field: Field;
	value: boolean;
	at: number;
}
export type Op =
	| { type: 'markAll'; folder_id: string | null; source_id: string | null }
	| { type: 'readEvent'; id: string; dwell_ms: number; completion: number }
	| { type: 'engage'; id: string; kind: 'open' | 'share' | 'skip' };
type OpEntry = Op & { at: number };

const KEY = 'ufeed_outbox';
const OPS_KEY = 'ufeed_outbox_ops';
const MAX_AGE_MS = 30 * 24 * 3600 * 1000; // older changes are dropped
const MAX_OPS = 300; // stats beyond this are dropped oldest-first

/** Number of changes waiting to be sent (for a small indicator). */
export const pendingCount = writable(0);

function read<T>(k: string, empty: T): T {
	try {
		const raw = localStorage.getItem(k);
		return raw ? (JSON.parse(raw) as T) : empty;
	} catch {
		return empty;
	}
}
function write(k: string, v: unknown, isEmpty: boolean) {
	try {
		if (isEmpty) localStorage.removeItem(k);
		else localStorage.setItem(k, JSON.stringify(v));
	} catch {
		/* storage blocked: changes just won't survive a reload */
	}
}

const loadStates = () => read<Record<string, StateEntry>>(KEY, {});
const loadOps = () => read<OpEntry[]>(OPS_KEY, []);
function saveStates(q: Record<string, StateEntry>) {
	write(KEY, q, !Object.keys(q).length);
	updateCount();
}
function saveOps(ops: OpEntry[]) {
	write(OPS_KEY, ops, !ops.length);
	updateCount();
}
function updateCount() {
	pendingCount.set(Object.keys(loadStates()).length + loadOps().length);
}

const key = (id: string, field: Field) => `${id}:${field}`;
const iso = (t: number) => new Date(t).toISOString();

function sendState(e: StateEntry): Promise<unknown> {
	if (e.field === 'read') return api.setRead(e.id, e.value);
	if (e.field === 'saved') return api.setSaved(e.id, e.value);
	return api.setFavorite(e.id, e.value);
}

/** `late`: sent from the queue, so it carries the moment it happened; sent
 *  right away it doesn't, and the server's clock applies (no device skew). */
function sendOp(o: OpEntry, late: boolean): Promise<unknown> {
	const at = late ? iso(o.at) : undefined;
	if (o.type === 'markAll') return api.markAllRead(o.folder_id, o.source_id, at);
	if (o.type === 'readEvent') return api.readEvent(o.id, o.dwell_ms, o.completion, at);
	return api.engage(o.id, o.kind, at);
}

/** Worth retrying later: no network, offline reply, rate limit or server error.
 *  Anything else (e.g. 404: the article was purged) will never succeed. */
function retriable(err: unknown): boolean {
	if (!(err instanceof ApiError)) return true; // fetch threw: no connection
	return err.code === 'offline' || err.status === 429 || err.status >= 500;
}

/** Send a state change now, or queue it if that isn't possible right now.
 *  Throws only for permanent failures (the caller may undo the UI change). */
export async function setState(id: string, field: Field, value: boolean): Promise<'sent' | 'queued'> {
	const q = loadStates();
	delete q[key(id, field)]; // a newer value supersedes anything queued
	saveStates(q);
	const entry = { id, field, value, at: Date.now() };
	// With an older operation still queued (e.g. an offline "mark all read"),
	// sending this now would apply it out of order: queue it behind.
	if (!loadOps().length) {
		try {
			await sendState(entry);
			return 'sent';
		} catch (err) {
			if (!retriable(err)) throw err;
		}
	}
	const q2 = loadStates();
	q2[key(id, field)] = entry;
	saveStates(q2);
	scheduleFlush();
	return 'queued';
}

/** Send an operation now, or queue it if that isn't possible right now.
 *  Permanent failures are dropped (stats of a purged article, etc.). */
export async function runOp(op: Op): Promise<'sent' | 'queued' | 'dropped'> {
	const entry = { ...op, at: Date.now() } as OpEntry;
	const behind = loadOps().length > 0 || Object.keys(loadStates()).length > 0;
	if (!behind) {
		try {
			await sendOp(entry, false);
			return 'sent';
		} catch (err) {
			if (!retriable(err)) return 'dropped';
		}
	}
	let ops = [...loadOps(), entry];
	if (ops.length > MAX_OPS) {
		// Drop the oldest stats first; "mark all read" is worth keeping.
		const extra = ops.length - MAX_OPS;
		let dropped = 0;
		ops = ops.filter((o) => {
			if (o.type === 'markAll' || dropped >= extra) return true;
			dropped++;
			return false;
		});
	}
	saveOps(ops);
	scheduleFlush();
	return 'queued';
}

let flushing: Promise<number> | null = null;
let flushTimer: ReturnType<typeof setTimeout> | undefined;

/** Queued while online (a server hiccup, or behind older queued changes):
 *  try again shortly instead of waiting for the next periodic retry. */
function scheduleFlush() {
	if (flushTimer || typeof navigator === 'undefined' || !navigator.onLine) return;
	flushTimer = setTimeout(() => {
		flushTimer = undefined;
		flush().catch(() => {});
	}, 3000);
}

/** Send everything queued, oldest first. Stops at the first failure that is
 *  worth retrying (the network is probably still down). Returns how many
 *  changes reached the server. */
export function flush(): Promise<number> {
	flushing ??= (async () => {
		let sent = 0;
		try {
			type Item = { at: number; state?: StateEntry; op?: OpEntry };
			const items: Item[] = [
				...Object.values(loadStates()).map((e) => ({ at: e.at, state: e })),
				...loadOps().map((o) => ({ at: o.at, op: o }))
			].sort((a, b) => a.at - b.at);
			for (const it of items) {
				const expired = Date.now() - it.at > MAX_AGE_MS;
				try {
					if (!expired) {
						await (it.state ? sendState(it.state) : sendOp(it.op!, true));
						sent++;
					}
				} catch (err) {
					if (retriable(err)) break;
				}
				if (it.state) dropState(it.state);
				else dropOp(it.op!);
			}
		} finally {
			flushing = null;
		}
		return sent;
	})();
	return flushing;
}

function dropState(e: StateEntry) {
	const q = loadStates();
	// Only if it wasn't replaced by a newer change meanwhile.
	if (q[key(e.id, e.field)]?.at === e.at) {
		delete q[key(e.id, e.field)];
		saveStates(q);
	}
}

function dropOp(o: OpEntry) {
	const ops = loadOps();
	const i = ops.findIndex((x) => x.at === o.at && x.type === o.type);
	if (i >= 0) {
		ops.splice(i, 1);
		saveOps(ops);
	}
}

/** Overlay queued changes on articles fetched from the server, so a post read
 *  offline doesn't come back as unread before the change is synced. */
export function applyPending(items: Article[]): Article[] {
	const q = loadStates();
	const marks = loadOps().filter((o): o is Extract<OpEntry, { type: 'markAll' }> => o.type === 'markAll');
	if (!Object.keys(q).length && !marks.length) return items;
	for (const a of items) {
		// A queued "mark all read" covers what had arrived when it was pressed
		// (individual changes made after it still win, below).
		const fetched = new Date(a.fetched_at ?? a.published_at ?? 0).getTime();
		let markedAt = 0;
		for (const m of marks) {
			if (fetched > m.at) continue;
			if (m.source_id && a.source_id !== m.source_id) continue;
			if (m.folder_id && !m.source_id && folderOf(a.source_id) !== m.folder_id) continue;
			markedAt = Math.max(markedAt, m.at);
		}
		if (markedAt) a.is_read = true;
		const r = q[key(a.id, 'read')];
		const s = q[key(a.id, 'saved')];
		const f = q[key(a.id, 'favorite')];
		if (r && r.at > markedAt) a.is_read = r.value;
		if (s) a.is_saved = s.value;
		if (f) a.is_favorite = f.value;
	}
	return items;
}

// Source -> folder lookup for folder-scoped "mark all read" (set by the page).
let folderOf: (sourceId: string) => string | null = () => null;
export function setFolderLookup(fn: (sourceId: string) => string | null) {
	folderOf = fn;
}

/** Initialise the counter from what's stored (e.g. after a reload). */
export function initOutbox() {
	updateCount();
}
