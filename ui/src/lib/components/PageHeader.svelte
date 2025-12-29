<script lang="ts">
	interface Props {
		title: string;
		description?: string;
		actions?: import('svelte').Snippet;
	}

	let { title, description, actions }: Props = $props();
</script>

<div class="border-b border-gray-200 bg-white px-4 py-5 sm:px-6 lg:px-8">
	<div class="-ml-4 -mt-2 flex flex-wrap items-center justify-between sm:flex-nowrap">
		<div class="ml-4 mt-2">
			<h1 class="text-2xl font-bold leading-7 text-gray-900 sm:truncate sm:text-3xl">
				{title}
			</h1>
			{#if description}
				<p class="mt-1 text-sm text-gray-500">{description}</p>
			{/if}
		</div>
		{#if actions}
			<div class="ml-4 mt-2 flex-shrink-0">
				{@render actions()}
			</div>
		{/if}
	</div>
</div>
