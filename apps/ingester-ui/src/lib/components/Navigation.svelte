<script lang="ts">
	import { page } from '$app/stores';

	interface NavItem {
		href: string;
		label: string;
		icon: string;
	}

	const navItems: NavItem[] = [
		{ href: '/', label: 'Dashboard', icon: '📊' },
		{ href: '/batches', label: 'Batches', icon: '📦' },
		{ href: '/workflows', label: 'Workflows', icon: '⚙️' },
		{ href: '/definitions/workflows', label: 'Workflow Definitions', icon: '📋' },
		{ href: '/definitions/params', label: 'Parameter ', icon: '⚙️' },
		{ href: '/stats', label: 'Statistics', icon: '📈' }
	];

	let mobileMenuOpen = $state(false);

	function handleToggleMenu() {
		mobileMenuOpen = !mobileMenuOpen;
	}

	function handleCloseMenu() {
		mobileMenuOpen = false;
	}

	function isActive(href: string): boolean {
		if (href === '/') {
			return $page.url.pathname === '/';
		}
		return $page.url.pathname.startsWith(href);
	}
</script>

<nav class="bg-white shadow-sm" aria-label="Main navigation">
	<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
		<div class="flex h-16 justify-between">
			<div class="flex">
				<div class="flex flex-shrink-0 items-center">
					<h1 class="text-xl font-bold text-gray-900">Soliplex Ingester</h1>
				</div>
				<div class="hidden sm:ml-6 sm:flex sm:space-x-4">
					{#each navItems as item}
						<a
							href={item.href}
							class="inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium {isActive(
								item.href
							)
								? 'border-blue-500 text-gray-900'
								: 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'}"
							aria-current={isActive(item.href) ? 'page' : undefined}
						>
							<span class="mr-2" aria-hidden="true">{item.icon}</span>
							{item.label}
						</a>
					{/each}
				</div>
			</div>
			<div class="-mr-2 flex items-center sm:hidden">
				<button
					type="button"
					class="inline-flex items-center justify-center rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
					aria-controls="mobile-menu"
					aria-expanded={mobileMenuOpen}
					onclick={handleToggleMenu}
				>
					<span class="sr-only">Open main menu</span>
					{#if mobileMenuOpen}
						<svg
							class="h-6 w-6"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							aria-hidden="true"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							></path>
						</svg>
					{:else}
						<svg
							class="h-6 w-6"
							fill="none"
							stroke="currentColor"
							viewBox="0 0 24 24"
							aria-hidden="true"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M4 6h16M4 12h16M4 18h16"
							></path>
						</svg>
					{/if}
				</button>
			</div>
		</div>
	</div>

	{#if mobileMenuOpen}
		<div class="sm:hidden" id="mobile-menu">
			<div class="space-y-1 pb-3 pt-2">
				{#each navItems as item}
					<a
						href={item.href}
						class="block border-l-4 py-2 pl-3 pr-4 text-base font-medium {isActive(item.href)
							? 'border-blue-500 bg-blue-50 text-blue-700'
							: 'border-transparent text-gray-500 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-700'}"
						aria-current={isActive(item.href) ? 'page' : undefined}
						onclick={handleCloseMenu}
					>
						<span class="mr-2" aria-hidden="true">{item.icon}</span>
						{item.label}
					</a>
				{/each}
			</div>
		</div>
	{/if}
</nav>
