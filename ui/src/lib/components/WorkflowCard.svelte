<script lang="ts">
	import type { WorkflowRun } from '$lib/types/api';
	import StatusBadge from './StatusBadge.svelte';
	import { formatDuration, formatRelativeTime, truncateText } from '$lib/utils/format';

	interface Props {
		workflow: WorkflowRun;
	}

	let { workflow }: Props = $props();

	const progress = $derived(() => {
		if (!workflow.steps || workflow.steps.length === 0) {
			return null;
		}
		const completed = workflow.steps.filter((s) => s.status === 'COMPLETED').length;
		return `${completed}/${workflow.steps.length}`;
	});
</script>

<a
	href="/workflows/{workflow.id}"
	class="block rounded-lg border border-gray-200 bg-white p-4 transition hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
>
	<div class="flex items-start justify-between">
		<div class="flex-1">
			<div class="flex items-center gap-2">
				<h3 class="text-sm font-semibold text-gray-900">
					Workflow #{workflow.id}
				</h3>
				<StatusBadge status={workflow.status} />
			</div>

			<p class="mt-2 text-sm text-gray-600">
				Document: {truncateText(workflow.doc_id, 40)}
				Source : {workflow.run_params.source}
			</p>
			<div class="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
				<span>
					Definition: <span class="font-medium">{workflow.workflow_definition_id}</span>
				</span>
				<span>
					Parameter Set: <span class="font-medium">{workflow.run_params.param_id}</span>
				</span>
				<span>Batch: <span class="font-medium">#{workflow.batch_id}</span></span>
				{#if progress()}
					<span>Progress: <span class="font-medium">{progress()}</span></span>
				{/if}
			</div>
		</div>
		<div class="ml-4 text-right text-xs text-gray-500">
			<div>{formatRelativeTime(workflow.created_date)}</div>
			{#if workflow.duration !== null}
				<div class="mt-1 font-medium">{formatDuration(workflow.duration)}</div>
			{/if}
		</div>
	</div>
	{#if workflow.status_message}
		<div class="mt-2 rounded bg-gray-50 p-2 text-xs text-gray-700">
			{workflow.status_message}
		</div>
	{/if}
</a>
