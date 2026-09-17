import type { Locale } from '$lib/types';

/** Compact relative time, e.g. "3h", "2d". */
export function relativeTime(iso: string | null, locale: Locale): string {
	if (!iso) return '';
	const then = new Date(iso).getTime();
	if (Number.isNaN(then)) return '';
	const diff = Date.now() - then;
	const min = Math.round(diff / 60000);
	if (min < 1) return locale === 'es' ? 'ahora' : 'now';
	if (min < 60) return `${min}m`;
	const h = Math.round(min / 60);
	if (h < 24) return `${h}h`;
	const d = Math.round(h / 24);
	if (d < 30) return `${d}d`;
	return new Date(iso).toLocaleDateString(locale);
}

/** Estimated reading time from a word count (~220 wpm). */
export function readingTime(words: number | null, locale: Locale): string {
	if (!words || words < 1) return '';
	const min = Math.max(1, Math.round(words / 220));
	return locale === 'es' ? `${min} min de lectura` : `${min} min read`;
}
