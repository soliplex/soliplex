<script lang="ts">
	import '../app.css';
	import Navigation from '$lib/components/Navigation.svelte';

	let { children } = $props();
</script>

<div class="min-h-screen bg-gray-50">
	<Navigation />
	<main>
		{@render children()}
	</main>
</div>
