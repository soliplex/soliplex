<script lang="ts">
	import { RunStatus } from '$lib/types/api';

	interface Props {
		currentStatus?: RunStatus | 'all';
		onStatusChange?: (status: RunStatus | 'all') => void;
		showRefresh?: boolean;
		onRefresh?: () => void;
	}

	let { currentStatus = 'all', onStatusChange, showRefresh = true, onRefresh }: Props = $props();

	const statusOptions: Array<{ value: RunStatus | 'all'; label: string }> = [
		{ value: 'all', label: 'All' },
		{ value: RunStatus.PENDING, label: 'Pending' },
		{ value: RunStatus.RUNNING, label: 'Running' },
		{ value: RunStatus.COMPLETED, label: 'Completed' },
		{ value: RunStatus.ERROR, label: 'Error' },
		{ value: RunStatus.FAILED, label: 'Failed' }
	];

	function handleStatusChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const value = target.value as RunStatus | 'all';
		if (onStatusChange) {
			onStatusChange(value);
		}
	}

	function handleRefreshClick() {
		if (onRefresh) {
			onRefresh();
		}
	}
</script>

<div class="flex items-center justify-between gap-4 rounded-lg bg-white p-4 shadow">
	<div class="flex items-center gap-4">
		<label for="status-filter" class="text-sm font-medium text-gray-700"> Status: </label>
		<select
			id="status-filter"
			class="rounded-md border-gray-300 py-2 pl-3 pr-10 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
			value={currentStatus}
			onchange={handleStatusChange}
		>
			{#each statusOptions as option}
				<option value={option.value}>{option.label}</option>
			{/each}
		</select>
	</div>
	{#if showRefresh && onRefresh}
		<button
			type="button"
			onclick={handleRefreshClick}
			class="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
		>
			<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
				></path>
			</svg>
			Refresh
		</button>
	{/if}
</div>
