<script lang="ts">
	interface Props {
		currentPage: number;
		totalPages: number;
		totalItems: number;
		itemsPerPage: number;
		onPageChange?: (page: number) => void;
		onPageSizeChange?: (pageSize: number) => void;
	}

	let {
		currentPage,
		totalPages,
		totalItems,
		itemsPerPage,
		onPageChange,
		onPageSizeChange
	}: Props = $props();

	const pageSizeOptions = [20, 50, 100];

	// Calculate displayed items range
	const startItem = $derived((currentPage - 1) * itemsPerPage + 1);
	const endItem = $derived(Math.min(currentPage * itemsPerPage, totalItems));

	// Calculate visible page numbers (show max 7 pages)
	const visiblePages = $derived.by(() => {
		const pages: (number | string)[] = [];
		const maxVisible = 7;

		if (totalPages <= maxVisible) {
			// Show all pages
			for (let i = 1; i <= totalPages; i++) {
				pages.push(i);
			}
		} else {
			// Always show first page
			pages.push(1);

			if (currentPage > 3) {
				pages.push('...');
			}

			// Show current page and neighbors
			const start = Math.max(2, currentPage - 1);
			const end = Math.min(totalPages - 1, currentPage + 1);

			for (let i = start; i <= end; i++) {
				pages.push(i);
			}

			if (currentPage < totalPages - 2) {
				pages.push('...');
			}

			// Always show last page
			pages.push(totalPages);
		}

		return pages;
	});

	function handlePageClick(page: number) {
		if (page !== currentPage && page >= 1 && page <= totalPages) {
			onPageChange?.(page);
		}
	}

	function handlePageSizeChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const newSize = parseInt(target.value);
		onPageSizeChange?.(newSize);
	}

	function handlePrevious() {
		if (currentPage > 1) {
			handlePageClick(currentPage - 1);
		}
	}

	function handleNext() {
		if (currentPage < totalPages) {
			handlePageClick(currentPage + 1);
		}
	}
</script>

<div
	class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between rounded-lg bg-white p-4 shadow"
>
	<!-- Results info and page size selector -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
		<div class="text-sm text-gray-700">
			Showing <span class="font-medium">{startItem}</span> to
			<span class="font-medium">{endItem}</span> of
			<span class="font-medium">{totalItems}</span> results
		</div>

		<div class="flex items-center gap-2">
			<label for="page-size" class="text-sm text-gray-700">Rows per page:</label>
			<select
				id="page-size"
				class="rounded-md border-gray-300 py-1.5 pl-3 pr-8 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
				value={itemsPerPage}
				onchange={handlePageSizeChange}
			>
				{#each pageSizeOptions as size}
					<option value={size}>{size}</option>
				{/each}
			</select>
		</div>
	</div>

	<!-- Page navigation -->
	<nav class="flex items-center gap-1" aria-label="Pagination">
		<!-- Previous button -->
		<button
			type="button"
			onclick={handlePrevious}
			disabled={currentPage === 1}
			class="inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-md
        {currentPage === 1
					? 'text-gray-400 cursor-not-allowed'
					: 'text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500'}"
			aria-label="Previous page"
		>
			<svg
				class="h-5 w-5"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
		</button>

		<!-- Page numbers -->
		{#each visiblePages as pageNum}
			{#if pageNum === '...'}
				<span class="px-3 py-2 text-sm text-gray-700">...</span>
			{:else}
				<button
					type="button"
					onclick={() => handlePageClick(pageNum as number)}
					class="min-w-[2.5rem] px-3 py-2 text-sm font-medium rounded-md
            {pageNum === currentPage
						? 'bg-blue-600 text-white'
						: 'text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500'}"
					aria-label="Page {pageNum}"
					aria-current={pageNum === currentPage ? 'page' : undefined}
				>
					{pageNum}
				</button>
			{/if}
		{/each}

		<!-- Next button -->
		<button
			type="button"
			onclick={handleNext}
			disabled={currentPage === totalPages}
			class="inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-md
        {currentPage === totalPages
					? 'text-gray-400 cursor-not-allowed'
					: 'text-gray-700 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500'}"
			aria-label="Next page"
		>
			<svg
				class="h-5 w-5"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				aria-hidden="true"
			>
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
			</svg>
		</button>
	</nav>
</div>
