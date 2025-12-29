<script lang="ts">
	interface Column {
		key: string;
		label: string;
		format?: (value: unknown) => string;
	}

	interface Props {
		columns: Column[];
		data: Record<string, unknown>[];
		onRowClick?: (row: Record<string, unknown>) => void;
	}

	let { columns, data, onRowClick }: Props = $props();

	function handleRowClick(row: Record<string, unknown>) {
		if (onRowClick) {
			onRowClick(row);
		}
	}

	function formatValue(value: unknown, column: Column): string {
		if (column.format) {
			return column.format(value);
		}
		if (value === null || value === undefined) {
			return '—';
		}
		return String(value);
	}
</script>

<div class="overflow-x-auto">
	<table class="min-w-full divide-y divide-gray-200">
		<thead class="bg-gray-50">
			<tr>
				{#each columns as column}
					<th
						scope="col"
						class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
					>
						{column.label}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody class="divide-y divide-gray-200 bg-white">
			{#each data as row}
				<tr
					class={onRowClick ? 'cursor-pointer hover:bg-gray-50' : ''}
					onclick={() => handleRowClick(row)}
				>
					{#each columns as column}
						<td class="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
							{formatValue(row[column.key], column)}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
