type LogFields = Record<string, unknown>;

function jsonValue(value: unknown): unknown {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(jsonValue);
  }
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, jsonValue(item)]),
    );
  }
  return String(value);
}

function baseEvent(event: string, level: "info" | "error") {
  return {
    schema_version: 1,
    timestamp: new Date().toISOString(),
    level,
    event,
    service: "frontend",
    container: process.env.HOSTNAME || null,
    environment: process.env.CLANKR_LOG_ENVIRONMENT || process.env.NODE_ENV || "development",
    run_kind: process.env.CLANKR_RUN_KIND || "normal",
    benchmark_run_id: process.env.BENCHMARK_RUN_ID || null,
    release_sha: process.env.RELEASE_SHA || null,
  };
}

/**
 * Emit a server-side JSON line. Do not pass cookies, headers, request bodies,
 * lyrics, audio metadata, or raw upstream responses as fields.
 */
export function logEvent(event: string, fields: LogFields = {}): void {
  const safeFields = jsonValue(fields) as LogFields;
  console.log(JSON.stringify({ ...baseEvent(event, "info"), ...safeFields }));
}

export function logError(event: string, error: unknown, fields: LogFields = {}): void {
  const errorType = error instanceof Error ? error.name : "UnknownError";
  const safeFields = jsonValue(fields) as LogFields;
  console.error(
    JSON.stringify({
      ...baseEvent(event, "error"),
      ...safeFields,
      error_type: errorType,
    }),
  );
}
