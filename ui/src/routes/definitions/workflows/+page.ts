import { apiClient } from '$lib/services/apiClient';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	try {
		const definitions = await apiClient.getWorkflowDefinitions();
		return {
			definitions
		};
	} catch (error) {
		console.error('Failed to load workflow definitions:', error);
		return {
			definitions: [],
			error
		};
	}
};
