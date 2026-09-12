import { describe, expect, it, vi } from 'vitest';
import type { TenderHackTransport } from './apiTransport';
import type { CaseView, Message, RequestView } from './generated';
import { dedupeMessages, isInputPreservingError, pollRequestUntilTerminal, readStoredCase, STORED_CASE_KEY } from './realChat';

const message = (id: string, seq: number): Message => ({
  message_id: id, case_id: 'case', seq, role: 'user', kind: 'question', content: id, created_at: 'now',
});

const caseView: CaseView = {
  case: { case_id: 'case', session_id: 'session', status: 'awaiting_feedback', case_version: 2, clarification_count: 0, created_at: 'now', updated_at: 'now' },
  messages: [message('second', 2), message('first', 1), message('second', 2)],
};

const transport = (requests: RequestView[]): TenderHackTransport => ({
  mode: 'real',
  createSession: vi.fn(),
  sendMessage: vi.fn(),
  getRequest: vi.fn(async () => requests.shift()!),
  getCase: vi.fn(async () => caseView),
  getSource: vi.fn(),
  saveFeedback: vi.fn(),
});

describe('real chat orchestration', () => {
  it('deduplicates history by message_id and restores server order', () => {
    expect(dedupeMessages(caseView.messages).map((item) => item.message_id)).toEqual(['first', 'second']);
  });

  it('polls at the foreground interval and reloads Case after terminal Request', async () => {
    const api = transport([
      { request_id: 'request', case_id: 'case', status: 'processing', progress: 'retrieving' },
      { request_id: 'request', case_id: 'case', status: 'final', result_message_ids: ['answer'] },
    ]);
    const waits: number[] = [];
    const updates: string[] = [];
    const result = await pollRequestUntilTerminal(
      api,
      'request',
      'case',
      () => true,
      async (milliseconds) => { waits.push(milliseconds); },
      () => false,
      (request) => updates.push(request.status),
    );
    expect(waits).toEqual([800]);
    expect(updates).toEqual(['processing', 'final']);
    expect(result.caseView?.messages?.map((item) => item.message_id)).toEqual(['first', 'second']);
  });

  it('drops a late result when the user has switched to another case', async () => {
    const api = transport([{ request_id: 'old-request', case_id: 'old-case', status: 'final' }]);
    const result = await pollRequestUntilTerminal(api, 'old-request', 'old-case', () => false, async () => undefined);
    expect(result.caseView).toBeNull();
    expect(api.getRequest).not.toHaveBeenCalled();
    expect(api.getCase).not.toHaveBeenCalled();
  });

  it('preserves input for stale, overload, storage and network rejection', () => {
    expect([409, 429, 503, null].every(isInputPreservingError)).toBe(true);
    expect(isInputPreservingError(422)).toBe(false);
  });

  it('restores only a non-empty case id from browser storage', () => {
    expect(readStoredCase({ getItem: (key) => key === STORED_CASE_KEY ? ' case ' : null })).toBe('case');
    expect(readStoredCase({ getItem: () => ' ' })).toBeNull();
  });
});
