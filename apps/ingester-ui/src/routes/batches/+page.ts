import { apiClient } from '$lib/services/apiClient';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	try {
		const batches = await apiClient.getBatches();
		return {
			batches
		};
	} catch (error) {
		console.error('Failed to load batches:', error);
		return {
			batches: [],
			error
		};
	}
};
