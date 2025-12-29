import { apiClient } from '$lib/services/apiClient';
import { RunStatus } from '$lib/types/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	try {
		const [runGroups, workflows] = await Promise.all([
			apiClient.getRunGroups(),
			apiClient.getWorkflowRuns()
		]);

		// Get stats for recent run groups
		const recentRunGroups = runGroups.slice(0, 10);
		const runGroupStats = await Promise.all(
			recentRunGroups.map(async (rg) => {
				try {
					const stats = await apiClient.getRunGroupStats(rg.id);
					return {
						runGroup: rg,
						stats
					};
				} catch {
					return null;
				}
			})
		);

		const validRunGroupStats = runGroupStats.filter((s) => s !== null);

		// Calculate overall statistics
		const totalWorkflows = workflows.length;
		const completedWorkflows = workflows.filter((w) => w.status === RunStatus.COMPLETED).length;
		const failedWorkflows = workflows.filter(
			(w) => w.status === RunStatus.FAILED || w.status === RunStatus.ERROR
		).length;
		const activeWorkflows = workflows.filter((w) => w.status === RunStatus.RUNNING).length;

		const successRate =
			totalWorkflows > 0 ? Math.round((completedWorkflows / totalWorkflows) * 100) : 0;

		// Calculate average duration from completed workflows
		const completedWithDuration = workflows.filter(
			(w) => w.status === RunStatus.COMPLETED && w.duration !== null
		);
		const avgDuration =
			completedWithDuration.length > 0
				? completedWithDuration.reduce((sum, w) => sum + (w.duration || 0), 0) /
					completedWithDuration.length
				: 0;

		return {
			systemStats: {
				totalWorkflows,
				completedWorkflows,
				failedWorkflows,
				activeWorkflows,
				successRate,
				avgDuration
			},
			runGroupStats: validRunGroupStats
		};
	} catch (error) {
		console.error('Failed to load statistics:', error);
		return {
			systemStats: {
				totalWorkflows: 0,
				completedWorkflows: 0,
				failedWorkflows: 0,
				activeWorkflows: 0,
				successRate: 0,
				avgDuration: 0
			},
			runGroupStats: [],
			error
		};
	}
};
