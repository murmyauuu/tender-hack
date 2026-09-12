import { describe, expect, it, vi } from 'vitest';
import { RealApiTransport, resolveApiBaseUrl, resolveFrontendMode } from './apiTransport';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

describe('real A02 transport', () => {
  it('uses the generated client for sessions, chat, requests, cases, sources, feedback and handoff', async () => {
    const requests: Request[] = [];
    const fetchMock = vi.fn(async (request: Request) => {
      requests.push(request);
      const path = new URL(request.url).pathname;
      if (path === '/api/v1/sessions') return json({ session_id: 'session', created_at: 'now', expires_at: 'later' }, 201);
      if (path === '/api/v1/chat') return json({ request_id: 'request', case_id: 'case', user_message_id: 'message', case_version: 1, status: 'queued', trace_id: 'trace' }, 202);
      if (path === '/api/v1/requests/request') return json({ request_id: 'request', case_id: 'case', status: 'final', result_message_ids: [] });
      if (path === '/api/v1/cases/case') return json({ case: { case_id: 'case', session_id: 'session', status: 'open', case_version: 1, clarification_count: 0, created_at: 'now', updated_at: 'now' }, messages: [] });
      if (path === '/api/v1/sources/source') return json({ source_id: 'source', source_type: 'portal', title: 'Title', excerpt: 'Excerpt', content_status: 'complete' });
      if (path === '/api/v1/feedback') return json({ feedback_id: 'feedback', message_id: 'message', case_version: 2, case_status: 'resolved', outcome_applied: true }, 201);
      if (path === '/api/v1/cases/case/handoff') return json({ ticket_id: 'ticket', case_id: 'case', status: 'new', created_at: 'now', updated_at: 'now' }, 201);
      return json({}, 404);
    });
    const transport = new RealApiTransport('http://api.test', fetchMock as typeof fetch);

    await transport.createSession();
    await transport.sendMessage({ request_key: 'key', text: 'Question' });
    await transport.getRequest('request');
    await transport.getCase('case');
    await transport.getSource('source');
    await transport.saveFeedback({ message_id: 'message', useful: true });
    await transport.createHandoff('case', { request_key: 'handoff-key', expected_case_version: 2 });

    expect(requests.map((request) => `${request.method} ${new URL(request.url).pathname}`)).toEqual([
      'POST /api/v1/sessions',
      'POST /api/v1/chat',
      'GET /api/v1/requests/request',
      'GET /api/v1/cases/case',
      'GET /api/v1/sources/source',
      'POST /api/v1/feedback',
      'POST /api/v1/cases/case/handoff',
    ]);
    expect(requests.every((request) => request.credentials === 'include')).toBe(true);
  });

  it('keeps the A02 status and canonical error envelope', async () => {
    const transport = new RealApiTransport('http://api.test', vi.fn(async () => json({
      error: { code: 'QUEUE_FULL', message: 'Очередь заполнена', retryable: true, trace_id: 'trace', current_case_version: null },
    }, 429)) as typeof fetch);
    await expect(transport.sendMessage({ request_key: 'key', text: 'Question' })).rejects.toMatchObject({
      status: 429,
      detail: { code: 'QUEUE_FULL', message: 'Очередь заполнена' },
    });
  });

  it('selects modes explicitly and removes one trailing slash from API base URL', () => {
    expect(resolveFrontendMode('real')).toBe('real');
    expect(resolveFrontendMode('mock')).toBe('mock');
    expect(resolveFrontendMode(undefined)).toBe('mock');
    expect(resolveApiBaseUrl('http://api.test/', 'http://ignored')).toBe('http://api.test');
  });
});
