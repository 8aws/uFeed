// Freeze diagnostics (temporary, to find why taps sometimes stop working
// while scrolling still does).
//
// While the app runs, a small log is kept in localStorage: a heartbeat every
// 2 s with what's on screen, taps that never became a click, and pauses of the
// page longer than 3 s. If the page freezes, the heartbeat stops and the log
// says when and where. On the next start the previous session's log is sent
// to the server (POST /me/diag) when it shows any of that.

import { api } from '$lib/api';

const KEY = 'ufeed_diag';
const MAX_EVENTS = 80;

type Event = { k: string; t: number } & Record<string, unknown>;
interface Log {
	session: string;
	start: number;
	beat: number;
	ctx: Record<string, unknown>;
	events: Event[];
}

let log: Log | null = null;
let context: () => Record<string, unknown> = () => ({});

function push(k: string, extra: Record<string, unknown> = {}) {
	if (!log) return;
	log.events.push({ k, t: Date.now(), ...extra });
	if (log.events.length > MAX_EVENTS) log.events.splice(0, log.events.length - MAX_EVENTS);
	save();
}

function save() {
	if (!log) return;
	try {
		localStorage.setItem(KEY, JSON.stringify(log));
	} catch {
		/* storage blocked: nothing to keep */
	}
}

function describe(el: EventTarget | null): string {
	const e = el instanceof Element ? el : null;
	const hit = e?.closest('button, a, [role="button"], input, .reader, .acard') ?? e;
	if (!hit) return '?';
	const label = hit.getAttribute('aria-label') || hit.getAttribute('title') || hit.className || '';
	return `${hit.tagName} ${String(label).slice(0, 40)}`;
}

/** Worth reporting: the page paused, or taps went unanswered. */
function suspicious(l: Log): boolean {
	return l.events.some((e) => e.k === 'stall' || e.k === 'lost');
}

async function sendPrevious() {
	let prev: Log | null = null;
	try {
		prev = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Log | null;
	} catch {
		prev = null;
	}
	if (!prev || !suspicious(prev)) return;
	try {
		await api.sendDiag({
			events: prev.events,
			context: { ...prev.ctx, session: prev.session, start: prev.start, lastBeat: prev.beat, ua: navigator.userAgent }
		});
	} catch {
		/* offline: it'll go with the next start's report if it repeats */
	}
}

/** Start logging; `ctx` describes what's on screen (reader open, scroll…). */
export function startDiag(ctx: () => Record<string, unknown>) {
	if (log || typeof window === 'undefined') return;
	context = ctx;
	void sendPrevious().finally(() => {
		log = { session: Math.random().toString(36).slice(2, 8), start: Date.now(), beat: Date.now(), ctx: {}, events: [] };
		save();
	});

	// Heartbeat + pause detector.
	let last = Date.now();
	setInterval(() => {
		const now = Date.now();
		if (document.visibilityState === 'visible' && now - last > 3000) push('stall', { ms: now - last });
		last = now;
	}, 1000);
	setInterval(() => {
		if (!log || document.visibilityState !== 'visible') return;
		log.beat = Date.now();
		try {
			log.ctx = context();
		} catch {
			log.ctx = {};
		}
		save();
	}, 2000);
	document.addEventListener('visibilitychange', () => {
		last = Date.now(); // timers sleep in the background: not a stall
		push('vis', { s: document.visibilityState });
	});

	// A tap (pointerdown + pointerup, no scroll) that never produced a click.
	let pending: { t: number; target: string } | null = null;
	let timer: ReturnType<typeof setTimeout> | undefined;
	window.addEventListener(
		'pointerdown',
		(e) => {
			if (e.pointerType !== 'mouse') pending = { t: Date.now(), target: describe(e.target) };
		},
		{ capture: true, passive: true }
	);
	window.addEventListener('pointercancel', () => (pending = null), { capture: true, passive: true });
	window.addEventListener(
		'pointerup',
		() => {
			if (!pending) return;
			const p = pending;
			clearTimeout(timer);
			timer = setTimeout(() => {
				if (pending === p) {
					push('lost', { target: p.target, held: Date.now() - p.t });
					pending = null;
				}
			}, 1000);
		},
		{ capture: true, passive: true }
	);
	window.addEventListener(
		'click',
		(e) => {
			pending = null;
			push('click', { target: describe(e.target) });
		},
		{ capture: true, passive: true }
	);
}
