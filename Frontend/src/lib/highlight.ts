// Highlight the sentence being read aloud (Accessibility), without touching
// the article's HTML: the CSS Custom Highlight API paints a Range
// (Chrome/Edge 105+, Safari 17.2+, Firefox 140+; elsewhere it's skipped).
//
// Spoken chunks come from readableText()/translationText(), which add pauses
// ('.') and normalise spaces, so matching uses only letters and digits: the
// article's text is indexed as a string of lowercase alphanumerics, each
// mapped back to its DOM text node and offset.

const NAME = 'ufeed-reading';
const SKIP = 'pre, code, figcaption, table, audio, video, .embed, .trnote, script, style';
const WORD = /[\p{L}\p{N}]/u;

type Pos = { node: Text; off: number };

export function highlightSupported(): boolean {
	return typeof CSS !== 'undefined' && 'highlights' in CSS && typeof Highlight !== 'undefined';
}

const key = (s: string) => [...s.toLowerCase()].filter((c) => WORD.test(c)).join('');

export class SentenceHighlighter {
	private text = '';
	private pos: Pos[] = [];
	private cursor = 0;
	private lastUserScroll = 0;
	private scroller: HTMLElement | null;
	private onUser = () => (this.lastUserScroll = Date.now());

	constructor(private root: HTMLElement) {
		this.scroller = root.closest('.reader-body');
		this.scroller?.addEventListener('wheel', this.onUser, { passive: true });
		this.scroller?.addEventListener('touchmove', this.onUser, { passive: true });
		this.index();
	}

	/** The article body this highlighter indexed. */
	get element(): HTMLElement {
		return this.root;
	}

	private index() {
		const chars: string[] = [];
		const walker = document.createTreeWalker(this.root, NodeFilter.SHOW_TEXT);
		for (let n = walker.nextNode() as Text | null; n; n = walker.nextNode() as Text | null) {
			if (n.parentElement?.closest(SKIP)) continue;
			const data = n.data;
			for (let i = 0; i < data.length; i++) {
				const c = data[i].toLowerCase();
				if (WORD.test(c)) {
					chars.push(c);
					this.pos.push({ node: n, off: i });
				}
			}
		}
		this.text = chars.join('');
	}

	/** Highlight the chunk being spoken; returns false if it isn't in the text
	 *  (e.g. the title, which lives outside the article body). */
	show(chunk: string): boolean {
		if (!highlightSupported()) return false;
		const k = key(chunk);
		if (k.length < 3) return false;
		let at = this.text.indexOf(k, this.cursor);
		if (at < 0) at = this.text.indexOf(k);
		let len = k.length;
		if (at < 0) {
			// Last resort: the start of the chunk (cut sentences, odd markup).
			const head = k.slice(0, 24);
			at = this.text.indexOf(head, this.cursor);
			if (at < 0) return false;
			len = Math.min(k.length, this.text.length - at);
		}
		const start = this.pos[at];
		const end = this.pos[at + len - 1];
		const range = document.createRange();
		range.setStart(start.node, start.off);
		range.setEnd(end.node, end.off + 1);
		CSS.highlights.set(NAME, new Highlight(range));
		this.cursor = at + len;
		this.follow(range);
		return true;
	}

	/** Keep the sentence in view, unless the reader scrolled away on purpose. */
	private follow(range: Range) {
		if (!this.scroller || Date.now() - this.lastUserScroll < 5000) return;
		const r = range.getBoundingClientRect();
		const box = this.scroller.getBoundingClientRect();
		if (r.top >= box.top + 60 && r.bottom <= box.bottom - 60) return;
		const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
		this.scroller.scrollBy({
			top: r.top - box.top - box.height / 3,
			behavior: reduce ? 'auto' : 'smooth'
		});
	}

	clear() {
		if (highlightSupported()) CSS.highlights.delete(NAME);
	}

	destroy() {
		this.clear();
		this.scroller?.removeEventListener('wheel', this.onUser);
		this.scroller?.removeEventListener('touchmove', this.onUser);
	}
}

/** Which chunk is playing at `fraction` (0..1) of a recording, assuming a
 *  steady pace (Piper's is): weights each chunk by its length. */
export function chunkAt(chunks: string[], fraction: number): number {
	const total = chunks.reduce((n, c) => n + c.length, 0);
	let acc = 0;
	const target = fraction * total;
	for (let i = 0; i < chunks.length; i++) {
		acc += chunks[i].length;
		if (acc >= target) return i;
	}
	return chunks.length - 1;
}
