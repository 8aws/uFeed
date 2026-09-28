import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		// SPA: fallback so client-side routing handles every path.
		adapter: adapter({ fallback: 'index.html' }),
		// Content-Security-Policy (emitted as a <meta> tag with hashes for the
		// inline bootstrap script). Only our own scripts can run, so injected
		// markup in third-party feed content can't execute or exfiltrate.
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				'script-src': ['self'],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'https:', 'data:', 'blob:'],
				'media-src': ['self', 'https:'],
				'font-src': ['self', 'data:'],
				'connect-src': ['self'],
				'worker-src': ['self'],
				'manifest-src': ['self'],
				// Only the privacy-enhanced YouTube and Vimeo players, created by the
				// reader when a video card is tapped (feed HTML never gets iframes).
				'frame-src': ['https://www.youtube-nocookie.com', 'https://player.vimeo.com'],
				'object-src': ['none'],
				'base-uri': ['self'],
				'form-action': ['self'],
				'upgrade-insecure-requests': true
			}
		}
	}
};

export default config;
