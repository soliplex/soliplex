<script lang="ts">
	import type { DocumentBatch } from '$lib/types/api';
	import BatchCard from './BatchCard.svelte';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		batches: DocumentBatch[];
	}

	let { batches }: Props = $props();
</script>

{#if batches.length === 0}
	<EmptyState title="No batches found" description="There are no batches to display." />
{:else}
	<div class="space-y-4">
		{#each batches as batch (batch.id)}
			<BatchCard {batch} />
		{/each}
	</div>
{/if}
