<script lang="ts">
	interface Props {
		data: unknown;
		title?: string;
	}

	let { data, title }: Props = $props();

	let copied = $state(false);

	async function handleCopy() {
		try {
			await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		} catch (err) {
			console.error('Failed to copy:', err);
		}
	}
</script>

<div class="rounded-lg border border-gray-200 bg-white">
	{#if title}
		<div class="flex items-center justify-between border-b border-gray-200 px-4 py-3">
			<h3 class="text-sm font-semibold text-gray-900">{title}</h3>
			<button
				type="button"
				onclick={handleCopy}
				class="rounded-md bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				{copied ? 'Copied!' : 'Copy'}
			</button>
		</div>
	{/if}
	<pre class="overflow-x-auto bg-gray-50 p-4 text-xs text-gray-900"><code
			>{JSON.stringify(data, null, 2)}</code
		></pre>
</div>
