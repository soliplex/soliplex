// Error handling utilities

export class ApiError extends Error {
	constructor(
		message: string,
		public statusCode: number,
		public endpoint?: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

export class NetworkError extends Error {
	constructor(
		message: string,
		public endpoint?: string
	) {
		super(message);
		this.name = 'NetworkError';
	}
}

export function handleApiError(error: unknown, endpoint?: string): never {
	if (error instanceof Response) {
		throw new ApiError(`HTTP ${error.status}: ${error.statusText}`, error.status, endpoint);
	}

	if (error instanceof TypeError && error.message.includes('fetch')) {
		throw new NetworkError('Network error: Unable to connect to API', endpoint);
	}

	if (error instanceof Error) {
		throw error;
	}

	throw new Error('Unknown error occurred');
}

export function getErrorMessage(error: unknown): string {
	if (error instanceof ApiError) {
		return `API Error (${error.statusCode}): ${error.message}`;
	}

	if (error instanceof NetworkError) {
		return `Network Error: ${error.message}`;
	}

	if (error instanceof Error) {
		return error.message;
	}

	return 'An unknown error occurred';
}
