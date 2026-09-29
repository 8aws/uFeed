// Device voice for "listen": the browser's speech synthesis (Web Speech API).
// Free and offline, quality depends on the voices installed on the device
// (on iPhone/Mac the "Enhanced"/"Premium" Siri voices sound far better).
//
// Text is spoken in short chunks: some browsers (Chrome) stop long utterances
// after ~15 s, and chunks let pause/resume and speed changes restart at the
// current sentence instead of relying on speechSynthesis.pause(), which is
// unreliable across browsers.

export type SpeechState = 'idle' | 'playing' | 'paused' | 'ended';

const MAX_CHUNK = 220;

export function speechSupported(): boolean {
	return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/** Split into sentence-sized chunks of at most MAX_CHUNK characters. */
export function chunks(text: string): string[] {
	const out: string[] = [];
	for (const sentence of text.split(/(?<=[.!?…;:])\s+/)) {
		let s = sentence.trim();
		while (s.length > MAX_CHUNK) {
			const cut = Math.max(s.lastIndexOf(', ', MAX_CHUNK), s.lastIndexOf(' ', MAX_CHUNK));
			const at = cut > 40 ? cut + 1 : MAX_CHUNK;
			out.push(s.slice(0, at).trim());
			s = s.slice(at).trim();
		}
		if (s) out.push(s);
	}
	return out;
}

/** Installed voices for a language (e.g. for a picker in Settings). */
export function voicesFor(lang: string): SpeechSynthesisVoice[] {
	if (!speechSupported()) return [];
	const base = lang.split(/[-_]/)[0].toLowerCase();
	return speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(base));
}

/** The voice chosen in Settings, else the best installed one for the language
 *  (enhanced/premium first, Spain's Spanish for es). */
export function pickVoice(lang: string, preferred?: string): SpeechSynthesisVoice | null {
	const voices = voicesFor(lang);
	if (!voices.length) return null;
	const chosen = preferred && voices.find((v) => v.name === preferred);
	if (chosen) return chosen;
	const base = lang.split(/[-_]/)[0].toLowerCase();
	const score = (v: SpeechSynthesisVoice) =>
		(/premium|enhanced|mejorad|natural|neural/i.test(v.name) ? 4 : 0) +
		(base === 'es' && /es[-_]es/i.test(v.lang) ? 2 : 0) +
		(v.localService ? 1 : 0) +
		(v.default ? 0.5 : 0);
	return voices.sort((a, b) => score(b) - score(a))[0];
}

/** Text worth reading from the rendered article: no code, captions, tables,
 *  media or video cards; block ends become pauses. */
export function readableText(title: string, content: HTMLElement | null): string {
	if (!content) return title;
	const clone = content.cloneNode(true) as HTMLElement;
	clone
		.querySelectorAll('pre, code, figcaption, table, audio, video, iframe, .embed, script, style')
		.forEach((n) => n.remove());
	// innerText needs layout; textContent + block breaks works detached.
	clone.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, blockquote, br, div').forEach((n) => {
		n.append(document.createTextNode('\n'));
	});
	const body = (clone.textContent ?? '')
		.split(/\n+/)
		.map((l) => l.replace(/\s+/g, ' ').trim())
		.filter(Boolean)
		.map((l) => (/[.!?…:;]$/.test(l) ? l : `${l}.`))
		.join(' ');
	return title ? `${title}. ${body}` : body;
}

/** Text to read from a translation (title + paragraphs). */
export function translationText(title: string | null, paragraphs: string[]): string {
	const body = paragraphs.map((p) => (/[.!?…:;]$/.test(p) ? p : `${p}.`)).join(' ');
	return title ? `${title}. ${body}` : body;
}

/** iOS only lets speech start inside a tap: speaking an empty utterance right
 *  away "unlocks" it, so real text can follow after an await (translation). */
export function unlockSpeech() {
	if (speechSupported()) speechSynthesis.speak(new SpeechSynthesisUtterance(''));
}

export class DeviceSpeech {
	private parts: string[];
	private index = 0;
	private run = 0; // invalidates callbacks of utterances we cancelled
	state: SpeechState = 'idle';

	constructor(
		text: string,
		private lang: string,
		private rate: number,
		private onChange: (state: SpeechState, index: number, total: number) => void,
		private voiceName?: string
	) {
		this.parts = chunks(text);
	}

	get total() {
		return this.parts.length;
	}

	/** Must be called from a user gesture the first time (iOS). */
	play() {
		if (!speechSupported() || !this.parts.length) return;
		if (this.state === 'ended') this.index = 0;
		this.speakFrom(this.index);
	}

	pause() {
		this.run++;
		speechSynthesis.cancel();
		this.set('paused');
	}

	stop() {
		this.run++;
		if (speechSupported()) speechSynthesis.cancel();
		this.index = 0;
		this.set('idle');
	}

	setRate(rate: number) {
		this.rate = rate;
		if (this.state === 'playing') this.speakFrom(this.index);
	}

	/** Jump by n chunks (e.g. -1 to repeat the previous sentence). */
	skip(n: number) {
		this.index = Math.max(0, Math.min(this.parts.length - 1, this.index + n));
		if (this.state === 'playing') this.speakFrom(this.index);
		else this.set(this.state);
	}

	private speakFrom(start: number) {
		const run = ++this.run;
		speechSynthesis.cancel();
		const voice = pickVoice(this.lang, this.voiceName);
		// Queue everything at once: no gap between sentences, and it keeps going
		// if the page is throttled between callbacks.
		for (let i = start; i < this.parts.length; i++) {
			const u = new SpeechSynthesisUtterance(this.parts[i]);
			u.lang = voice?.lang ?? this.lang;
			if (voice) u.voice = voice;
			u.rate = this.rate;
			u.onstart = () => {
				if (run !== this.run) return;
				this.index = i;
				this.set('playing');
			};
			if (i === this.parts.length - 1) {
				u.onend = () => {
					if (run !== this.run) return;
					this.index = 0;
					this.set('ended');
				};
			}
			speechSynthesis.speak(u);
		}
		this.set('playing');
	}

	private set(state: SpeechState) {
		this.state = state;
		this.onChange(state, this.index, this.parts.length);
	}
}

/** Say a short sample with a given voice (Settings "try" button). */
export function sampleVoice(lang: string, voiceName: string, rate: number, text: string) {
	if (!speechSupported()) return;
	speechSynthesis.cancel();
	const u = new SpeechSynthesisUtterance(text);
	const voice = pickVoice(lang, voiceName);
	u.lang = voice?.lang ?? lang;
	if (voice) u.voice = voice;
	u.rate = rate;
	speechSynthesis.speak(u);
}
