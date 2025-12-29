import { apiClient } from '$lib/services/apiClient';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	try {
		const paramSet = await apiClient.getParamSet(params.id);
		return {
			paramSet
		};
	} catch (err) {
		console.error('Failed to load parameter set:', err);
		throw error(404, 'Parameter set not found');
	}
};
