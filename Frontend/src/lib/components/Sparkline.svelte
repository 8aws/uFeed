<script lang="ts">
	// Tiny inline chart for the admin resource monitor (no chart library: the
	// CSP only allows our own scripts). Line for series, bars for daily counts.
	let {
		values,
		kind = 'line',
		max = null,
		label = ''
	}: { values: (number | null)[]; kind?: 'line' | 'bars'; max?: number | null; label?: string } = $props();

	const W = 240;
	const H = 44;
	const nums = $derived(values.map((v) => (v == null || !Number.isFinite(v) ? null : v)));
	const top = $derived(max ?? Math.max(1e-9, ...nums.filter((v): v is number => v != null)));
	const y = (v: number) => H - 2 - (Math.min(v, top) / top) * (H - 4);
	const path = $derived.by(() => {
		const n = nums.length;
		let d = '';
		nums.forEach((v, i) => {
			if (v == null) return;
			const x = n <= 1 ? W : (i / (n - 1)) * W;
			d += `${d ? 'L' : 'M'}${x.toFixed(1)},${y(v).toFixed(1)}`;
		});
		return d;
	});
</script>

<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label={label}>
	{#if kind === 'bars'}
		{#each nums as v, i (i)}
			{#if v != null && v > 0}
				{@const bw = W / Math.max(nums.length, 1)}
				<rect x={i * bw + 1} y={y(v)} width={Math.max(bw - 2, 1)} height={H - 2 - y(v)} rx="1.5" />
			{/if}
		{/each}
	{:else if path}
		<path d={path} />
	{/if}
</svg>

<style>
	svg {
		display: block;
		width: 100%;
		height: 44px;
	}
	path {
		fill: none;
		stroke: var(--accent);
		stroke-width: 1.6;
		vector-effect: non-scaling-stroke;
	}
	rect {
		fill: var(--accent);
		opacity: 0.8;
	}
</style>
