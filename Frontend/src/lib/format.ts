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

/** Strip HTML tags to plain text (for card summaries). */
const NAMED: Record<string, string> = {
	'&nbsp;': ' ',
	'&quot;': '"',
	'&apos;': "'",
	'&lt;': '<',
	'&gt;': '>',
	'&rsquo;': '\u2019',
	'&lsquo;': '\u2018',
	'&rdquo;': '\u201D',
	'&ldquo;': '\u201C',
	'&hellip;': '\u2026',
	'&mdash;': '\u2014',
	'&ndash;': '\u2013'
};

/** Plain text of a feed excerpt (often HTML, sometimes escaped twice: `&amp;#8217;`). */
export function stripHtml(html: string | null): string {
	if (!html) return '';
	return html
		.replace(/<[^>]+>/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&#([xX][0-9a-fA-F]+|\d+);/g, (m, v: string) => {
			const code = /^[xX]/.test(v) ? parseInt(v.slice(1), 16) : parseInt(v, 10);
			return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : m;
		})
		.replace(/&[a-z]+;/g, (m) => NAMED[m] ?? m)
		.replace(/\s+/g, ' ')
		.trim();
}

/** Estimated reading time from a word count (~220 wpm). */
export function readingTime(words: number | null, locale: Locale): string {
	if (!words || words < 1) return '';
	const min = Math.max(1, Math.round(words / 220));
	return locale === 'es' ? `${min} min de lectura` : `${min} min read`;
}
