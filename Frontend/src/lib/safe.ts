// Defence in depth for third-party feed content rendered in the reader.
// The backend already keeps only http(s) links and feedparser strips scripts,
// but anything that ends up in href/src/innerHTML is re-checked here.
import DOMPurify from 'dompurify';

/** Only absolute http(s) URLs; anything else (javascript:, data:, …) -> undefined. */
export function safeUrl(url: string | null | undefined, base?: string): string | undefined {
	if (!url) return undefined;
	try {
		const u = base ? new URL(url, base) : new URL(url);
		return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : undefined;
	} catch {
		return undefined;
	}
}

let hooked = false;
// Article address, for relative links/media in content stored before the
// backend resolved them (`/storage/clip.mp4` would otherwise hit uFeed).
let base: string | undefined;

/** Sanitised article HTML: no scripts/forms/embeds/inline styles; links open
 *  in a new tab without access to this window; media never autoplays. */
export function safeHtml(html: string | null | undefined, baseUrl?: string | null): string {
	if (!html) return '';
	if (!hooked) {
		DOMPurify.addHook('afterSanitizeAttributes', (node) => {
			for (const attr of ['src', 'href', 'poster']) {
				const v = node.getAttribute(attr);
				if (v === null) continue;
				const abs = safeUrl(v, base);
				if (abs) node.setAttribute(attr, abs);
				else node.removeAttribute(attr);
			}
			if (node.tagName === 'A') {
				node.setAttribute('target', '_blank');
				node.setAttribute('rel', 'noopener noreferrer nofollow');
			}
			if (node.tagName === 'IMG') {
				// Long articles carry dozens of full-size photos: fetch them as the
				// reader gets there and decode off the main thread, or a small
				// iPhone stops answering taps while it works through them.
				node.setAttribute('loading', 'lazy');
				node.setAttribute('decoding', 'async');
			}
			if (node.tagName === 'VIDEO' || node.tagName === 'AUDIO') {
				// Playable, and quiet until the reader asks (saves mobile data).
				node.removeAttribute('autoplay');
				node.setAttribute('controls', '');
				node.setAttribute('preload', node.tagName === 'VIDEO' ? 'metadata' : 'none');
				if (node.tagName === 'VIDEO') node.setAttribute('playsinline', '');
			}
		});
		hooked = true;
	}
	base = safeUrl(baseUrl ?? undefined);
	try {
		return DOMPurify.sanitize(html, {
			FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select', 'iframe', 'object', 'embed'],
			FORBID_ATTR: ['style', 'srcset'],
			ADD_ATTR: ['target', 'playsinline']
		});
	} finally {
		base = undefined;
	}
}

/** YouTube/Vimeo id from a link (the backend marks players it found with
 *  data-embed; plain watch links are recognised too). */
export function embedOf(a: HTMLAnchorElement): { provider: 'youtube' | 'vimeo'; id: string } | null {
	const tag = a.dataset.embed;
	if (tag) {
		const [provider, id] = tag.split(':');
		if (provider === 'youtube' && /^[\w-]{11}$/.test(id)) return { provider, id };
		if (provider === 'vimeo' && /^\d{4,12}$/.test(id)) return { provider, id };
	}
	let u: URL;
	try {
		u = new URL(a.href);
	} catch {
		return null;
	}
	const host = u.hostname.replace(/^(www|m)\./, '');
	let id: string | null = null;
	if (host === 'youtube.com' && u.pathname === '/watch') id = u.searchParams.get('v');
	else if (host === 'youtube.com' && /^\/(shorts|live)\//.test(u.pathname)) id = u.pathname.split('/')[2];
	else if (host === 'youtu.be') id = u.pathname.slice(1);
	if (id && /^[\w-]{11}$/.test(id)) return { provider: 'youtube', id };
	const vm = host === 'vimeo.com' && u.pathname.match(/^\/(\d{4,12})$/);
	if (vm) return { provider: 'vimeo', id: vm[1] };
	return null;
}
