import answerFixture from '../../contracts/fixtures/answer.json';
import clarifyFixture from '../../contracts/fixtures/clarify.json';
import errorFixture from '../../contracts/fixtures/error.json';
import handoffFixture from '../../contracts/fixtures/handoff_offered.json';
import operatorFixture from '../../contracts/fixtures/operator.json';
import policyFixture from '../../contracts/fixtures/policy.json';
import staleFixture from '../../contracts/fixtures/stale.json';
import ticketFixture from '../../contracts/fixtures/ticket.json';
import type {
  CandidateSource,
  CaseView,
  ChatInput,
  FeedbackInput,
  FeedbackResponse,
  HandoffInput,
  RequestView,
  SourceRecord,
  Ticket,
} from './generated';

export const fixtureNames = [
  'answer',
  'clarify',
  'handoff_offered',
  'ticket',
  'operator',
  'policy',
  'error',
  'stale',
] as const;

export type FixtureName = (typeof fixtureNames)[number];
export type ScenarioName = 'queued' | 'retrieving' | 'candidate' | 'retry' | FixtureName;

type FrozenErrorEnvelope = typeof errorFixture | typeof staleFixture;

const cases: Record<Exclude<FixtureName, 'error' | 'stale'>, CaseView> = {
  answer: answerFixture as unknown as CaseView,
  clarify: clarifyFixture as unknown as CaseView,
  handoff_offered: handoffFixture as unknown as CaseView,
  ticket: ticketFixture as unknown as CaseView,
  operator: operatorFixture as unknown as CaseView,
  policy: policyFixture as unknown as CaseView,
};

const answerCase = cases.answer;
const answerMessage = (answerCase.messages ?? []).find((message) => message.kind === 'answer');
const sourceId = answerMessage?.source_ids?.[0] ?? 'source-demo';

const candidate: CandidateSource = {
  source_id: sourceId,
  title: sourceId,
  source_type: 'unknown',
};

const requestBase: Omit<RequestView, 'status' | 'progress' | 'candidate_sources'> = {
  request_id: '33333333-3333-4333-8333-333333333333',
  case_id: answerCase.case.case_id,
  result_message_ids: [],
  error: null,
  timings_ms: {},
};

export const transitionalRequests: Record<'queued' | 'retrieving' | 'candidate' | 'retry', RequestView> = {
  queued: { ...requestBase, status: 'queued', progress: 'queued', candidate_sources: [] },
  retrieving: { ...requestBase, status: 'processing', progress: 'retrieving', candidate_sources: [] },
  candidate: {
    ...requestBase,
    status: 'processing',
    progress: 'sources_found',
    candidate_sources: [candidate],
  },
  retry: {
    ...requestBase,
    status: 'error',
    progress: null,
    candidate_sources: [],
    error: { code: 'GENERATION_FAILED', message: 'Не удалось получить ответ', retryable: true },
  },
};

export type MockAction =
  | { operation: 'POST /api/v1/feedback'; body: FeedbackInput }
  | { operation: 'POST /api/v1/chat'; body: ChatInput }
  | { operation: 'POST /api/v1/cases/{case_id}/handoff'; caseId: string; body: HandoffInput };

export class MockTransport {
  readonly mode = 'mock' as const;
  readonly actions: MockAction[] = [];
  private readonly handoffReceipts = new Map<string, Ticket>();

  getCase(name: ScenarioName): CaseView | null {
    if (name === 'queued' || name === 'retrieving' || name === 'candidate' || name === 'retry') return answerCase;
    if (name === 'error' || name === 'stale') return null;
    return cases[name];
  }

  getRequest(name: ScenarioName): RequestView | null {
    if (name === 'queued' || name === 'retrieving' || name === 'candidate' || name === 'retry') {
      return transitionalRequests[name];
    }
    return null;
  }

  getError(name: ScenarioName): FrozenErrorEnvelope | null {
    if (name === 'error') return errorFixture;
    if (name === 'stale') return staleFixture;
    return null;
  }

  getSource(_sourceId: string): SourceRecord | null {
    // C0 freezes no SourceRecord fixture. The drawer deliberately renders unavailable.
    return null;
  }

  async saveFeedback(body: FeedbackInput, caseVersion: number, caseStatus: FeedbackResponse['case_status']) {
    this.actions.push({ operation: 'POST /api/v1/feedback', body });
    return {
      feedback_id: crypto.randomUUID(),
      message_id: body.message_id,
      case_version: caseVersion,
      case_status: caseStatus,
      outcome_applied: body.solved !== null && body.solved !== undefined,
      outcome_reason: null,
    } satisfies FeedbackResponse;
  }

  async sendMessage(body: ChatInput) {
    this.actions.push({ operation: 'POST /api/v1/chat', body });
  }

  async createHandoff(caseId: string, body: HandoffInput): Promise<Ticket> {
    this.actions.push({ operation: 'POST /api/v1/cases/{case_id}/handoff', caseId, body });
    const existing = this.handoffReceipts.get(caseId);
    if (existing) return existing;
    if (caseId !== cases.handoff_offered.case.case_id || body.expected_case_version !== cases.handoff_offered.case.case_version) {
      throw new Error('STALE_CASE_VERSION');
    }
    const ticket = cases.ticket.ticket;
    if (!ticket) throw new Error('Fixture Ticket is missing');
    this.handoffReceipts.set(caseId, ticket);
    return ticket;
  }
}

export const mockTransport = new MockTransport();
