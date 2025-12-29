<script lang="ts">
	import { apiClient } from '$lib/services/apiClient';
	import LoadingSpinner from './LoadingSpinner.svelte';
	import type { WorkflowDefinitionSummary, ParamSetSummary } from '$lib/types/api';

	interface Props {
		batchId: number;
		workflowDefinitions: WorkflowDefinitionSummary[];
		paramSets: ParamSetSummary[];
		onSuccess?: () => void;
	}

	let { batchId, workflowDefinitions, paramSets, onSuccess }: Props = $props();

	let selectedWorkflow = $state('');
	let selectedParamSet = $state('default');
	let priority = $state(0);
	let isSubmitting = $state(false);
	let error = $state<string | null>(null);
	let success = $state<string | null>(null);

	async function handleSubmit(event: Event) {
		event.preventDefault();
		isSubmitting = true;
		error = null;
		success = null;

		try {
			const response = await apiClient.startWorkflows(
				batchId,
				selectedWorkflow || undefined,
				priority,
				selectedParamSet || undefined
			);

			success = `${response.message}: ${response.workflows} workflows started (Run Group: ${response.run_group})`;

			// Reset form
			selectedWorkflow = '';
			selectedParamSet = 'default';
			priority = 0;

			// Call success callback
			if (onSuccess) {
				setTimeout(onSuccess, 1500);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to start workflows';
		} finally {
			isSubmitting = false;
		}
	}
</script>

<div class="rounded-lg border border-gray-200 bg-white p-6 shadow">
	<h3 class="text-lg font-semibold text-gray-900">Start Workflows</h3>
	<p class="mt-1 text-sm text-gray-600">
		Start workflow processing for all documents in this batch
	</p>

	<form onsubmit={handleSubmit} class="mt-4 space-y-4">
		<div>
			<label for="workflow" class="block text-sm font-medium text-gray-700">
				Workflow Definition
			</label>
			<select
				id="workflow"
				bind:value={selectedWorkflow}
				disabled={isSubmitting}
				class="mt-1 block w-full rounded-md border-gray-300 py-2 pl-3 pr-10 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
			>
				<option value="">Default (from config)</option>
				{#each workflowDefinitions as definition}
					<option value={definition.id}>{definition.name} ({definition.id})</option>
				{/each}
			</select>
		</div>

		<div>
			<label for="param-set" class="block text-sm font-medium text-gray-700"> Parameter Set </label>
			<select
				id="param-set"
				bind:value={selectedParamSet}
				disabled={isSubmitting}
				class="mt-1 block w-full rounded-md border-gray-300 py-2 pl-3 pr-10 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
			>
				<option value="">Default</option>
				{#each paramSets as paramSet}
					<option value={paramSet.id}>{paramSet.name} ({paramSet.id})</option>
				{/each}
			</select>
		</div>

		<div>
			<label for="priority" class="block text-sm font-medium text-gray-700"> Priority </label>
			<input
				type="number"
				id="priority"
				bind:value={priority}
				disabled={isSubmitting}
				min="0"
				max="100"
				class="mt-1 block w-full rounded-md border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-500"
			/>
			<p class="mt-1 text-xs text-gray-500">Higher values = higher priority (default: 0)</p>
		</div>

		{#if error}
			<div class="rounded-md bg-red-50 p-3" role="alert">
				<p class="text-sm text-red-800">{error}</p>
			</div>
		{/if}

		{#if success}
			<div class="rounded-md bg-green-50 p-3" role="alert">
				<p class="text-sm text-green-800">{success}</p>
			</div>
		{/if}

		<div class="flex justify-end">
			<button
				type="submit"
				disabled={isSubmitting}
				class="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-400 disabled:cursor-not-allowed"
			>
				{#if isSubmitting}
					<LoadingSpinner size="sm" />
					<span>Starting...</span>
				{:else}
					<span>Start Workflows</span>
				{/if}
			</button>
		</div>
	</form>
</div>
