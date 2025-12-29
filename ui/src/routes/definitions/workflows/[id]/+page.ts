import { apiClient } from '$lib/services/apiClient';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	try {
		const definition = await apiClient.getWorkflowDefinition(params.id);
		return {
			definition
		};
	} catch (err) {
		console.error('Failed to load workflow definition:', err);
		throw error(404, 'Workflow definition not found');
	}
};
