<script lang="ts">
	import { getErrorMessage } from '$lib/utils/errors';

	interface Props {
		error: unknown;
		retry?: () => void;
	}

	let { error, retry }: Props = $props();

	const message = $derived(getErrorMessage(error));
</script>

<div class="rounded-lg border border-red-200 bg-red-50 p-4" role="alert" aria-live="assertive">
	<div class="flex items-start gap-3">
		<svg
			class="h-5 w-5 flex-shrink-0 text-red-600"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
			></path>
		</svg>
		<div class="flex-1">
			<h3 class="text-sm font-semibold text-red-800">Error</h3>
			<p class="mt-1 text-sm text-red-700">{message}</p>
		</div>
		{#if retry}
			<button
				onclick={retry}
				class="rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
			>
				Retry
			</button>
		{/if}
	</div>
</div>
