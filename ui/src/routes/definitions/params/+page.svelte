<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import DefinitionCard from '$lib/components/DefinitionCard.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Parameter Sets" description="Browse available parameter configurations" />

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} />
		</div>
	{:else if data.paramSets.length === 0}
		<div class="mt-6">
			<EmptyState
				title="No parameter sets found"
				description="There are no parameter sets configured."
			/>
		</div>
	{:else}
		<div class="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
			{#each data.paramSets as paramSet (paramSet.id)}
				<DefinitionCard definition={paramSet} type="param" />
			{/each}
		</div>
	{/if}
</div>
