import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, RealApiTransport, type TenderHackTransport } from './apiTransport';
import type {
  CaseView,
  ErrorDetail,
  FeedbackInput,
  RequestView,
  SourceRecord,
} from './generated/types.gen';
import {
  normalizeCaseView,
  pollRequestUntilTerminal,
  readStoredCase,
  STORED_CASE_KEY,
} from './realChat';

export interface RealChatModel {
  connection: 'connecting' | 'ready' | 'error';
  caseView: CaseView | null;
  request: RequestView | null;
  error: ErrorDetail | null;
  source: SourceRecord | null;
  sourceLoading: boolean;
  sending: boolean;
  sendMessage(text: string): Promise<boolean>;
  saveFeedback(input: FeedbackInput): Promise<void>;
  openSource(sourceId: string): Promise<void>;
  closeSource(): void;
  newTopic(): void;
}

const clientError = (error: unknown): ErrorDetail => error instanceof ApiError
  ? error.detail
  : {
      code: 'CLIENT_ERROR',
      message: error instanceof Error ? error.message : 'Неизвестная ошибка клиента',
      retryable: true,
      trace_id: 'client-no-trace',
      current_case_version: null,
    };

export function useRealChat(
  suppliedTransport?: TenderHackTransport,
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> = globalThis.localStorage,
): RealChatModel {
  const transport = useMemo(
    () => suppliedTransport ?? new RealApiTransport(),
    [suppliedTransport],
  );
  const [connection, setConnection] = useState<RealChatModel['connection']>('connecting');
  const [caseView, setCaseView] = useState<CaseView | null>(null);
  const [request, setRequest] = useState<RequestView | null>(null);
  const [error, setError] = useState<ErrorDetail | null>(null);
  const [source, setSource] = useState<SourceRecord | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const currentCaseId = useRef<string | null>(null);
  const generation = useRef(0);
  const pendingSubmission = useRef<{
    text: string;
    caseId: string | null;
    expectedVersion: number | null;
    requestKey: string;
  } | null>(null);

  const isCurrent = useCallback(
    (candidate: string, token: number) => currentCaseId.current === candidate && generation.current === token,
    [],
  );

  const loadCase = useCallback(async (caseId: string, token = generation.current) => {
    try {
      const loaded = normalizeCaseView(await transport.getCase(caseId));
      if (isCurrent(caseId, token)) setCaseView(loaded);
      return loaded;
    } catch (caught) {
      if (isCurrent(caseId, token)) setError(clientError(caught));
      return null;
    }
  }, [isCurrent, transport]);

  const followRequest = useCallback(async (requestId: string, caseId: string, token: number) => {
    try {
      const result = await pollRequestUntilTerminal(
        transport,
        requestId,
        caseId,
        (candidate) => isCurrent(candidate, token),
        undefined,
        undefined,
        (next) => { if (isCurrent(caseId, token)) setRequest(next); },
      );
      if (!isCurrent(caseId, token)) return;
      setRequest(result.request);
      if (result.caseView) setCaseView(result.caseView);
    } catch (caught) {
      if (isCurrent(caseId, token)) setError(clientError(caught));
    }
  }, [isCurrent, transport]);

  useEffect(() => {
    let cancelled = false;
    void transport.createSession().then(async () => {
      if (cancelled) return;
      setConnection('ready');
      const restoredCaseId = readStoredCase(storage);
      if (!restoredCaseId) return;
      currentCaseId.current = restoredCaseId;
      const token = generation.current;
      const restored = await loadCase(restoredCaseId, token);
      const activeRequestId = restored?.case.active_request_id;
      if (activeRequestId && isCurrent(restoredCaseId, token)) {
        void followRequest(activeRequestId, restoredCaseId, token);
      }
    }).catch((caught) => {
      if (!cancelled) {
        setConnection('error');
        setError(clientError(caught));
      }
    });
    return () => { cancelled = true; generation.current += 1; };
  }, [followRequest, isCurrent, loadCase, storage, transport]);

  const sendMessage = useCallback(async (text: string): Promise<boolean> => {
    const trimmed = text.trim();
    if (!trimmed || sending) return false;
    setSending(true);
    setError(null);
    const previousCaseId = currentCaseId.current;
    const expectedVersion = caseView?.case.case_id === previousCaseId
      ? caseView.case.case_version
      : null;
    const previousSubmission = pendingSubmission.current;
    const requestKey = previousSubmission?.text === trimmed
      && previousSubmission.caseId === previousCaseId
      && previousSubmission.expectedVersion === expectedVersion
      ? previousSubmission.requestKey
      : crypto.randomUUID();
    pendingSubmission.current = {
      text: trimmed,
      caseId: previousCaseId,
      expectedVersion,
      requestKey,
    };
    try {
      const accepted = await transport.sendMessage({
        case_id: previousCaseId,
        expected_case_version: expectedVersion,
        request_key: requestKey,
        text: trimmed,
        retry_of: null,
      });
      generation.current += 1;
      const token = generation.current;
      currentCaseId.current = accepted.case_id;
      storage.setItem(STORED_CASE_KEY, accepted.case_id);
      pendingSubmission.current = null;
      setRequest({
        request_id: accepted.request_id,
        case_id: accepted.case_id,
        status: accepted.status,
        progress: accepted.status === 'queued' ? 'queued' : null,
        candidate_sources: [],
        result_message_ids: [],
        error: null,
        timings_ms: {},
      });
      void loadCase(accepted.case_id, token);
      void followRequest(accepted.request_id, accepted.case_id, token);
      return true;
    } catch (caught) {
      const apiError = caught instanceof ApiError ? caught : new ApiError(null, caught);
      setError(apiError.detail);
      if (apiError.status === 409 && previousCaseId) await loadCase(previousCaseId);
      return false;
    } finally {
      setSending(false);
    }
  }, [caseView, followRequest, loadCase, sending, storage, transport]);

  const saveFeedback = useCallback(async (input: FeedbackInput) => {
    setError(null);
    try {
      await transport.saveFeedback(input);
      if (currentCaseId.current) await loadCase(currentCaseId.current);
    } catch (caught) {
      setError(clientError(caught));
      if (caught instanceof ApiError && caught.status === 409 && currentCaseId.current) {
        await loadCase(currentCaseId.current);
      }
      throw caught;
    }
  }, [loadCase, transport]);

  const openSource = useCallback(async (sourceId: string) => {
    const token = generation.current;
    const caseId = currentCaseId.current;
    setSourceLoading(true);
    setSource(null);
    try {
      const loaded = await transport.getSource(sourceId);
      if (generation.current === token && currentCaseId.current === caseId) setSource(loaded);
    } catch (caught) {
      if (generation.current === token) setError(clientError(caught));
    } finally {
      if (generation.current === token) setSourceLoading(false);
    }
  }, [transport]);

  const closeSource = useCallback(() => { setSource(null); setSourceLoading(false); }, []);

  const newTopic = useCallback(() => {
    generation.current += 1;
    currentCaseId.current = null;
    storage.removeItem(STORED_CASE_KEY);
    pendingSubmission.current = null;
    setCaseView(null);
    setRequest(null);
    setError(null);
    setSource(null);
  }, [storage]);

  return {
    connection,
    caseView,
    request,
    error,
    source,
    sourceLoading,
    sending,
    sendMessage,
    saveFeedback,
    openSource,
    closeSource,
    newTopic,
  };
}
