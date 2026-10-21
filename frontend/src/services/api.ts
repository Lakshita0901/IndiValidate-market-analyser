import { AnalyzeRequest, HealthResponse, MarketValidationReport } from '../types';

// Default to relative URL so Vite proxy forwards to http://127.0.0.1:8000 during dev,
// or use explicit VITE_API_BASE_URL if configured.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  status?: number;
  details?: unknown;
  retryAfter?: number;

  constructor(message: string, status?: number, details?: unknown, retryAfter?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

/**
 * Check backend health status without invoking heavy LLM or scraper operations.
 */
export async function checkBackendHealth(): Promise<HealthResponse> {
  const url = `${API_BASE_URL}/health`;
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 4000);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new ApiError(`Health check failed with status ${response.status}`, response.status);
    }

    return await response.json();
  } catch (error: unknown) {
    if (error instanceof ApiError) {
      throw error;
    }
    const msg = error instanceof Error ? error.message : 'Backend connection unavailable';
    throw new ApiError(msg, 0);
  }
}

/**
 * Execute the full multi-persona market validation pipeline.
 * Since the LangGraph pipeline is synchronous and evaluates 10 personas,
 * this request may take ~30-90 seconds. An AbortSignal can be passed to cancel.
 */
export async function analyzeMarketIdea(
  request: AnalyzeRequest,
  signal?: AbortSignal
): Promise<MarketValidationReport> {
  const url = `${API_BASE_URL}/api/analyze`;

  // Clean payload: ensure required idea string is non-empty and optional values are well-formed
  const payload: Record<string, unknown> = {
    idea: request.idea.trim(),
  };

  if (request.founder_context) {
    payload.founder_context = request.founder_context;
  }
  if (typeof request.persona_count === 'number' && request.persona_count > 0) {
    payload.persona_count = request.persona_count;
  }
  if (typeof request.evaluation_concurrency === 'number' && request.evaluation_concurrency > 0) {
    payload.evaluation_concurrency = request.evaluation_concurrency;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('Analysis was cancelled by user', 499);
    }
    const msg = error instanceof Error ? error.message : 'Network error communicating with backend';
    throw new ApiError(`Failed to reach IndiValidate API: ${msg}. Verify FastAPI is running at http://127.0.0.1:8000.`, 0);
  }

  if (!response.ok) {
    let errorDetail = `Pipeline request failed (HTTP ${response.status})`;
    let parsedBody: unknown = null;
    const retryAfterHeader = response.headers.get('Retry-After');
    const retryAfterSeconds = retryAfterHeader ? parseInt(retryAfterHeader, 10) : undefined;

    try {
      parsedBody = await response.json();
      if (parsedBody && typeof parsedBody === 'object' && 'detail' in parsedBody) {
        const detail = (parsedBody as { detail: unknown }).detail;
        if (typeof detail === 'string') {
          errorDetail = detail;
        } else if (Array.isArray(detail)) {
          // Pydantic validation error array
          errorDetail = detail
            .map((err) => `${err.loc?.join('.') || 'field'}: ${err.msg}`)
            .join('; ');
        }
      }
    } catch {
      // Body wasn't JSON
    }

    // Never expose raw stack traces, API keys, or raw secrets in the frontend
    errorDetail = errorDetail.split('Traceback (most recent call last):')[0].trim();
    errorDetail = errorDetail.replace(/(Bearer\s+)[A-Za-z0-9_\-\.]{8,}/gi, '$1[REDACTED]');
    errorDetail = errorDetail.replace(/(api[_-]?key['":\s=]+)[A-Za-z0-9_\-\.]{8,}/gi, '$1[REDACTED]');
    errorDetail = errorDetail.replace(/(mistral[_-]?api[_-]?key['":\s=]+)[A-Za-z0-9_\-\.]{8,}/gi, '$1[REDACTED]');

    const isRateLimit =
      response.status === 429 ||
      errorDetail.includes('1300') ||
      errorDetail.toLowerCase().includes('rate limit') ||
      errorDetail.toLowerCase().includes('too many requests');

    if (isRateLimit) {
      throw new ApiError(
        'Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.',
        429,
        parsedBody,
        retryAfterSeconds
      );
    }

    if (response.status === 422) {
      throw new ApiError(`Validation error: ${errorDetail}`, 422, parsedBody);
    } else if (response.status === 500) {
      if (errorDetail.toLowerCase().includes('quota') || errorDetail.toLowerCase().includes('resourceexhausted')) {
        throw new ApiError(
          'Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.',
          429,
          parsedBody,
          retryAfterSeconds
        );
      }
      throw new ApiError(`Backend analysis error: ${errorDetail}`, 500, parsedBody);
    }

    throw new ApiError(errorDetail, response.status, parsedBody, retryAfterSeconds);
  }

  const reportData = await response.json();
  if (!reportData || typeof reportData !== 'object' || !reportData.report_id) {
    throw new ApiError('Received malformed report payload from backend API', 500, reportData);
  }

  return reportData as MarketValidationReport;
}
