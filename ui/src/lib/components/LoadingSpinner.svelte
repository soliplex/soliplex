<script lang="ts">
	interface Props {
		size?: 'sm' | 'md' | 'lg';
		text?: string;
	}

	let { size = 'md', text }: Props = $props();

	const sizeClasses = {
		sm: 'h-4 w-4 border-2',
		md: 'h-8 w-8 border-3',
		lg: 'h-12 w-12 border-4'
	};
</script>

<div class="flex items-center justify-center gap-2">
	<div
		class="animate-spin rounded-full border-blue-600 border-t-transparent {sizeClasses[size]}"
		role="status"
		aria-label="Loading"
	></div>
	{#if text}
		<span class="text-sm text-gray-600">{text}</span>
	{/if}
</div>
