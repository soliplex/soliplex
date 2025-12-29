// API Type Definitions for Soliplex Ingester

// Enums
export enum RunStatus {
	PENDING = 'PENDING',
	RUNNING = 'RUNNING',
	COMPLETED = 'COMPLETED',
	ERROR = 'ERROR',
	FAILED = 'FAILED'
}

export enum WorkflowStepType {
	INGEST = 'ingest',
	VALIDATE = 'validate',
	PARSE = 'parse',
	CHUNK = 'chunk',
	EMBED = 'embed',
	STORE = 'store',
	ENRICH = 'enrich',
	ROUTE = 'route'
}

// Document Models
export interface Document {
	hash: string;
	mime_type: string;
	file_size: number;
	doc_meta: Record<string, unknown>;
	rag_id: string;
	batch_id: number;
}

export interface DocumentURI {
	id: number;
	doc_hash: string;
	uri: string;
	source: string;
	version: number;
	batch_id: number;
}

// Batch Models
export interface DocumentBatch {
	id: number;
	name: string;
	source: string;
	start_date: string;
	completed_date: string | null;
	batch_params: Record<string, unknown>;
	duration: number | null;
}

export interface BatchStatus {
	batch: DocumentBatch;
	document_count: number;
	workflow_count: Record<RunStatus, number>;
	workflows: WorkflowRun[];
	parsed: number;
	remaining: number;
}

// Workflow Models
export interface WorkflowRun {
	id: number;
	workflow_definition_id: string;
	run_group_id: number;
	batch_id: number;
	doc_id: string;
	priority: number;
	created_date: string;
	start_date: string | null;
	completed_date: string | null;
	status: RunStatus;
	status_date: string;
	status_message: string | null;
	status_meta: Record<string, unknown>;
	run_params: Record<string, unknown>;
	duration: number | null;
	steps?: RunStep[];
}

export interface RunStep {
	id: number;
	workflow_run_id: number;
	workflow_step_number: number;
	workflow_step_name: string;
	step_config_id: number;
	step_type: WorkflowStepType;
	is_last_step: boolean;
	created_date: string;
	priority: number;
	start_date: string | null;
	status_date: string;
	completed_date: string | null;
	retry: number;
	retries: number;
	status: RunStatus;
	status_message: string | null;
	status_meta: Record<string, unknown>;
	worker_id: string | null;
	duration: number | null;
}

export interface RunGroup {
	id: number;
	batch_id: number;
	workflow_definition_id: string;
	param_id: string;
	created_date: string;
	completed_date: string | null;
}

export interface RunGroupStats {
	run_group_id: number;
	total_runs: number;
	status_counts: Record<RunStatus, number>;
	avg_duration: number | null;
	min_duration: number | null;
	max_duration: number | null;
}

// Workflow Definition Models
export interface WorkflowDefinition {
	id: string;
	name: string;
	steps?: WorkflowStep[] | { items: WorkflowStep[] }; // Can be array or object with items
	items?: WorkflowStep[]; // Alternative location for steps
	metadata?: Record<string, unknown>;
}

export interface WorkflowStep {
	step_number: number;
	step_name: string;
	step_type: WorkflowStepType;
	handler: string;
	config: Record<string, unknown>;
	retry_config?: {
		max_retries: number;
		retry_delay: number;
	};
	is_last_step: boolean;
}

export interface WorkflowDefinitionSummary {
	id: string;
	name: string;
}

// Parameter Set Models
export interface WorkflowParams {
	id: string;
	name: string;
	target: string;
	embedding?: {
		model: string;
		provider: string;
		dimensions: number;
		batch_size?: number;
	};
	chunking?: {
		max_size: number;
		overlap: number;
		strategy: string;
		min_size?: number;
	};
	parsing?: {
		extract_tables: boolean;
		extract_images: boolean;
		ocr_enabled?: boolean;
		language?: string;
	};
	custom?: Record<string, unknown>;
}

export interface ParamSetSummary {
	id: string;
	name: string;
}

// API Response Models
export interface IngestResponse {
	batch_id: number;
	document_uri: string;
	document_hash: string;
	source: string;
	uri_id: number;
}

export interface CreateBatchResponse {
	batch_id: number;
}

export interface StartWorkflowsResponse {
	message: string;
	workflows: number;
	run_group: number;
}

export interface StartWorkflowsRequest {
	batch_id: number;
	workflow_definition_id?: string;
	priority?: number;
	param_id?: string;
}

export interface ApiError {
	error: string;
	status_code: number;
}

// Pagination Models
export interface PaginatedResponse<T> {
	items: T[];
	total: number;
	page: number;
	rows_per_page: number;
	total_pages: number;
}

export interface PaginationParams {
	page: number;
	rows_per_page: number;
}
