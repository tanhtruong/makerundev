export function activityCount(count: number): string {
  return `${count} ${count === 1 ? "activity" : "activities"}`;
}
