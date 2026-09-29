import { writable } from 'svelte/store';

/** How toolbar buttons render their label/icon. */
export type ToolbarLabels = 'auto' | 'both' | 'icons' | 'text';

// 'auto' shows icon + text on wide screens and icon-only on narrow ones, so the
// desktop builds the visual memory that makes the mobile icons legible.
function initialToolbarLabels(): ToolbarLabels {
	if (typeof localStorage !== 'undefined') {
		const v = localStorage.getItem('toolbar_labels');
		if (v === 'auto' || v === 'both' || v === 'icons' || v === 'text') return v;
	}
	return 'auto';
}

export const toolbarLabels = writable<ToolbarLabels>(initialToolbarLabels());

toolbarLabels.subscribe((value) => {
	if (typeof localStorage !== 'undefined') {
		try {
			localStorage.setItem('toolbar_labels', value);
		} catch {
			/* ignore */
		}
	}
});

/** Read-aloud preferences (per device: installed voices differ by device). */
export interface SpeechPrefs {
	mode: 'device' | 'server'; // preferred engine (server needs the plan feature)
	gender: 'f' | 'm'; // server voice
	rate: number; // 0.85 calm · 1 normal · 1.25 fast (fine-tuned in the player)
	deviceVoice: Record<string, string>; // lang -> installed voice name ('' = automatic)
	autoRead: boolean; // accessibility: start reading when an article opens
	myLanguage: boolean; // translate articles in another language before reading
	offlineAudio: boolean; // keep server-voice recordings of saved articles
	highlight: boolean; // highlight the sentence being read (reading difficulties)
	radioPosts: number; // Post radio: stop after this many posts (0 = plan max)
	radioMinutes: number; // ...or after this many minutes (0 = plan max)
}

export const PACES = { calm: 0.85, normal: 1, fast: 1.25 } as const;

const SPEECH_DEFAULTS: SpeechPrefs = {
	mode: 'device',
	gender: 'f',
	rate: 1,
	deviceVoice: {},
	autoRead: false,
	myLanguage: false,
	offlineAudio: false,
	highlight: true,
	radioPosts: 10,
	radioMinutes: 30
};

function initialSpeechPrefs(): SpeechPrefs {
	try {
		const raw = localStorage.getItem('speech_prefs');
		if (raw) return { ...SPEECH_DEFAULTS, ...(JSON.parse(raw) as Partial<SpeechPrefs>) };
	} catch {
		/* fall through */
	}
	return { ...SPEECH_DEFAULTS };
}

export const speechPrefs = writable<SpeechPrefs>(
	typeof localStorage !== 'undefined' ? initialSpeechPrefs() : { ...SPEECH_DEFAULTS }
);

speechPrefs.subscribe((value) => {
	if (typeof localStorage === 'undefined') return;
	try {
		localStorage.setItem('speech_prefs', JSON.stringify(value));
	} catch {
		/* ignore */
	}
});

/** Accessibility display options (per device). */
export interface DisplayPrefs {
	textScale: number; // 1 = default; scales the whole interface (rem-based)
	font: 'system' | 'atkinson'; // Atkinson Hyperlegible: designed for low vision
	autoFull: boolean; // load the full article when the feed only has an excerpt
}

export const TEXT_SCALES = [1, 1.15, 1.3, 1.5] as const;

function initialDisplayPrefs(): DisplayPrefs {
	const d: DisplayPrefs = { textScale: 1, font: 'system', autoFull: true };
	try {
		const raw = localStorage.getItem('display_prefs');
		if (raw) return { ...d, ...(JSON.parse(raw) as Partial<DisplayPrefs>) };
	} catch {
		/* fall through */
	}
	return d;
}

export const displayPrefs = writable<DisplayPrefs>(
	typeof localStorage !== 'undefined'
		? initialDisplayPrefs()
		: { textScale: 1, font: 'system', autoFull: true }
);

displayPrefs.subscribe((value) => {
	if (typeof document === 'undefined') return;
	// Applied on <html> so every page (and the rem-based layout) follows.
	document.documentElement.style.setProperty('--text-scale', String(value.textScale));
	document.documentElement.dataset.font = value.font;
	try {
		localStorage.setItem('display_prefs', JSON.stringify(value));
	} catch {
		/* ignore */
	}
});
