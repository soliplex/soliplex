<script lang="ts">
	import { RunStatus } from '$lib/types/api';

	interface Props {
		status: RunStatus;
		compact?: boolean;
	}

	let { status, compact = false }: Props = $props();

	const statusConfig = {
		[RunStatus.PENDING]: {
			color: 'bg-gray-100 text-gray-800 border-gray-300',
			icon: '⏸',
			label: 'Pending'
		},
		[RunStatus.RUNNING]: {
			color: 'bg-blue-100 text-blue-800 border-blue-300',
			icon: '⟳',
			label: 'Running'
		},
		[RunStatus.COMPLETED]: {
			color: 'bg-green-100 text-green-800 border-green-300',
			icon: '✓',
			label: 'Completed'
		},
		[RunStatus.ERROR]: {
			color: 'bg-orange-100 text-orange-800 border-orange-300',
			icon: '⚠',
			label: 'Error'
		},
		[RunStatus.FAILED]: {
			color: 'bg-red-100 text-red-800 border-red-300',
			icon: '✗',
			label: 'Failed'
		}
	};

	const config = $derived(statusConfig[status]);
</script>

<span
	class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-medium {config.color}"
	role="status"
	aria-label={config.label}
>
	<span class={status === RunStatus.RUNNING ? 'animate-spin' : ''} aria-hidden="true">
		{config.icon}
	</span>
	{#if !compact}
		<span>{config.label}</span>
	{/if}
</span>
