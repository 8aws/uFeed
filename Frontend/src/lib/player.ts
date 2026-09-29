// One <audio> element for the whole app. iOS lets a page start playback on
// an element only after a tap on it; reusing the same element keeps that
// permission, so Post radio can go jingle -> next post with the screen locked.

let el: HTMLAudioElement | null = null;

export function sharedAudio(): HTMLAudioElement {
	el ??= new Audio();
	el.preload = 'auto';
	return el;
}

/** Play the short chime between posts on the shared element; resolves when
 *  it has finished (or failed, so the radio never gets stuck). */
export function playJingle(): Promise<void> {
	const a = sharedAudio();
	return new Promise((resolve) => {
		const done = () => {
			a.removeEventListener('ended', done);
			a.removeEventListener('error', done);
			resolve();
		};
		a.addEventListener('ended', done);
		a.addEventListener('error', done);
		a.dataset.owner = 'jingle';
		a.src = '/jingle.wav';
		a.play().catch(done);
		setTimeout(done, 3000);
	});
}
