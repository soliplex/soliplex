<script lang="ts">
	import type { RunStep } from '$lib/types/api';
	import { RunStatus } from '$lib/types/api';
	import StatusBadge from './StatusBadge.svelte';
	import { formatDuration, formatDateTime } from '$lib/utils/format';

	interface Props {
		steps: RunStep[];
	}

	let { steps }: Props = $props();

	let expandedSteps = $state<Set<number>>(new Set());

	function handleToggleStep(stepId: number) {
		if (expandedSteps.has(stepId)) {
			expandedSteps.delete(stepId);
		} else {
			expandedSteps.add(stepId);
		}
		expandedSteps = new Set(expandedSteps);
	}

	function getStepIcon(status: RunStatus): string {
		switch (status) {
			case RunStatus.COMPLETED:
				return '✓';
			case RunStatus.RUNNING:
				return '⟳';
			case RunStatus.PENDING:
				return '⏸';
			case RunStatus.ERROR:
				return '⚠';
			case RunStatus.FAILED:
				return '✗';
			default:
				return '•';
		}
	}

	function getStepColor(status: RunStatus): string {
		switch (status) {
			case RunStatus.COMPLETED:
				return 'text-green-600';
			case RunStatus.RUNNING:
				return 'text-blue-600 animate-pulse';
			case RunStatus.PENDING:
				return 'text-gray-400';
			case RunStatus.ERROR:
				return 'text-orange-600';
			case RunStatus.FAILED:
				return 'text-red-600';
			default:
				return 'text-gray-500';
		}
	}

	const sortedSteps = $derived(
		[...steps].sort((a, b) => a.workflow_step_number - b.workflow_step_number)
	);
</script>

<div class="space-y-2">
	{#each sortedSteps as step (step.id)}
		<div class="rounded-lg border border-gray-200 bg-white">
			<button
				type="button"
				class="w-full px-4 py-3 text-left hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
				onclick={() => handleToggleStep(step.id)}
			>
				<div class="flex items-center gap-3">
					<span class="text-lg {getStepColor(step.status)}" aria-hidden="true">
						{getStepIcon(step.status)}
					</span>
					<div class="flex-1">
						<div class="flex items-center gap-2">
							<span class="font-medium text-gray-900">
								{step.workflow_step_number}. {step.workflow_step_name}
							</span>
							<StatusBadge status={step.status} compact={true} />
						</div>
						<div class="mt-1 text-xs text-gray-500">
							Type: {step.step_type}
							{#if step.duration !== null}
								• Duration: {formatDuration(step.duration)}
							{/if}
						</div>
					</div>
					<svg
						class="h-5 w-5 text-gray-400 transition-transform {expandedSteps.has(step.id)
							? 'rotate-180'
							: ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						aria-hidden="true"
					>
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"
						></path>
					</svg>
				</div>
			</button>

			{#if expandedSteps.has(step.id)}
				<div class="border-t border-gray-200 bg-gray-50 px-4 py-3">
					<dl class="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
						<div>
							<dt class="font-medium text-gray-700">Status</dt>
							<dd class="mt-1 text-gray-900">{step.status}</dd>
						</div>
						<div>
							<dt class="font-medium text-gray-700">Started</dt>
							<dd class="mt-1 text-gray-900">{formatDateTime(step.start_date)}</dd>
						</div>
						<div>
							<dt class="font-medium text-gray-700">Completed</dt>
							<dd class="mt-1 text-gray-900">{formatDateTime(step.completed_date)}</dd>
						</div>
						<div>
							<dt class="font-medium text-gray-700">Duration</dt>
							<dd class="mt-1 text-gray-900">{formatDuration(step.duration)}</dd>
						</div>
						<div>
							<dt class="font-medium text-gray-700">Retries</dt>
							<dd class="mt-1 text-gray-900">{step.retry}/{step.retries}</dd>
						</div>
						{#if step.worker_id}
							<div>
								<dt class="font-medium text-gray-700">Worker</dt>
								<dd class="mt-1 text-gray-900">{step.worker_id}</dd>
							</div>
						{/if}
					</dl>
					{#if step.status_message}
						<div class="mt-3">
							<dt class="font-medium text-gray-700">Status Message</dt>
							<dd class="mt-1 text-gray-900">{step.status_message}</dd>
						</div>
					{/if}
					{#if Object.keys(step.status_meta).length > 0}
						<div class="mt-3">
							<dt class="font-medium text-gray-700">Metadata</dt>
							<dd class="mt-1">
								<pre
									class="overflow-x-auto rounded bg-gray-100 p-2 text-xs text-gray-900">{JSON.stringify(
										step.status_meta,
										null,
										2
									)}</pre>
							</dd>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/each}
</div>
