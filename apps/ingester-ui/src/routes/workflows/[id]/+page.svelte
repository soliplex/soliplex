<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import StepTimeline from '$lib/components/StepTimeline.svelte';
	import { formatDateTime, formatDuration, truncateText } from '$lib/utils/format';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const hasSteps = $derived(data.workflow.steps && data.workflow.steps.length > 0);
	const completedSteps = $derived(
		data.workflow.steps?.filter((s) => s.status === 'COMPLETED').length || 0
	);
	const totalSteps = $derived(data.workflow.steps?.length || 0);
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Workflow Run #{data.workflow.id}">
		{#snippet actions()}
			<a href="/workflows" class="text-sm font-medium text-gray-600 hover:text-gray-900">
				← Back to workflows
			</a>
		{/snippet}
	</PageHeader>

	<div class="mt-6">
		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="px-6 py-5">
				<div class="flex items-start justify-between">
					<div class="flex-1">
						<div class="flex items-center gap-3">
							<h2 class="text-xl font-semibold text-gray-900">
								Workflow #{data.workflow.id}
							</h2>
							<StatusBadge status={data.workflow.status} />
						</div>
						<p class="mt-2 text-sm text-gray-600">
							Document: <span class="font-mono text-xs"
								>{truncateText(data.workflow.doc_id, 60)}</span
							>
						</p>
					</div>
				</div>

				<div
					class="mt-6 grid grid-cols-1 gap-6 border-t border-gray-200 pt-6 sm:grid-cols-2 lg:grid-cols-3"
				>
					<div>
						<dt class="text-sm font-medium text-gray-500">Definition</dt>
						<dd class="mt-1 text-sm text-gray-900">
							<a
								href="/definitions/workflows/{data.workflow.workflow_definition_id}"
								class="text-blue-600 hover:text-blue-700"
							>
								{data.workflow.workflow_definition_id}
							</a>
						</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Batch</dt>
						<dd class="mt-1 text-sm text-gray-900">
							<a href="/batches/{data.workflow.batch_id}" class="text-blue-600 hover:text-blue-700">
								#{data.workflow.batch_id}
							</a>
						</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Run Group</dt>
						<dd class="mt-1 text-sm text-gray-900">#{data.workflow.run_group_id}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Priority</dt>
						<dd class="mt-1 text-sm text-gray-900">{data.workflow.priority}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Created</dt>
						<dd class="mt-1 text-sm text-gray-900">
							{formatDateTime(data.workflow.created_date)}
						</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Started</dt>
						<dd class="mt-1 text-sm text-gray-900">
							{formatDateTime(data.workflow.start_date)}
						</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Completed</dt>
						<dd class="mt-1 text-sm text-gray-900">
							{formatDateTime(data.workflow.completed_date)}
						</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Duration</dt>
						<dd class="mt-1 text-sm text-gray-900">
							{formatDuration(data.workflow.duration)}
						</dd>
					</div>
					{#if hasSteps}
						<div>
							<dt class="text-sm font-medium text-gray-500">Progress</dt>
							<dd class="mt-1 text-sm text-gray-900">
								{completedSteps}/{totalSteps} steps
							</dd>
						</div>
					{/if}
				</div>

				{#if data.workflow.status_message}
					<div class="mt-6 rounded-md bg-gray-50 p-4">
						<h3 class="text-sm font-medium text-gray-700">Status Message</h3>
						<p class="mt-1 text-sm text-gray-900">{data.workflow.status_message}</p>
					</div>
				{/if}

				{#if Object.keys(data.workflow.status_meta).length > 0}
					<div class="mt-6 rounded-md bg-gray-50 p-4">
						<h3 class="text-sm font-medium text-gray-700">Status Metadata</h3>
						<pre class="mt-2 overflow-x-auto text-xs text-gray-900">{JSON.stringify(
								data.workflow.status_meta,
								null,
								2
							)}</pre>
					</div>
				{/if}
			</div>
		</div>

		{#if hasSteps}
			<div class="mt-8">
				<h2 class="mb-4 text-lg font-semibold text-gray-900">Workflow Steps</h2>
				<StepTimeline steps={data.workflow.steps || []} />
			</div>
		{/if}
	</div>
</div>
