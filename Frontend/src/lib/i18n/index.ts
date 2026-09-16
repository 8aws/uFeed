import { derived, writable } from 'svelte/store';
import type { Locale } from '$lib/types';
import { en, type Dict } from './en';
import { es } from './es';

const DICTS: Record<Locale, Dict> = { en, es };

function initialLocale(): Locale {
	if (typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem('locale');
		if (stored === 'en' || stored === 'es') return stored;
	}
	if (typeof navigator !== 'undefined' && navigator.language.startsWith('es')) return 'es';
	return 'en';
}

export const locale = writable<Locale>(initialLocale());

locale.subscribe((value) => {
	if (typeof localStorage !== 'undefined') localStorage.setItem('locale', value);
	if (typeof document !== 'undefined') document.documentElement.lang = value;
});

/** Reactive translator: use as $t('key'). */
export const t = derived(locale, ($locale) => {
	const dict = DICTS[$locale];
	return (key: keyof Dict): string => dict[key] ?? key;
});

export function setLocale(value: Locale) {
	locale.set(value);
}
