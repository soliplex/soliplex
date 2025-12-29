import { apiClient } from '$lib/services/apiClient';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	try {
		const workflowId = parseInt(params.id);

		if (isNaN(workflowId)) {
			throw error(400, 'Invalid workflow ID');
		}

		const workflow = await apiClient.getWorkflowRunDetails(workflowId);

		return {
			workflow
		};
	} catch (err) {
		console.error('Failed to load workflow:', err);
		throw error(404, 'Workflow not found');
	}
};
