import type { CaseView, Message, RequestView } from './generated/types.gen';
import type { TenderHackTransport } from './apiTransport';

export const STORED_CASE_KEY = 'tenderhack.current-case-id';
export const FOREGROUND_POLL_MS = 800;
export const BACKGROUND_POLL_MS = 3000;
export const HUMAN_FOREGROUND_POLL_MS = 1200;
export const HUMAN_BACKGROUND_POLL_MS = 4000;

export function dedupeMessages(messages: Message[] = []): Message[] {
  const byId = new Map<string, Message>();
  for (const message of messages) byId.set(message.message_id, message);
  return [...byId.values()].sort((left, right) => left.seq - right.seq);
}

export function normalizeCaseView(view: CaseView): CaseView {
  return { ...view, messages: dedupeMessages(view.messages) };
}

export function isInputPreservingError(status: number | null): boolean {
  return status === 409 || status === 429 || status === 503 || status === null;
}

export function readStoredCase(storage: Pick<Storage, 'getItem'>): string | null {
  const value = storage.getItem(STORED_CASE_KEY)?.trim();
  return value || null;
}

export type Wait = (milliseconds: number) => Promise<void>;

const defaultWait: Wait = (milliseconds) => new Promise((resolve) => {
  globalThis.setTimeout(resolve, milliseconds);
});

export interface PollResult {
  request: RequestView;
  caseView: CaseView | null;
}

export async function pollRequestUntilTerminal(
  transport: TenderHackTransport,
  requestId: string,
  caseId: string,
  isCurrentCase: (candidateCaseId: string) => boolean,
  wait: Wait = defaultWait,
  isHidden: () => boolean = () => globalThis.document?.hidden ?? false,
  onUpdate: (request: RequestView) => void = () => undefined,
): Promise<PollResult> {
  let latest: RequestView = { request_id: requestId, case_id: caseId, status: 'cancelled' };
  while (true) {
    if (!isCurrentCase(caseId)) return { request: latest, caseView: null };
    const request = await transport.getRequest(requestId);
    latest = request;
    if (!isCurrentCase(caseId) || request.case_id !== caseId) {
      return { request, caseView: null };
    }
    onUpdate(request);
    if (request.status === 'final' || request.status === 'error' || request.status === 'cancelled') {
      const caseView = await transport.getCase(caseId);
      return isCurrentCase(caseId)
        ? { request, caseView: normalizeCaseView(caseView) }
        : { request, caseView: null };
    }
    await wait(isHidden() ? BACKGROUND_POLL_MS : FOREGROUND_POLL_MS);
  }
}
