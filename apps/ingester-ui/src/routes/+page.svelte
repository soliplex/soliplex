<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import StatsCard from '$lib/components/StatsCard.svelte';
	import WorkflowList from '$lib/components/WorkflowList.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader
		title="Dashboard"
		description="Monitor your document processing workflows and batches"
	/>

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} />
		</div>
	{:else}
		<div class="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
			<StatsCard
				title="Total Batches"
				value={data.metrics.totalBatches}
				description="{data.metrics.recentBatches} added this week"
				icon="📦"
				href="/batches"
			/>
			<StatsCard
				title="Active Workflows"
				value={data.metrics.activeWorkflows}
				description="{data.metrics.runningWorkflows} running, {data.metrics
					.pendingWorkflows} pending"
				icon="⚙️"
				href="/workflows?status=RUNNING"
			/>
			<StatsCard
				title="Failed Workflows"
				value={data.metrics.failedWorkflows}
				description="Requires attention"
				icon="⚠️"
				href="/workflows?status=FAILED"
			/>
			<StatsCard
				title="Success Rate"
				value="{data.metrics.successRate}%"
				description="{data.metrics.completedToday} completed today"
				icon="✓"
			/>
		</div>

		<div class="mt-8">
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-lg font-semibold text-gray-900">Recent Activity</h2>
				<a href="/workflows" class="text-sm font-medium text-blue-600 hover:text-blue-700">
					View all workflows →
				</a>
			</div>
			{#if data.recentActivity.length === 0}
				<div class="rounded-lg bg-white p-8 text-center text-gray-500 shadow">
					<p>No workflow activity yet</p>
				</div>
			{:else}
				<WorkflowList workflows={data.recentActivity} />
			{/if}
		</div>
	{/if}
</div>
