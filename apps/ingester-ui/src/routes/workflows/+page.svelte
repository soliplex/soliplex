<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import WorkflowList from '$lib/components/WorkflowList.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import { RunStatus } from '$lib/types/api';
	import type { PageData } from './$types';
	import type { PaginatedResponse, WorkflowRun } from '$lib/types/api';

	let { data }: { data: PageData } = $props();

	const currentStatus = $derived<RunStatus | 'all'>(
		(data.filters.status as RunStatus) || 'all'
	);

	// Determine if we have paginated data
	const isPaginatedResponse = $derived(
		data.workflowRuns !== null &&
			typeof data.workflowRuns === 'object' &&
			'items' in data.workflowRuns
	);

	// Extract workflows array (works for both paginated and non-paginated)
	const workflows = $derived<WorkflowRun[]>(
		isPaginatedResponse
			? (data.workflowRuns as PaginatedResponse<WorkflowRun>).items
			: (data.workflowRuns as WorkflowRun[])
	);

	// Extract pagination metadata
	const paginationData = $derived(
		isPaginatedResponse
			? {
					currentPage: (data.workflowRuns as PaginatedResponse<WorkflowRun>).page,
					totalPages: (data.workflowRuns as PaginatedResponse<WorkflowRun>).total_pages,
					totalItems: (data.workflowRuns as PaginatedResponse<WorkflowRun>).total,
					itemsPerPage: (data.workflowRuns as PaginatedResponse<WorkflowRun>).rows_per_page
				}
			: null
	);

	function updateUrlParams(updates: Record<string, string | null>) {
		const url = new URL($page.url);

		// Apply updates
		Object.entries(updates).forEach(([key, value]) => {
			if (value === null) {
				url.searchParams.delete(key);
			} else {
				url.searchParams.set(key, value);
			}
		});

		goto(url.toString());
	}

	function handleStatusChange(status: RunStatus | 'all') {
		updateUrlParams({
			status: status === 'all' ? null : status,
			page: '1' // Reset to page 1 when filter changes
		});
	}

	function handlePageChange(newPage: number) {
		updateUrlParams({ page: String(newPage) });
	}

	function handlePageSizeChange(newSize: number) {
		updateUrlParams({
			limit: String(newSize),
			page: '1' // Reset to page 1 when page size changes
		});
	}

	function handleRefresh() {
		window.location.reload();
	}
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Workflow Runs" description="Monitor workflow runs and their status" />

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} retry={handleRefresh} />
		</div>
	{:else}
		<div class="mt-6">
			<FilterBar {currentStatus} onStatusChange={handleStatusChange} onRefresh={handleRefresh} />
		</div>

		<div class="mt-6">
			<WorkflowList {workflows} />
		</div>

		<!-- Pagination controls (only show when paginated) -->
		{#if isPaginatedResponse && paginationData}
			<div class="mt-6">
				<Pagination
					currentPage={paginationData.currentPage}
					totalPages={paginationData.totalPages}
					totalItems={paginationData.totalItems}
					itemsPerPage={paginationData.itemsPerPage}
					onPageChange={handlePageChange}
					onPageSizeChange={handlePageSizeChange}
				/>
			</div>
		{/if}
	{/if}
</div>
