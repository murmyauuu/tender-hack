import { describe, expect, it } from 'vitest';
import { fixtureNames, MockTransport, transitionalRequests } from './mockTransport';

describe('frozen fixture transport', () => {
  it('exposes every shared C0 fixture', () => {
    expect(fixtureNames).toEqual(['answer', 'clarify', 'handoff_offered', 'ticket', 'operator', 'policy', 'error', 'stale']);
    const transport = new MockTransport();
    for (const name of fixtureNames) {
      expect(transport.getCase(name) ?? transport.getError(name)).not.toBeNull();
    }
  });

  it('uses generated RequestView-compatible progress states without scores', () => {
    expect(transitionalRequests.queued.progress).toBe('queued');
    expect(transitionalRequests.retrieving.progress).toBe('retrieving');
    expect(transitionalRequests.candidate.candidate_sources).toHaveLength(1);
    expect(JSON.stringify(transitionalRequests)).not.toContain('score');
  });

  it('sends the first useful click as canonical feedback input', async () => {
    const transport = new MockTransport();
    await transport.saveFeedback({ message_id: '55555555-5555-4555-8555-555555555555', useful: true, reason_codes: [] }, 2, 'awaiting_feedback');
    expect(transport.actions[0]).toEqual({
      operation: 'POST /api/v1/feedback',
      body: { message_id: '55555555-5555-4555-8555-555555555555', useful: true, reason_codes: [] },
    });
  });

  it('creates at most one Ticket per Case and sends the current version', async () => {
    const transport = new MockTransport();
    const body = { request_key: 'handoff-key', expected_case_version: 2 };
    const first = await transport.createHandoff('22222222-2222-4222-8222-222222222222', body);
    const second = await transport.createHandoff('22222222-2222-4222-8222-222222222222', { ...body, request_key: 'another-key' });
    expect(second.ticket_id).toBe(first.ticket_id);
    expect(new Set([first.ticket_id, second.ticket_id]).size).toBe(1);
    expect(transport.actions[0]).toMatchObject({ operation: 'POST /api/v1/cases/{case_id}/handoff', body: { expected_case_version: 2 } });
  });

  it('represents retry with retry_of and no duplicate user text', async () => {
    const transport = new MockTransport();
    await transport.sendMessage({ case_id: 'case', expected_case_version: 7, request_key: 'retry-key', text: null, retry_of: 'failed-request' });
    expect(transport.actions[0]).toEqual({
      operation: 'POST /api/v1/chat',
      body: { case_id: 'case', expected_case_version: 7, request_key: 'retry-key', text: null, retry_of: 'failed-request' },
    });
  });
});
