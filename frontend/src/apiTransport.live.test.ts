import { describe, expect, it } from 'vitest';
import { RealApiTransport } from './apiTransport';

declare const process: { env: Record<string, string | undefined> };
const liveUrl = process.env.B02_LIVE_API_URL;

function cookieAwareFetch(): typeof fetch {
  let cookie = '';
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const headers = new Headers(request.headers);
    headers.set('Origin', 'http://127.0.0.1:5173');
    if (cookie) headers.set('Cookie', cookie);
    const response = await fetch(new Request(request, { headers }));
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) cookie = setCookie.split(';', 1)[0];
    return response;
  }) as typeof fetch;
}

describe('B02 live HTTP smoke', () => {
  it.skipIf(!liveUrl)('runs session, chat, poll, case, source and feedback against A02 HTTP', async () => {
    const transport = new RealApiTransport(liveUrl, cookieAwareFetch());
    const session = await transport.createSession();
    expect(session.session_id).toBeTruthy();

    const accepted = await transport.sendMessage({
      request_key: crypto.randomUUID(),
      text: 'Как подписать контракт?',
    });
    let request = await transport.getRequest(accepted.request_id);
    for (let attempt = 0; attempt < 30 && request.status !== 'final'; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      request = await transport.getRequest(accepted.request_id);
    }
    expect(request.status).toBe('final');

    const caseView = await transport.getCase(accepted.case_id);
    const answer = caseView.messages?.find((message) => message.kind === 'answer');
    expect(answer?.structured_content?.steps).toEqual(['Откройте карточку контракта.']);
    expect(await transport.getSource(answer!.source_ids![0])).toMatchObject({ source_id: 'source-demo' });
    expect(await transport.saveFeedback({ message_id: answer!.message_id, useful: true })).toMatchObject({
      message_id: answer!.message_id,
      outcome_applied: false,
    });
  });
});
