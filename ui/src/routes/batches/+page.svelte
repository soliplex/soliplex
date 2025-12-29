<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import BatchList from '$lib/components/BatchList.svelte';
	import ErrorMessage from '$lib/components/ErrorMessage.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
	<PageHeader title="Batches" description="View and manage document batches" />

	{#if data.error}
		<div class="mt-6">
			<ErrorMessage error={data.error} />
		</div>
	{:else}
		<div class="mt-6">
			<BatchList batches={data.batches} />
		</div>
	{/if}
</div>
