/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `ufeed-${version}`;
// .woff duplicates the .woff2 fonts for very old browsers: not worth precaching.
const ASSETS = [...build, ...files].filter((f) => !f.endsWith('.woff'));

// Offline reading of saved articles (kept across deploys; cleared on logout).
const API_CACHE = 'ufeed-offline-api';
const IMG_CACHE = 'ufeed-offline-img';
const IMG_MAX = 150;
const SAVED_KEY = '/__offline/saved';
// Server-voice recordings of saved articles (see lib/offlineAudio.ts).
const AUDIO_CACHE = 'ufeed-offline-audio';
// Enough of the API for the app shell to open offline.
const SHELL_API = new Set(['/api/me', '/api/sources', '/api/folders', '/api/site']);

sw.addEventListener('install', (event) => {
	// '/' is the SPA shell, needed to open the app offline.
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll([...ASSETS, '/']))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) =>
				Promise.all(
					keys
						.filter((k) => k !== CACHE && !k.startsWith('ufeed-offline'))
						.map((k) => caches.delete(k))
				)
			)
			.then(() => sw.clients.claim())
	);
});

function offlineError(): Response {
	return new Response(JSON.stringify({ error: { code: 'offline', message: 'Offline' } }), {
		status: 503,
		headers: { 'content-type': 'application/json' }
	});
}

// A connection that is up but crawling (a cold start on mobile data, a
// sleepy NAS proxy) must not leave the app blank: after this long the cached
// copy is served and the network response still refreshes the cache.
const NAV_TIMEOUT_MS = 3000;
const API_TIMEOUT_MS = 4000;

/** Resolve with the network response, or with the cached `fallback` if the
 *  network fails or takes longer than `ms` (when a cached copy exists). */
async function raceNetwork(
	network: Promise<Response>,
	cached: () => Promise<Response | undefined>,
	ms: number
): Promise<Response | undefined> {
	return new Promise((resolve) => {
		let done = false;
		const finish = (r: Response | undefined) => {
			if (!done && r) {
				done = true;
				resolve(r);
			}
		};
		const timer = setTimeout(() => cached().then(finish), ms);
		network.then(
			(r) => {
				clearTimeout(timer);
				finish(r);
			},
			async () => {
				clearTimeout(timer);
				const c = await cached();
				if (c) finish(c);
				else if (!done) {
					done = true;
					resolve(undefined);
				}
			}
		);
	});
}

/** Network first; on success optionally refresh the cached copy under `store`,
 *  on failure (or a very slow network) serve the copy under `fallback`. */
async function networkFirst(event: FetchEvent, fallback: string, store: string | null) {
	const cache = await caches.open(API_CACHE);
	const network = fetch(event.request).then(async (resp) => {
		if (resp.ok && store) await cache.put(store, resp.clone());
		return resp;
	});
	event.waitUntil(network.catch(() => {}));
	return (await raceNetwork(network, () => cache.match(fallback), API_TIMEOUT_MS)) ?? offlineError();
}

/** A stored recording, honouring Range (iOS plays audio only via ranges);
 *  otherwise the network. Recordings never change, so the copy always wins. */
async function audio(req: Request): Promise<Response> {
	const cache = await caches.open(AUDIO_CACHE);
	const hit = await cache.match(new URL(req.url).pathname);
	if (!hit) return fetch(req);
	const range = req.headers.get('range');
	if (!range) return hit;
	const buf = await hit.arrayBuffer();
	const m = /bytes=(\d*)-(\d*)/.exec(range);
	const size = buf.byteLength;
	let start = m?.[1] ? Number(m[1]) : 0;
	let end = m?.[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
	if (!m?.[1] && m?.[2]) {
		// Suffix range: the last N bytes.
		start = Math.max(0, size - Number(m[2]));
		end = size - 1;
	}
	if (start >= size || start > end) {
		return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}` } });
	}
	return new Response(buf.slice(start, end + 1), {
		status: 206,
		headers: {
			'Content-Type': 'audio/mpeg',
			'Content-Range': `bytes ${start}-${end}/${size}`,
			'Content-Length': String(end - start + 1),
			'Accept-Ranges': 'bytes'
		}
	});
}

async function trim(cache: Cache, max: number) {
	const keys = await cache.keys();
	for (const k of keys.slice(0, Math.max(0, keys.length - max))) await cache.delete(k);
}

// The page asks us to keep a saved article's images for offline reading.
sw.addEventListener('message', (event) => {
	const data = event.data as { type?: string; urls?: string[] } | null;
	if (data?.type !== 'cache-images' || !Array.isArray(data.urls)) return;
	event.waitUntil(
		(async () => {
			const cache = await caches.open(IMG_CACHE);
			for (const url of data.urls!.slice(0, IMG_MAX)) {
				if (!/^https?:\/\//.test(url) || (await cache.match(url))) continue;
				try {
					const resp = await fetch(url, { mode: 'no-cors' });
					if (resp.ok || resp.type === 'opaque') await cache.put(url, resp);
				} catch {
					/* skip unreachable images */
				}
			}
			await trim(cache, IMG_MAX);
		})()
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);

	if (url.origin === location.origin && url.pathname.startsWith('/api')) {
		// Saved list: the page's warm-up request (offline=1) refreshes the copy;
		// any saved list request falls back to it when there's no network.
		if (url.pathname === '/api/articles' && url.searchParams.get('saved') === 'true') {
			const store = url.searchParams.get('offline') === '1' ? SAVED_KEY : null;
			event.respondWith(networkFirst(event, SAVED_KEY, store));
			return;
		}
		if (url.pathname.startsWith('/api/audio/')) {
			event.respondWith(audio(req));
			return;
		}
		if (SHELL_API.has(url.pathname)) {
			event.respondWith(networkFirst(event, url.pathname, url.pathname));
			return;
		}
		return; // everything else: network only
	}

	// Images of saved articles (cached on request by the page) work offline.
	if (req.destination === 'image') {
		event.respondWith(
			caches
				.open(IMG_CACHE)
				.then((c) => c.match(req.url))
				.then((hit) => hit ?? fetch(req))
		);
		return;
	}

	// Navigations: network-first so a new deploy is picked up immediately;
	// fall back to the cached app shell when offline or the network stalls.
	if (req.mode === 'navigate') {
		const network = fetch(req);
		event.waitUntil(network.catch(() => {}));
		event.respondWith(
			raceNetwork(network, () => caches.match('/'), NAV_TIMEOUT_MS).then((r) => r ?? network)
		);
		return;
	}

	// Static assets (hashed, immutable): cache-first.
	event.respondWith(
		caches.match(req).then(
			(cached) =>
				cached ??
				fetch(req).then((resp) => {
					if (resp.ok && url.origin === location.origin) {
						const copy = resp.clone();
						caches.open(CACHE).then((cache) => cache.put(req, copy));
					}
					return resp;
				})
		) as Promise<Response>
	);
});
