// Offline audio: the server voice's MP3 of saved articles, kept on the device
// so they can be listened to without connection (the device voice already
// works offline). Stored in the Cache API under the stable path
// /api/audio/<name> (the signed query expires); the service worker serves it
// from there, including the Range requests iOS uses for audio.
// Cleared on logout with the other ufeed-offline* caches.

import { api, ApiError } from '$lib/api';
import type { Article } from '$lib/types';

export const AUDIO_CACHE = 'ufeed-offline-audio';
const MAX_ARTICLES = 20; // ~1.5 MB each
const SERVER_LANGS = ['es', 'en'];

const pathOf = (url: string) => new URL(url, location.origin).pathname;
const prefix = (id: string, lang: string, gender: string) => `/api/audio/${id}-${lang}${gender}-`;

/** URL of a stored recording for this article/voice (served by the SW), or null. */
export async function offlineAudioUrl(id: string, lang: string, gender: string): Promise<string | null> {
	if (typeof caches === 'undefined') return null;
	try {
		const keys = await (await caches.open(AUDIO_CACHE)).keys();
		const p = prefix(id, lang, gender);
		const hit = keys.find((k) => new URL(k.url).pathname.startsWith(p));
		return hit ? new URL(hit.url).pathname : null;
	} catch {
		return null;
	}
}

let warming = false;

/** Download (generating on the server if needed) the recordings of the saved
 *  articles, newest first, and drop those of articles no longer saved. */
export async function warmAudio(
	saved: Article[],
	opts: { gender: 'f' | 'm'; myLang: string | null; canTranslate: (a: Article) => boolean },
	full = true // the whole saved list (prunes the rest) vs. just these articles
): Promise<void> {
	if (warming || typeof caches === 'undefined' || !navigator.onLine) return;
	warming = true;
	try {
		const cache = await caches.open(AUDIO_CACHE);
		const wanted = saved.slice(0, MAX_ARTICLES);
		const ids = new Set(wanted.map((a) => a.id));
		// Forget recordings of articles that were unsaved (or fell off the list).
		for (const k of full ? await cache.keys() : []) {
			const name = new URL(k.url).pathname.split('/').pop() ?? '';
			if (!ids.has(name.slice(0, 36))) await cache.delete(k);
		}
		for (const a of wanted) {
			const translated = !!opts.myLang && opts.canTranslate(a);
			const lang = translated ? opts.myLang! : (a.lang || '').split(/[-_]/)[0].toLowerCase();
			if (!SERVER_LANGS.includes(lang)) continue;
			if (await offlineAudioUrl(a.id, lang, opts.gender)) continue;
			try {
				const r = await api.articleAudio(a.id, lang, opts.gender, translated);
				const resp = await fetch(r.url);
				if (resp.ok) await cache.put(pathOf(r.url), resp);
			} catch (e) {
				// Quota, plan or connection: try again on the next warm-up.
				if (e instanceof ApiError && [403, 429].includes(e.status)) break;
				if (!navigator.onLine) break;
			}
		}
	} finally {
		warming = false;
	}
}

/** Remove every stored recording (toggle switched off). */
export async function clearAudio() {
	if (typeof caches !== 'undefined') await caches.delete(AUDIO_CACHE).catch(() => false);
}
