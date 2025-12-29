// API Configuration

// Application runs client-side only (SSR disabled)
// In development: Use relative URL to leverage Vite proxy (avoids CORS)
// In production: Use environment variable or default
export const API_BASE_URL = import.meta.env.DEV
	? import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
	: '/api/v1';

export const API_TIMEOUT = 30000; // 30 seconds

export const POLL_INTERVAL = 10000; // 10 seconds for dashboard
export const WORKFLOW_POLL_INTERVAL = 5000; // 5 seconds for workflow details
