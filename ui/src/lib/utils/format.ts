// Formatting utilities

export function formatDuration(seconds: number | null): string {
	if (seconds === null || seconds === undefined) {
		return '—';
	}

	if (seconds < 60) {
		return `${Math.round(seconds)}s`;
	}

	const minutes = Math.floor(seconds / 60);
	const remainingSeconds = Math.round(seconds % 60);

	if (minutes < 60) {
		return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
	}

	const hours = Math.floor(minutes / 60);
	const remainingMinutes = minutes % 60;

	return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

export function formatRelativeTime(dateString: string): string {
	const date = new Date(dateString);
	const now = new Date();
	const diffMs = now.getTime() - date.getTime();
	const diffSeconds = Math.floor(diffMs / 1000);

	if (diffSeconds < 60) {
		return 'just now';
	}

	const diffMinutes = Math.floor(diffSeconds / 60);
	if (diffMinutes < 60) {
		return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;
	}

	const diffHours = Math.floor(diffMinutes / 60);
	if (diffHours < 24) {
		return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
	}

	const diffDays = Math.floor(diffHours / 24);
	if (diffDays < 30) {
		return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
	}

	return date.toLocaleDateString();
}

export function formatDateTime(dateString: string | null): string {
	if (!dateString) {
		return '—';
	}

	const date = new Date(dateString);
	return date.toLocaleString();
}

export function formatDate(dateString: string | null): string {
	if (!dateString) {
		return '—';
	}

	const date = new Date(dateString);
	return date.toLocaleDateString();
}

export function truncateText(text: string, maxLength: number): string {
	if (text.length <= maxLength) {
		return text;
	}
	return text.substring(0, maxLength) + '...';
}
