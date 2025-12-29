<script lang="ts">
	import type { DocumentBatch } from '$lib/types/api';
	import { formatDateTime, formatDuration } from '$lib/utils/format';

	interface Props {
		batch: DocumentBatch;
		documentCount?: number;
		workflowCounts?: {
			completed?: number;
			running?: number;
			pending?: number;
			failed?: number;
		};
	}

	let { batch, documentCount, workflowCounts }: Props = $props();

	const isComplete = $derived(batch.completed_date !== null);
	const totalWorkflows = $derived(
		workflowCounts
			? (workflowCounts.completed || 0) +
					(workflowCounts.running || 0) +
					(workflowCounts.pending || 0) +
					(workflowCounts.failed || 0)
			: 0
	);
</script>

<a
	href="/batches/{batch.id}"
	class="block rounded-lg border border-gray-200 bg-white p-5 transition hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
>
	<div class="flex items-start justify-between">
		<div class="flex-1">
			<div class="flex items-center gap-2">
				<h3 class="text-lg font-semibold text-gray-900">
					{batch.name}
				</h3>
				{#if isComplete}
					<span
						class="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800"
					>
						✓ Complete
					</span>
				{:else}
					<span
						class="inline-flex items-center rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-800"
					>
						⟳ In Progress
					</span>
				{/if}
			</div>
			<p class="mt-1 text-sm text-gray-600">
				Source: <span class="font-medium">{batch.source}</span>
			</p>
			<div class="mt-3 flex flex-wrap gap-4 text-sm">
				{#if documentCount !== undefined}
					<div class="flex items-center gap-1 text-gray-600">
						<span class="font-medium">{documentCount}</span>
						<span>documents</span>
					</div>
				{/if}
				{#if workflowCounts}
					<div class="flex items-center gap-2 text-gray-600">
						{#if workflowCounts.completed}
							<span class="text-green-600">✓ {workflowCounts.completed}</span>
						{/if}
						{#if workflowCounts.running}
							<span class="text-blue-600">⟳ {workflowCounts.running}</span>
						{/if}
						{#if workflowCounts.pending}
							<span class="text-gray-500">⏸ {workflowCounts.pending}</span>
						{/if}
						{#if workflowCounts.failed}
							<span class="text-red-600">✗ {workflowCounts.failed}</span>
						{/if}
					</div>
				{/if}
			</div>
		</div>
		<div class="ml-4 text-right text-xs text-gray-500">
			<div>Started: {formatDateTime(batch.start_date)}</div>
			{#if batch.duration !== null}
				<div class="mt-1 font-medium">{formatDuration(batch.duration)}</div>
			{/if}
		</div>
	</div>
</a>
