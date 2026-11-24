export function parseSearch(query: string): Record<string, string | string[]> {
  const params = new URLSearchParams(query);
  const search: Record<string, string | string[]> = {};
  for (const key of new Set(params.keys())) {
    const values = params.getAll(key);
    search[key] = values.length === 1 && values[0] !== undefined ? values[0] : values;
  }
  return search;
}

export function stringifySearch(search: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(search)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (typeof item === "string" || typeof item === "number" || typeof item === "boolean") {
        params.append(key, String(item));
      }
    }
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}
