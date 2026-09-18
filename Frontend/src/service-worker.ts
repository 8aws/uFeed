/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `ufeed-${version}`;
const ASSETS = [...build, ...files];

sw.addEventListener('install', (event) => {
	event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => sw.skipWaiting()));
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => sw.clients.claim())
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);
	// Never cache API traffic; always hit the network.
	if (url.pathname.startsWith('/api')) return;

	// Navigations: network-first so a new deploy is picked up immediately;
	// fall back to the cached app shell only when offline.
	if (req.mode === 'navigate') {
		event.respondWith(fetch(req).catch(() => caches.match('/') as Promise<Response>));
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
