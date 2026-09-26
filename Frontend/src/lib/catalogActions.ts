// Shared actions for the starter catalogue (onboarding + Settings).

import { api } from '$lib/api';
import type { CatalogFeed } from '$lib/catalog';
import type { Folder, Subscription } from '$lib/types';

/** Loose URL key so `https://www.x.com/feed/` and `http://x.com/feed` match. */
export function feedKey(url: string): string {
	return url
		.trim()
		.toLowerCase()
		.replace(/^https?:\/\//, '')
		.replace(/^www\./, '')
		.replace(/\/+$/, '');
}

/** Reuse a folder with this name (case-insensitive) or create it. */
export async function ensureFolder(name: string, folders: Folder[]): Promise<Folder | null> {
	const found = folders.find((f) => f.name.toLowerCase() === name.toLowerCase());
	if (found) return found;
	try {
		const created = await api.createFolder(name);
		folders.push(created);
		return created;
	} catch {
		return null; // fall back to top level
	}
}

/** Subscribe to a catalogue feed, applying its curated name when the feed's own
 *  title is generic (e.g. tag feeds titled "Magazine - programacion"). */
export async function addCatalogFeed(
	f: CatalogFeed,
	folderId: string | null
): Promise<Subscription | null> {
	try {
		const sub = await api.subscribe(f.url, folderId);
		if (!sub.custom_title && sub.source.title !== f.title) {
			try {
				return await api.updateSubscription(sub.id, { custom_title: f.title });
			} catch {
				/* keep the feed's own title */
			}
		}
		return sub;
	} catch {
		return null;
	}
}
