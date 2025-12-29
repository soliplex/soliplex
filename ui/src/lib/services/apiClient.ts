// API Client Service for Soliplex Ingester

import { API_BASE_URL, API_TIMEOUT } from '$lib/config/api';
import { handleApiError } from '$lib/utils/errors';
import type {
	DocumentBatch,
	BatchStatus,
	WorkflowRun,
	RunStep,
	RunGroup,
	RunGroupStats,
	WorkflowDefinition,
	WorkflowDefinitionSummary,
	WorkflowParams,
	ParamSetSummary,
	DocumentURI,
	RunStatus,
	PaginatedResponse,
	PaginationParams
} from '$lib/types/api';

class ApiClient {
	private baseUrl: string;
	private timeout: number;

	constructor(baseUrl: string = API_BASE_URL, timeout: number = API_TIMEOUT) {
		this.baseUrl = baseUrl;
		this.timeout = timeout;
	}

	private async fetchWithTimeout(url: string, options?: RequestInit): Promise<Response> {
		const controller = new AbortController();
		const timeoutId = setTimeout(() => controller.abort(), this.timeout);

		try {
			const response = await fetch(url, {
				...options,
				signal: controller.signal
			});
			clearTimeout(timeoutId);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.error || response.statusText);
			}

			return response;
		} catch (error) {
			clearTimeout(timeoutId);
			handleApiError(error, url);
		}
	}

	private async get<T>(endpoint: string, params?: Record<string, string | number>): Promise<T> {
		let url = `${this.baseUrl}${endpoint}`;

		if (params) {
			const searchParams = new URLSearchParams();
			Object.entries(params).forEach(([key, value]) => {
				searchParams.append(key, String(value));
			});
			url += `?${searchParams.toString()}`;
		}

		const response = await this.fetchWithTimeout(url);
		return response.json();
	}

	private async post<T>(endpoint: string, data?: Record<string, unknown> | FormData): Promise<T> {
		const isFormData = data instanceof FormData;

		const response = await this.fetchWithTimeout(`${this.baseUrl}${endpoint}`, {
			method: 'POST',
			headers: isFormData ? {} : { 'Content-Type': 'application/json' },
			body: isFormData ? data : JSON.stringify(data)
		});

		return response.json();
	}

	// Batch Endpoints

	async getBatches(): Promise<DocumentBatch[]> {
		return this.get<DocumentBatch[]>('/batch/');
	}

	async getBatchStatus(batchId: number): Promise<BatchStatus> {
		return this.get<BatchStatus>('/batch/status', { batch_id: batchId });
	}

	// Document Endpoints

	async getDocuments(batchId?: number, source?: string): Promise<DocumentURI[]> {
		const params: Record<string, number | string> = {};
		if (batchId) params.batch_id = batchId;
		if (source) params.source = source;
		return this.get<DocumentURI[]>('/document/', params);
	}

	// Workflow Endpoints

	async getWorkflowRuns(
		batchId?: number,
		paginationParams?: PaginationParams
	): Promise<WorkflowRun[] | PaginatedResponse<WorkflowRun>> {
		const params: Record<string, number> = {};
		if (batchId) params.batch_id = batchId;
		if (paginationParams) {
			params.page = paginationParams.page;
			params.rows_per_page = paginationParams.rows_per_page;
		}
		return this.get<WorkflowRun[] | PaginatedResponse<WorkflowRun>>('/workflow/', params);
	}

	async getWorkflowRunsByStatus(
		status: RunStatus,
		batchId?: number,
		paginationParams?: PaginationParams
	): Promise<WorkflowRun[] | PaginatedResponse<WorkflowRun>> {
		const params: Record<string, string | number> = { status };
		if (batchId) params.batch_id = batchId;
		if (paginationParams) {
			params.page = paginationParams.page;
			params.rows_per_page = paginationParams.rows_per_page;
		}
		return this.get<WorkflowRun[] | PaginatedResponse<WorkflowRun>>('/workflow/by-status', params);
	}

	async getWorkflowRunDetails(workflowId: number): Promise<WorkflowRun> {
		return this.get<WorkflowRun>(`/workflow/runs/${workflowId}`);
	}

	async getWorkflowSteps(status: RunStatus): Promise<RunStep[]> {
		return this.get<RunStep[]>('/workflow/steps', { status });
	}

	// Workflow Definition Endpoints

	async getWorkflowDefinitions(): Promise<WorkflowDefinitionSummary[]> {
		return this.get<WorkflowDefinitionSummary[]>('/workflow/definitions');
	}

	async getWorkflowDefinition(workflowId: string): Promise<WorkflowDefinition> {
		return this.get<WorkflowDefinition>(`/workflow/definitions/${workflowId}`);
	}

	// Parameter Set Endpoints

	async getParamSets(): Promise<ParamSetSummary[]> {
		return this.get<ParamSetSummary[]>('/workflow/param-sets');
	}

	async getParamSet(setId: string): Promise<WorkflowParams> {
		return this.get<WorkflowParams>(`/workflow/param-sets/${setId}`);
	}

	async getParamSetsByTarget(target: string): Promise<WorkflowParams[]> {
		return this.get<WorkflowParams[]>(`/workflow/param-sets/target/${target}`);
	}

	// Run Group Endpoints

	async getRunGroups(batchId?: number): Promise<RunGroup[]> {
		const params = batchId ? { batch_id: batchId } : undefined;
		return this.get<RunGroup[]>('/workflow/run-groups', params);
	}

	async getRunGroup(runGroupId: number): Promise<RunGroup> {
		return this.get<RunGroup>(`/workflow/run-groups/${runGroupId}`);
	}

	async getRunGroupStats(runGroupId: number): Promise<RunGroupStats> {
		return this.get<RunGroupStats>(`/workflow/run-groups/${runGroupId}/stats`);
	}

	// Batch Action Endpoints

	async startWorkflows(
		batchId: number,
		workflowDefinitionId?: string,
		priority?: number,
		paramId?: string
	): Promise<import('$lib/types/api').StartWorkflowsResponse> {
		const formData = new URLSearchParams();
		formData.append('batch_id', String(batchId));
		if (workflowDefinitionId) formData.append('workflow_definition_id', workflowDefinitionId);
		if (priority !== undefined) formData.append('priority', String(priority));
		if (paramId) formData.append('param_id', paramId);

		const response = await this.fetchWithTimeout(`${this.baseUrl}/batch/start-workflows`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
			body: formData.toString()
		});

		return response.json();
	}
}

// Export singleton instance
export const apiClient = new ApiClient();

// Export class for testing
export { ApiClient };
