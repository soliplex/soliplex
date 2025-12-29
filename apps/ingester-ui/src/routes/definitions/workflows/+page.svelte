<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import DefinitionCard from '$lib/components/DefinitionCard.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Workflow Definitions" description="Browse available workflow configurations" />

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} />
		</div>
	{:else if data.definitions.length === 0}
		<div class="mt-6">
			<EmptyState
				title="No workflow definitions found"
				description="There are no workflow definitions configured."
			/>
		</div>
	{:else}
		<div class="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
			{#each data.definitions as definition (definition.id)}
				<DefinitionCard {definition} type="workflow" />
			{/each}
		</div>
	{/if}
</div>
