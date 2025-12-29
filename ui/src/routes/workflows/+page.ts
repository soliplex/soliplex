import { apiClient } from '$lib/services/apiClient';
import { RunStatus } from '$lib/types/api';
import type { PageLoad } from './$types';
import type { WorkflowRun, PaginatedResponse } from '$lib/types/api';

const DEFAULT_ROWS_PER_PAGE = 20;

export const load: PageLoad = async ({ url }) => {
	try {
		const statusParam = url.searchParams.get('status');
		const batchIdParam = url.searchParams.get('batch_id');
		const pageParam = url.searchParams.get('page');
		const limitParam = url.searchParams.get('limit');

		const batchId = batchIdParam ? parseInt(batchIdParam) : undefined;
		const page = pageParam ? parseInt(pageParam) : 1;
		const limit = limitParam ? parseInt(limitParam) : DEFAULT_ROWS_PER_PAGE;

		// Validate page and limit
		if (page < 1 || limit < 1) {
			throw new Error('Invalid pagination parameters');
		}

		const paginationParams = { page, rows_per_page: limit };
		let workflowRuns: WorkflowRun[] | PaginatedResponse<WorkflowRun>;

		// Call appropriate endpoint with pagination
		if (statusParam && Object.values(RunStatus).includes(statusParam as RunStatus)) {
			workflowRuns = await apiClient.getWorkflowRunsByStatus(
				statusParam as RunStatus,
				batchId,
				paginationParams
			);
		} else {
			workflowRuns = await apiClient.getWorkflowRuns(batchId, paginationParams);
		}

		return {
			workflowRuns,
			filters: {
				status: statusParam as RunStatus | null,
				batchId
			},
			pagination: {
				page,
				limit
			}
		};
	} catch (error) {
		console.error('Failed to load workflows:', error);
		return {
			workflowRuns: [],
			filters: {
				status: null,
				batchId: undefined
			},
			pagination: {
				page: 1,
				limit: DEFAULT_ROWS_PER_PAGE
			},
			error
		};
	}
};
