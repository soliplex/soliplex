import { apiClient } from '$lib/services/apiClient';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	try {
		const batchId = parseInt(params.id);

		if (isNaN(batchId)) {
			throw error(400, 'Invalid batch ID');
		}

		const [batchStatus, workflows, workflowDefinitions, paramSets] = await Promise.all([
			apiClient.getBatchStatus(batchId),
			apiClient.getWorkflowRuns(batchId),
			apiClient.getWorkflowDefinitions(),
			apiClient.getParamSets()
		]);

		return {
			batchId,
			batch: batchStatus.batch,
			documentCount: batchStatus.document_count,
			workflowCounts: batchStatus.workflow_count,
			workflows,
			parsed: batchStatus.parsed,
			remaining: batchStatus.remaining,
			workflowDefinitions,
			paramSets
		};
	} catch (err) {
		console.error('Failed to load batch:', err);
		throw error(404, 'Batch not found');
	}
};
