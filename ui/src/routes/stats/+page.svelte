<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import StatsCard from '$lib/components/StatsCard.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import { formatDuration, formatDateTime } from '$lib/utils/format';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const tableData = $derived(
		data.runGroupStats.map((item) => ({
			runGroupId: item.runGroup.id,
			batchId: item.runGroup.batch_id,
			workflow: item.runGroup.workflow_definition_id,
			created: formatDateTime(item.runGroup.created_date),
			totalRuns: item.stats.total_runs,
			completed: item.stats.status_counts.COMPLETED || 0,
			failed: (item.stats.status_counts.FAILED || 0) + (item.stats.status_counts.ERROR || 0),
			avgDuration: formatDuration(item.stats.avg_duration)
		}))
	);

	const columns = [
		{ key: 'runGroupId', label: 'Run Group' },
		{ key: 'batchId', label: 'Batch' },
		{ key: 'workflow', label: 'Workflow' },
		{ key: 'created', label: 'Created' },
		{ key: 'totalRuns', label: 'Total Runs' },
		{ key: 'completed', label: 'Completed' },
		{ key: 'failed', label: 'Failed' },
		{ key: 'avgDuration', label: 'Avg Duration' }
	];

	function handleRowClick(row: Record<string, unknown>) {
		goto(`/batches/${row.batchId}`);
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Statistics" description="System-wide workflow and processing metrics" />

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} />
		</div>
	{:else}
		<div class="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
			<StatsCard title="Total Workflows" value={data.systemStats.totalWorkflows} icon="⚙️" />
			<StatsCard
				title="Completed"
				value={data.systemStats.completedWorkflows}
				description="Successfully finished"
				icon="✓"
			/>
			<StatsCard
				title="Failed"
				value={data.systemStats.failedWorkflows}
				description="Requires attention"
				icon="✗"
			/>
			<StatsCard title="Success Rate" value="{data.systemStats.successRate}%" icon="📊" />
		</div>

		<div class="mt-8">
			<div class="overflow-hidden rounded-lg bg-white shadow">
				<div class="px-6 py-5">
					<h3 class="text-lg font-semibold text-gray-900">Performance Metrics</h3>
					<div class="mt-4 grid grid-cols-1 gap-6 sm:grid-cols-3">
						<div>
							<dt class="text-sm font-medium text-gray-500">Average Duration</dt>
							<dd class="mt-1 text-2xl font-semibold text-gray-900">
								{formatDuration(data.systemStats.avgDuration)}
							</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Active Workflows</dt>
							<dd class="mt-1 text-2xl font-semibold text-gray-900">
								{data.systemStats.activeWorkflows}
							</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Total Run Groups</dt>
							<dd class="mt-1 text-2xl font-semibold text-gray-900">
								{data.runGroupStats.length}
							</dd>
						</div>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-8">
			<div class="overflow-hidden rounded-lg bg-white shadow">
				<div class="border-b border-gray-200 px-6 py-4">
					<h3 class="text-lg font-semibold text-gray-900">Recent Run Groups</h3>
				</div>
				{#if tableData.length === 0}
					<div class="px-6 py-12 text-center text-gray-500">
						<p>No run group data available</p>
					</div>
				{:else}
					<DataTable {columns} data={tableData} onRowClick={handleRowClick} />
				{/if}
			</div>
		</div>
	{/if}
</div>
