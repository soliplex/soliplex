<script lang="ts">
	interface Props {
		title: string;
		description?: string;
		actionText?: string;
		actionHref?: string;
	}

	let { title, description, actionText, actionHref }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center py-12 text-center">
	<div class="mb-4 rounded-full bg-gray-100 p-4">
		<svg
			class="h-12 w-12 text-gray-400"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="2"
				d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
			></path>
		</svg>
	</div>
	<h3 class="mb-2 text-lg font-semibold text-gray-900">{title}</h3>
	{#if description}
		<p class="mb-4 max-w-md text-sm text-gray-600">{description}</p>
	{/if}
	{#if actionText && actionHref}
		<a
			href={actionHref}
			class="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
		>
			{actionText}
		</a>
	{/if}
</div>
