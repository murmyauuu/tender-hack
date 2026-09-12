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
});
