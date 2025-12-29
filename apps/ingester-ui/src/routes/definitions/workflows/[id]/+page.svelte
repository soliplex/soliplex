<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import JsonViewer from '$lib/components/JsonViewer.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// Extract steps from various possible response structures
	const getSteps = (definition: typeof data.definition) => {
		// Check if steps is directly an array
		if (Array.isArray(definition.steps)) {
			return definition.steps;
		}
		// Check if steps is an object with items property
		if (definition.steps && typeof definition.steps === 'object' && 'items' in definition.steps) {
			return (definition.steps as { items: any[] }).items;
		}
		// Check if items is at the root level
		if (Array.isArray(definition.items)) {
			return definition.items;
		}
		return [];
	};

	const sortedSteps = $derived(
		getSteps(data.definition).sort((a, b) => a.step_number - b.step_number)
	);
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Workflow Definition: {data.definition.name}">
		{#snippet actions()}
			<a
				href="/definitions/workflows"
				class="text-sm font-medium text-gray-600 hover:text-gray-900"
			>
				← Back to definitions
			</a>
		{/snippet}
	</PageHeader>

	<div class="mt-6">
		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="px-6 py-5">
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
					<div>
						<dt class="text-sm font-medium text-gray-500">Definition ID</dt>
						<dd class="mt-1 font-mono text-sm text-gray-900">{data.definition.id}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Name</dt>
						<dd class="mt-1 text-sm text-gray-900">{data.definition.name}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Total Steps</dt>
						<dd class="mt-1 text-sm text-gray-900">{sortedSteps.length}</dd>
					</div>
				</div>
			</div>
		</div>

		<div class="mt-8">
			<h2 class="mb-4 text-lg font-semibold text-gray-900">Workflow Steps</h2>
			{#if sortedSteps.length === 0}
				<div class="rounded-lg bg-white p-8 text-center text-gray-500 shadow">
					<p>No steps defined in this workflow</p>
				</div>
			{:else}
				<div class="space-y-4">
					{#each sortedSteps as step (step.step_number)}
						<div class="overflow-hidden rounded-lg border border-gray-200 bg-white">
							<div class="bg-gray-50 px-6 py-4">
								<div class="flex items-center gap-3">
									<span
										class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white"
									>
										{step.step_number}
									</span>
									<div>
										<h3 class="font-semibold text-gray-900">{step.step_name}</h3>
										<p class="text-sm text-gray-600">Type: {step.step_type}</p>
									</div>
								</div>
							</div>
							<div class="px-6 py-4">
								<dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
									<div>
										<dt class="text-sm font-medium text-gray-500">Handler</dt>
										<dd class="mt-1 font-mono text-xs text-gray-900">{step.handler}</dd>
									</div>
									<div>
										<dt class="text-sm font-medium text-gray-500">Is Last Step</dt>
										<dd class="mt-1 text-sm text-gray-900">
											{step.is_last_step ? 'Yes' : 'No'}
										</dd>
									</div>
								</dl>
								{#if Object.keys(step.config).length > 0}
									<div class="mt-4">
										<h4 class="text-sm font-medium text-gray-700">Configuration</h4>
										<pre
											class="mt-2 overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-900">{JSON.stringify(
												step.config,
												null,
												2
											)}</pre>
									</div>
								{/if}
								{#if step.retry_config}
									<div class="mt-4">
										<h4 class="text-sm font-medium text-gray-700">Retry Configuration</h4>
										<pre
											class="mt-2 overflow-x-auto rounded bg-gray-50 p-3 text-xs text-gray-900">{JSON.stringify(
												step.retry_config,
												null,
												2
											)}</pre>
									</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		{#if data.definition.metadata && Object.keys(data.definition.metadata).length > 0}
			<div class="mt-8">
				<JsonViewer data={data.definition.metadata} title="Workflow Metadata" />
			</div>
		{/if}

		<div class="mt-8">
			<JsonViewer data={data.definition} title="Complete Definition (JSON)" />
		</div>
	</div>
</div>
