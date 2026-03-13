import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getStageColor(stage: string): string {
  switch (stage.toUpperCase()) {
    case 'ACTIVE':
      return '#10b981'; // green-500
    case 'WARM':
      return '#f59e0b'; // amber-500
    case 'DORMANT':
      return '#f97316'; // orange-500
    case 'COLD':
      return '#ef4444'; // red-500
    case 'AT_RISK':
      return '#dc2626'; // red-600
    default:
      return '#6b7280'; // gray-500
  }
}

export function getDaysAgo(dateString: string): number {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays;
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
