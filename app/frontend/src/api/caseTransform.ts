/**
 * Recursively converts snake_case object keys to camelCase.
 *
 * The real backend's 360°-view endpoints (Customer Detail, Contract Detail) are built
 * directly on top of Postgres tables that use snake_case columns (`recovery_score`,
 * `risk_segment`, ...). This codebase's convention is to keep Zod schemas themselves
 * idiomatic camelCase TypeScript rather than smuggling snake_case field names into the
 * schema — so this mapper sits between the raw fetch and the schema parse in
 * `apiRequest` (see `api/client.ts`), normalizing whatever shape the server sends before
 * validation runs.
 *
 * It's a no-op for objects that are already camelCase (e.g. today's MSW fixtures), so it
 * is safe to apply unconditionally now and will keep working unchanged once a real
 * snake_case-emitting backend lands behind the same endpoint.
 */
export function snakeToCamelDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => snakeToCamelDeep(item));
  }
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, val]) => [snakeToCamel(key), snakeToCamelDeep(val)]),
    );
  }
  return value;
}

function snakeToCamel(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_match, char: string) => char.toUpperCase());
}
