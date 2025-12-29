<script lang="ts">
	import type { WorkflowRun } from '$lib/types/api';
	import WorkflowCard from './WorkflowCard.svelte';
	import EmptyState from './EmptyState.svelte';

	interface Props {
		workflows: WorkflowRun[];
		compact?: boolean;
	}

	let { workflows, compact = false }: Props = $props();
</script>

{#if workflows.length === 0}
	<EmptyState title="No workflows found" description="There are no workflow runs to display." />
{:else}
	<div class="space-y-3">
		{#each workflows as workflow (workflow.id)}
			<WorkflowCard {workflow} />
		{/each}
	</div>
{/if}
