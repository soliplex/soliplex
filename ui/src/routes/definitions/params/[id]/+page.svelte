<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import JsonViewer from '$lib/components/JsonViewer.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Parameter Set: {data.paramSet.name}">
		{#snippet actions()}
			<a href="/definitions/params" class="text-sm font-medium text-gray-600 hover:text-gray-900">
				← Back to parameters
			</a>
		{/snippet}
	</PageHeader>

	<div class="mt-6">
		<div class="overflow-hidden rounded-lg bg-white shadow">
			<div class="px-6 py-5">
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
					<div>
						<dt class="text-sm font-medium text-gray-500">Parameter Set ID</dt>
						<dd class="mt-1 font-mono text-sm text-gray-900">{data.paramSet.id}</dd>
					</div>
					<div>
						<dt class="text-sm font-medium text-gray-500">Name</dt>
						<dd class="mt-1 text-sm text-gray-900">{data.paramSet.name}</dd>
					</div>
					<div class="sm:col-span-2">
						<dt class="text-sm font-medium text-gray-500">Target</dt>
						<dd class="mt-1 font-mono text-sm text-gray-900">{data.paramSet.target}</dd>
					</div>
				</div>
			</div>
		</div>

		{#if data.paramSet.embedding}
			<div class="mt-6 overflow-hidden rounded-lg bg-white shadow">
				<div class="border-b border-gray-200 bg-gray-50 px-6 py-4">
					<h3 class="text-base font-semibold text-gray-900">Embedding Configuration</h3>
				</div>
				<div class="px-6 py-4">
					<dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div>
							<dt class="text-sm font-medium text-gray-500">Model</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.embedding.model}</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Provider</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.embedding.provider}</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Dimensions</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.embedding.dimensions}</dd>
						</div>
						{#if data.paramSet.embedding.batch_size}
							<div>
								<dt class="text-sm font-medium text-gray-500">Batch Size</dt>
								<dd class="mt-1 text-sm text-gray-900">{data.paramSet.embedding.batch_size}</dd>
							</div>
						{/if}
					</dl>
				</div>
			</div>
		{/if}

		{#if data.paramSet.chunking}
			<div class="mt-6 overflow-hidden rounded-lg bg-white shadow">
				<div class="border-b border-gray-200 bg-gray-50 px-6 py-4">
					<h3 class="text-base font-semibold text-gray-900">Chunking Configuration</h3>
				</div>
				<div class="px-6 py-4">
					<dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div>
							<dt class="text-sm font-medium text-gray-500">Strategy</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.chunking.strategy}</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Max Size</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.chunking.max_size} tokens</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Overlap</dt>
							<dd class="mt-1 text-sm text-gray-900">{data.paramSet.chunking.overlap} tokens</dd>
						</div>
						{#if data.paramSet.chunking.min_size}
							<div>
								<dt class="text-sm font-medium text-gray-500">Min Size</dt>
								<dd class="mt-1 text-sm text-gray-900">{data.paramSet.chunking.min_size} tokens</dd>
							</div>
						{/if}
					</dl>
				</div>
			</div>
		{/if}

		{#if data.paramSet.parsing}
			<div class="mt-6 overflow-hidden rounded-lg bg-white shadow">
				<div class="border-b border-gray-200 bg-gray-50 px-6 py-4">
					<h3 class="text-base font-semibold text-gray-900">Parsing Configuration</h3>
				</div>
				<div class="px-6 py-4">
					<dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div>
							<dt class="text-sm font-medium text-gray-500">Extract Tables</dt>
							<dd class="mt-1 text-sm text-gray-900">
								{data.paramSet.parsing.extract_tables ? 'Yes' : 'No'}
							</dd>
						</div>
						<div>
							<dt class="text-sm font-medium text-gray-500">Extract Images</dt>
							<dd class="mt-1 text-sm text-gray-900">
								{data.paramSet.parsing.extract_images ? 'Yes' : 'No'}
							</dd>
						</div>
						{#if data.paramSet.parsing.ocr_enabled !== undefined}
							<div>
								<dt class="text-sm font-medium text-gray-500">OCR Enabled</dt>
								<dd class="mt-1 text-sm text-gray-900">
									{data.paramSet.parsing.ocr_enabled ? 'Yes' : 'No'}
								</dd>
							</div>
						{/if}
						{#if data.paramSet.parsing.language}
							<div>
								<dt class="text-sm font-medium text-gray-500">Language</dt>
								<dd class="mt-1 text-sm text-gray-900">{data.paramSet.parsing.language}</dd>
							</div>
						{/if}
					</dl>
				</div>
			</div>
		{/if}

		{#if data.paramSet.custom && Object.keys(data.paramSet.custom).length > 0}
			<div class="mt-6">
				<JsonViewer data={data.paramSet.custom} title="Custom Parameters" />
			</div>
		{/if}

		<div class="mt-6">
			<JsonViewer data={data.paramSet} title="Complete Parameter Set (JSON)" />
		</div>
	</div>
</div>
