<script lang="ts">
	import type { WorkflowDefinitionSummary, ParamSetSummary } from '$lib/types/api';

	interface Props {
		definition: WorkflowDefinitionSummary | ParamSetSummary;
		type: 'workflow' | 'param';
	}

	let { definition, type }: Props = $props();

	const href = $derived(
		type === 'workflow'
			? `/definitions/workflows/${definition.id}`
			: `/definitions/params/${definition.id}`
	);
</script>

<a
	{href}
	class="block rounded-lg border border-gray-200 bg-white p-5 transition hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
>
	<div class="flex items-start justify-between">
		<div class="flex-1">
			<h3 class="text-lg font-semibold text-gray-900">
				{definition.name}
			</h3>
			<p class="mt-1 text-sm text-gray-600">
				ID: <span class="font-mono text-xs">{definition.id}</span>
			</p>
		</div>
		<div class="ml-4">
			<span class="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800">
				{type === 'workflow' ? 'Workflow' : 'Parameters'}
			</span>
		</div>
	</div>
	<div class="mt-4 flex items-center text-sm text-blue-600">
		<span>View details</span>
		<svg
			class="ml-1 h-4 w-4"
			fill="none"
			stroke="currentColor"
			viewBox="0 0 24 24"
			aria-hidden="true"
		>
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
		</svg>
	</div>
</a>
