<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import WorkflowList from '$lib/components/WorkflowList.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import StartWorkflowsForm from '$lib/components/StartWorkflowsForm.svelte';
	import { RunStatus } from '$lib/types/api';
	import { formatDateTime, formatDuration } from '$lib/utils/format';
	import { invalidateAll } from '$app/navigation';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let statusFilter = $state<RunStatus | 'all'>('all');

	const filteredWorkflows = $derived(
		statusFilter === 'all'
			? data.workflows
			: data.workflows.filter((w) => w.status === statusFilter)
	);

	const isComplete = $derived(data.batch.completed_date !== null);

	function handleWorkflowsStarted() {
		// Refresh the page data
		invalidateAll();
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Batch: {data.batch.name}">
		{#snippet actions()}
			<a href="/batches" class="text-sm font-medium text-gray-600 hover:text-gray-900">
				← Back to batches
			</a>
		{/snippet}
	</PageHeader>

	<div class="mt-6">
		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="px-6 py-5">
				<div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
					<div>
						<dt class="text-sm font-medium text-gray-500">Batch ID</dt>
						<dd class="mt-1 text-lg font-semibold text-gray-900">#{data.batch.id}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Source</dt>
						<dd class="mt-1 text-lg font-semibold text-gray-900">{data.batch.source}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Documents</dt>
						<dd class="mt-1 text-lg font-semibold text-gray-900">{data.documentCount}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Status</dt>
						<dd class="mt-1">
							{#if isComplete}
								<span
									class="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800"
								>
									✓ Complete
								</span>
							{:else}
								<span
									class="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800"
								>
									⟳ In Progress
								</span>
							{/if}
						</dd>
					</div>
				</div>

				<div class="mt-6 border-t border-gray-200 pt-6">
					<div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
						<div>
							<dt class="text-sm font-medium text-gray-500">Started</dt>
							<dd class="mt-1 text-sm text-gray-900">
								{formatDateTime(data.batch.start_date)}
							</dd>
						</div>
						{#if data.batch.completed_date}
							<div>
								<dt class="text-sm font-medium text-gray-500">Completed</dt>
								<dd class="mt-1 text-sm text-gray-900">
									{formatDateTime(data.batch.completed_date)}
								</dd>
							</div>
						{/if}
						{#if data.batch.duration !== null}
							<div>
								<dt class="text-sm font-medium text-gray-500">Duration</dt>
								<dd class="mt-1 text-sm text-gray-900">
									{formatDuration(data.batch.duration)}
								</dd>
							</div>
						{/if}
					</div>
				</div>
			</div>

			<div class="border-t border-gray-200 bg-gray-50 px-6 py-4">
				<h3 class="text-sm font-medium text-gray-700">Workflow Status</h3>
				<div class="mt-3 flex flex-wrap gap-4">
					<div class="flex items-center gap-2">
						<StatusBadge status={RunStatus.COMPLETED} />
						<span class="text-sm text-gray-600">
							{data.workflowCounts.COMPLETED || 0}
						</span>
					</div>
					<div class="flex items-center gap-2">
						<StatusBadge status={RunStatus.RUNNING} />
						<span class="text-sm text-gray-600">
							{data.workflowCounts.RUNNING || 0}
						</span>
					</div>
					<div class="flex items-center gap-2">
						<StatusBadge status={RunStatus.PENDING} />
						<span class="text-sm text-gray-600">
							{data.workflowCounts.PENDING || 0}
						</span>
					</div>
					<div class="flex items-center gap-2">
						<StatusBadge status={RunStatus.ERROR} />
						<span class="text-sm text-gray-600">
							{data.workflowCounts.ERROR || 0}
						</span>
					</div>
					<div class="flex items-center gap-2">
						<StatusBadge status={RunStatus.FAILED} />
						<span class="text-sm text-gray-600">
							{data.workflowCounts.FAILED || 0}
						</span>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-8">
			<StartWorkflowsForm
				batchId={data.batchId}
				workflowDefinitions={data.workflowDefinitions}
				paramSets={data.paramSets}
				onSuccess={handleWorkflowsStarted}
			/>
		</div>

		<div class="mt-8">
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-lg font-semibold text-gray-900">Workflows</h2>
				<div class="flex items-center gap-2">
					<label for="status-select" class="text-sm text-gray-600">Filter:</label>
					<select
						id="status-select"
						bind:value={statusFilter}
						class="rounded-md border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500"
					>
						<option value="all">All</option>
						<option value={RunStatus.PENDING}>Pending</option>
						<option value={RunStatus.RUNNING}>Running</option>
						<option value={RunStatus.COMPLETED}>Completed</option>
						<option value={RunStatus.ERROR}>Error</option>
						<option value={RunStatus.FAILED}>Failed</option>
					</select>
				</div>
			</div>
			<WorkflowList workflows={filteredWorkflows} />
		</div>
	</div>
</div>
