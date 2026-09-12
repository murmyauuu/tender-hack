import {
  acceptChatApiV1ChatPost,
  createHandoffApiV1CasesCaseIdHandoffPost,
  createSessionApiV1SessionsPost,
  getCaseApiV1CasesCaseIdGet,
  getRequestApiV1RequestsRequestIdGet,
  getSourceApiV1SourcesSourceIdGet,
  saveFeedbackApiV1FeedbackPost,
} from './generated/sdk.gen';
import { createClient } from './generated/client/client.gen';
import type {
  AcceptedRequest,
  CaseView,
  ChatInput,
  ErrorEnvelope,
  FeedbackInput,
  FeedbackResponse,
  HandoffInput,
  RequestView,
  Session,
  SourceRecord,
  Ticket,
} from './generated/types.gen';

export type FrontendMode = 'mock' | 'real';

export interface TenderHackTransport {
  readonly mode: FrontendMode;
  createSession(): Promise<Session>;
  sendMessage(input: ChatInput): Promise<AcceptedRequest>;
  getRequest(requestId: string): Promise<RequestView>;
  getCase(caseId: string): Promise<CaseView>;
  getSource(sourceId: string): Promise<SourceRecord>;
  saveFeedback(input: FeedbackInput): Promise<FeedbackResponse>;
  createHandoff(caseId: string, input: HandoffInput): Promise<Ticket>;
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly detail: ErrorEnvelope['error'];

  constructor(status: number | null, error: unknown) {
    const envelope = isErrorEnvelope(error) ? error : null;
    const fallback = error instanceof Error ? error.message : 'Не удалось связаться с API';
    super(envelope?.error.message ?? fallback);
    this.name = 'ApiError';
    this.status = status;
    this.detail = envelope?.error ?? {
      code: status === null ? 'NETWORK_ERROR' : `HTTP_${status}`,
      message: fallback,
      retryable: status === null || status >= 500,
      trace_id: 'client-no-trace',
      current_case_version: null,
    };
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== 'object' || !('error' in value)) return false;
  const error = (value as { error?: unknown }).error;
  return Boolean(error && typeof error === 'object' && 'code' in error && 'message' in error);
}

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response?: Response;
};

function unwrap<T>(result: ApiResult<T>): T {
  if (result.data !== undefined) return result.data;
  throw new ApiError(result.response?.status ?? null, result.error);
}

export function resolveApiBaseUrl(
  configured = import.meta.env.VITE_API_BASE_URL,
  origin = globalThis.location?.origin,
): string {
  const value = configured?.trim();
  if (value) return value.replace(/\/$/, '');
  if (origin) return origin;
  return 'http://127.0.0.1:8000';
}

export function resolveFrontendMode(configured = import.meta.env.VITE_API_MODE): FrontendMode {
  return configured === 'real' ? 'real' : 'mock';
}

export class RealApiTransport implements TenderHackTransport {
  readonly mode = 'real' as const;
  private readonly apiClient;

  constructor(baseUrl = resolveApiBaseUrl(), fetchImpl: typeof fetch = globalThis.fetch) {
    this.apiClient = createClient({
      baseUrl,
      credentials: 'include',
      fetch: fetchImpl,
      responseStyle: 'fields',
    });
  }

  async createSession(): Promise<Session> {
    return unwrap(await createSessionApiV1SessionsPost({ client: this.apiClient }));
  }

  async sendMessage(input: ChatInput): Promise<AcceptedRequest> {
    return unwrap(await acceptChatApiV1ChatPost({ body: input, client: this.apiClient }));
  }

  async getRequest(requestId: string): Promise<RequestView> {
    return unwrap(await getRequestApiV1RequestsRequestIdGet({
      client: this.apiClient,
      path: { request_id: requestId },
    }));
  }

  async getCase(caseId: string): Promise<CaseView> {
    return unwrap(await getCaseApiV1CasesCaseIdGet({
      client: this.apiClient,
      path: { case_id: caseId },
    }));
  }

  async getSource(sourceId: string): Promise<SourceRecord> {
    return unwrap(await getSourceApiV1SourcesSourceIdGet({
      client: this.apiClient,
      path: { source_id: sourceId },
    }));
  }

  async saveFeedback(input: FeedbackInput): Promise<FeedbackResponse> {
    return unwrap(await saveFeedbackApiV1FeedbackPost({ body: input, client: this.apiClient }));
  }

  async createHandoff(caseId: string, input: HandoffInput): Promise<Ticket> {
    return unwrap(await createHandoffApiV1CasesCaseIdHandoffPost({
      body: input,
      client: this.apiClient,
      path: { case_id: caseId },
    }));
  }
}
