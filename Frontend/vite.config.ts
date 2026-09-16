import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5173,
		// In dev, proxy API calls to the backend so the app is same-origin.
		proxy: {
			'/api': { target: 'http://localhost:8000', changeOrigin: true },
			'/openapi.json': { target: 'http://localhost:8000', changeOrigin: true }
		}
	}
});
