// Defence in depth for third-party feed content rendered in the reader.
// The backend already keeps only http(s) links and feedparser strips scripts,
// but anything that ends up in href/src/innerHTML is re-checked here.
import DOMPurify from 'dompurify';

/** Only absolute http(s) URLs; anything else (javascript:, data:, …) -> undefined. */
export function safeUrl(url: string | null | undefined): string | undefined {
	if (!url) return undefined;
	try {
		const u = new URL(url);
		return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : undefined;
	} catch {
		return undefined;
	}
}

let hooked = false;

/** Sanitised article HTML: no scripts/forms/embeds/inline styles; links open
 *  in a new tab without access to this window. */
export function safeHtml(html: string | null | undefined): string {
	if (!html) return '';
	if (!hooked) {
		DOMPurify.addHook('afterSanitizeAttributes', (node) => {
			if (node.tagName === 'A') {
				if (!safeUrl(node.getAttribute('href'))) node.removeAttribute('href');
				node.setAttribute('target', '_blank');
				node.setAttribute('rel', 'noopener noreferrer nofollow');
			}
			if (node.tagName === 'IMG' && !safeUrl(node.getAttribute('src'))) {
				node.removeAttribute('src');
			}
		});
		hooked = true;
	}
	return DOMPurify.sanitize(html, {
		FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select', 'iframe', 'object', 'embed'],
		FORBID_ATTR: ['style', 'srcset'],
		ADD_ATTR: ['target']
	});
}
