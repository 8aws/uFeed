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
}

export const PACES = { calm: 0.85, normal: 1, fast: 1.25 } as const;

const SPEECH_DEFAULTS: SpeechPrefs = {
	mode: 'device',
	gender: 'f',
	rate: 1,
	deviceVoice: {},
	autoRead: false
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
