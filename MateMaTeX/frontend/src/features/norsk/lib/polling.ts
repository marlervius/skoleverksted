/** Exponential backoff for generation status polling (starts at ~2s, caps ~8s). */
export function nextPollDelayMs(attempt: number): number {
  return Math.min(Math.round(2000 * Math.pow(1.35, attempt)), 8000);
}
