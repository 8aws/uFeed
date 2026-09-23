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
