import type { CapacitorConfig } from '@capacitor/cli';

// The iOS app is a native shell around the uFeed web app served by the
// server, so every deploy reaches the app without a new store release.
// Native parts: background audio (Info.plist + AVAudioSession in
// AppDelegate), App-Bound Domains so the service worker (offline mode) works
// in WKWebView, and a user-agent mark so the web app hides "install app".
// CAP_SERVER_URL points a development build at another uFeed (e.g. the local
// stack) — never set for store builds.
const devUrl = process.env.CAP_SERVER_URL;

const config: CapacitorConfig = {
	appId: 'es.uverse.ufeed',
	appName: 'uFeed',
	webDir: 'www',
	server: {
		url: devUrl || 'https://ufeed.uverse.es',
		cleartext: !!devUrl?.startsWith('http:'),
		// Shown if the server can't be reached at launch.
		errorPath: 'offline.html'
	},
	ios: {
		appendUserAgent: 'uFeedApp/1.0',
		limitsNavigationsToAppBoundDomains: !devUrl,
		contentInset: 'never',
		backgroundColor: '#f7f7f8'
	}
};

export default config;
