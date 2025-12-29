import { apiClient } from '$lib/services/apiClient';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	try {
		const paramSets = await apiClient.getParamSets();
		return {
			paramSets
		};
	} catch (error) {
		console.error('Failed to load parameter sets:', error);
		return {
			paramSets: [],
			error
		};
	}
};
