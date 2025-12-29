<script lang="ts">
	interface Props {
		title: string;
		value: string | number;
		description?: string;
		icon?: string;
		href?: string;
		trend?: {
			value: number;
			isPositive: boolean;
		};
	}

	let { title, value, description, icon, href, trend }: Props = $props();
</script>

{#snippet content()}
	<div class="flex items-center">
		{#if icon}
			<div class="flex-shrink-0">
				<span class="text-3xl" aria-hidden="true">{icon}</span>
			</div>
		{/if}
		<div class={icon ? 'ml-5 w-0 flex-1' : 'w-full'}>
			<dl>
				<dt class="truncate text-sm font-medium text-gray-500">{title}</dt>
				<dd class="flex items-baseline">
					<div class="text-2xl font-semibold text-gray-900">{value}</div>
					{#if trend}
						<div
							class="ml-2 flex items-baseline text-sm font-semibold {trend.isPositive
								? 'text-green-600'
								: 'text-red-600'}"
						>
							{trend.isPositive ? '↑' : '↓'}
							{Math.abs(trend.value)}%
						</div>
					{/if}
				</dd>
				{#if description}
					<dd class="mt-1 text-xs text-gray-600">{description}</dd>
				{/if}
			</dl>
		</div>
	</div>
{/snippet}

{#if href}
	<a
		{href}
		class="block overflow-hidden rounded-lg bg-white px-4 py-5 shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 sm:p-6"
	>
		{@render content()}
	</a>
{:else}
	<div class="overflow-hidden rounded-lg bg-white px-4 py-5 shadow sm:p-6">
		{@render content()}
	</div>
{/if}
