import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { ApiError, type TenderHackTransport } from './apiTransport';
import type { AcceptedRequest, ChatInput, HandoffInput } from './generated';
import { mockTransport } from './mockTransport';

const select = (name: string) => fireEvent.click(screen.getByRole('button', { name }));

describe('TenderHack fixture UI', () => {
  it('renders all frozen fixture scenarios and transitional states', () => {
    render(<App />);
    expect(screen.getByText('Тестовый ответ по инструкции.')).toBeTruthy();
    expect(screen.getByText('Действуйте от имени поставщика.')).toBeTruthy();
    expect(screen.getByText('Откройте карточку контракта.')).toBeTruthy();
    select('Queued'); expect(screen.getByText('Запрос в очереди')).toBeTruthy();
    select('Retrieval'); expect(screen.getByText('Ищу подходящую инструкцию')).toBeTruthy();
    select('Candidate source'); expect(screen.getByTestId('candidate').textContent).toContain('ещё не ответ');
    select('Clarification'); expect(screen.getByText('Уточните, вы поставщик или заказчик?')).toBeTruthy();
    select('Handoff offered'); expect(screen.getByText('Передать специалисту нашего сервиса')).toBeTruthy();
    select('Ticket'); expect(screen.getByText('Ожидаем ответа специалиста нашего сервиса')).toBeTruthy();
    select('Operator reply'); expect(screen.getByText('Ответ специалиста в тестовом сценарии.')).toBeTruthy();
    select('Policy closure'); expect(screen.getByText(/обнаружена нецензурная лексика/)).toBeTruthy(); expect((screen.getByLabelText('Сообщение') as HTMLTextAreaElement).disabled).toBe(true);
    select('Generic error'); expect(screen.getByText('Хранилище временно недоступно')).toBeTruthy();
    select('Stale/version'); expect(screen.getAllByText('Состояние обращения изменилось')).toHaveLength(2);
  });

  it('orders source, conditions and steps and opens an honest source drawer', () => {
    render(<App />);
    const source = screen.getByRole('heading', { name: 'Источник' });
    const conditions = screen.getByRole('heading', { name: 'Условия' });
    const steps = screen.getByRole('heading', { name: 'Шаги' });
    expect(source.compareDocumentPosition(conditions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(conditions.compareDocumentPosition(steps) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Открыть источник/ }));
    expect(screen.getByRole('dialog', { name: 'Источник' }).textContent).toContain('Карточка источника недоступна');
  });

  it('keeps useful separate from solved and sends useful immediately', () => {
    render(<App />);
    const feedback = screen.getByLabelText('Оценка ответа');
    const before = mockTransport.actions.length;
    fireEvent.click(within(feedback).getByRole('button', { name: 'Да' }));
    expect(mockTransport.actions).toHaveLength(before + 1);
    expect(mockTransport.actions.at(-1)).toMatchObject({ operation: 'POST /api/v1/feedback', body: { useful: true } });
    expect(within(feedback).getByText('Вопрос решён?')).toBeTruthy();
  });

  it('shows specialist rating only for a real operator answer state', () => {
    render(<App />);
    expect(screen.queryByText('Оценка специалиста')).toBeNull();
    expect(screen.getByText('Тестовый ответ по инструкции.').closest('article')?.classList.contains('operator')).toBe(false);
    select('Operator reply');
    expect(screen.getByText('Оценка специалиста')).toBeTruthy();
    const before = mockTransport.actions.length;
    fireEvent.click(screen.getByRole('button', { name: '5 из 5' }));
    expect(mockTransport.actions).toHaveLength(before + 1);
    expect(mockTransport.actions.at(-1)).toMatchObject({ operation: 'POST /api/v1/feedback', body: { message_id: '77777777-7777-4777-8777-777777777777', specialist_rating: 5 } });
  });

  it('does not expose forbidden internal fields', () => {
    const { container } = render(<App />);
    expect(container.textContent).not.toMatch(/retrieval score|prompt|VRAM|trace-error-demo/i);
  });
});

describe('TenderHack real API UI', () => {
  beforeEach(() => localStorage.clear());

  it('does not clear user input after a 429 rejection and labels the real mode', async () => {
    const sendMessage = vi.fn(async (_input: ChatInput): Promise<AcceptedRequest> => { throw new ApiError(429, { error: { code: 'QUEUE_FULL', message: 'Очередь заполнена', retryable: true, trace_id: 'trace', current_case_version: null } }); });
    const transport: TenderHackTransport = {
      mode: 'real',
      createSession: async () => ({ session_id: 'session', created_at: 'now', expires_at: 'later' }),
      sendMessage,
      getRequest: async () => { throw new Error('not called'); },
      getCase: async () => { throw new Error('not called'); },
      getSource: async () => { throw new Error('not called'); },
      saveFeedback: async () => { throw new Error('not called'); },
      createHandoff: async () => { throw new Error('not called'); },
    };
    render(<App mode="real" transport={transport} />);
    await screen.findByText('API подключён');
    const input = screen.getByLabelText('Сообщение') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Сохраните этот ввод' } });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить' }));
    await screen.findByText('Очередь заполнена');
    expect(input.value).toBe('Сохраните этот ввод');
    expect(screen.getByText('Реальный API')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Отправить' }));
    await vi.waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2));
    expect(sendMessage.mock.calls[1][0].request_key).toBe(sendMessage.mock.calls[0][0].request_key);
  });

  it('requires explicit confirmation and creates one fixture Ticket with current case_version', async () => {
    render(<App />);
    select('Handoff offered');
    const before = mockTransport.actions.length;
    fireEvent.click(screen.getByRole('button', { name: 'Передать специалисту нашего сервиса' }));
    expect(screen.getByRole('dialog', { name: 'Подтверждение передачи' })).toBeTruthy();
    expect(mockTransport.actions).toHaveLength(before);
    fireEvent.click(screen.getByRole('button', { name: 'Да, передать' }));
    expect(await screen.findByText('Ожидаем ответа специалиста нашего сервиса')).toBeTruthy();
    expect(mockTransport.actions.at(-1)).toMatchObject({
      operation: 'POST /api/v1/cases/{case_id}/handoff',
      caseId: '22222222-2222-4222-8222-222222222222',
      body: { expected_case_version: 2 },
    });
  });

  it('uses current version for clarification, retry_of, and a user reply after operator answer', async () => {
    render(<App />);
    select('Clarification');
    fireEvent.change(screen.getByLabelText('Сообщение'), { target: { value: 'Я поставщик' } });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить' }));
    expect(mockTransport.actions.at(-1)).toMatchObject({ operation: 'POST /api/v1/chat', body: { expected_case_version: 2, text: 'Я поставщик', retry_of: null } });

    select('Retry request');
    fireEvent.click(screen.getByRole('button', { name: 'Повторить этот запрос' }));
    expect(mockTransport.actions.at(-1)).toMatchObject({ operation: 'POST /api/v1/chat', body: { text: null, retry_of: '33333333-3333-4333-8333-333333333333' } });

    select('Operator reply');
    const operator = screen.getByText('Ответ специалиста в тестовом сценарии.').closest('article');
    expect(operator?.classList.contains('operator')).toBe(true);
    fireEvent.change(screen.getByLabelText('Сообщение'), { target: { value: 'Спасибо, ещё вопрос' } });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить' }));
    expect(await screen.findByText('Ожидаем ответа специалиста нашего сервиса')).toBeTruthy();
    expect(screen.getAllByText('Спасибо, ещё вопрос')).toHaveLength(1);
    expect(mockTransport.actions.at(-1)).toMatchObject({ operation: 'POST /api/v1/chat', body: { expected_case_version: 4, retry_of: null } });
  });

  it('restores a saved Case and renders duplicate operator message ids only once', async () => {
    localStorage.setItem('tenderhack.current-case-id', 'case');
    const restoredMessage = {
      message_id: 'message', case_id: 'case', seq: 1, role: 'assistant' as const,
      kind: 'answer' as const, responder_type: 'operator' as const, answer_origin: 'operator' as const,
      content: 'Восстановленный ответ специалиста', created_at: 'now',
    };
    const getCase = vi.fn(async () => ({
      case: { case_id: 'case', session_id: 'session', status: 'open' as const, case_version: 1, clarification_count: 0, created_at: 'now', updated_at: 'now' },
      messages: [restoredMessage, restoredMessage],
    }));
    const transport: TenderHackTransport = {
      mode: 'real',
      createSession: async () => ({ session_id: 'session', created_at: 'now', expires_at: 'later' }),
      sendMessage: async () => { throw new Error('not called'); },
      getRequest: async () => { throw new Error('not called'); },
      getCase,
      getSource: async () => { throw new Error('not called'); },
      saveFeedback: async () => { throw new Error('not called'); },
      createHandoff: async () => { throw new Error('not called'); },
    };
    render(<App mode="real" transport={transport} />);
    expect(await screen.findAllByText('Восстановленный ответ специалиста')).toHaveLength(1);
    expect(getCase).toHaveBeenCalledWith('case');
  });

  it('sends explicit handoff to the real transport with the freshly loaded case_version', async () => {
    localStorage.setItem('tenderhack.current-case-id', 'case');
    let handedOff = false;
    const getCase = vi.fn(async () => handedOff
      ? { case: { case_id: 'case', session_id: 'session', status: 'handed_off' as const, case_version: 12, clarification_count: 0, created_at: 'now', updated_at: 'later' }, ticket: { ticket_id: 'ticket', case_id: 'case', status: 'new' as const, created_at: 'now', updated_at: 'now' }, messages: [] }
      : { case: { case_id: 'case', session_id: 'session', status: 'handoff_offered' as const, case_version: 11, clarification_count: 0, created_at: 'now', updated_at: 'now' }, ticket: null, messages: [] });
    const createHandoff = vi.fn(async (_caseId: string, _input: HandoffInput) => {
      handedOff = true;
      return { ticket_id: 'ticket', case_id: 'case', status: 'new' as const, created_at: 'now', updated_at: 'now' };
    });
    const transport: TenderHackTransport = {
      mode: 'real', createSession: async () => ({ session_id: 'session', created_at: 'now', expires_at: 'later' }),
      sendMessage: async () => { throw new Error('not called'); }, getRequest: async () => { throw new Error('not called'); }, getCase,
      getSource: async () => { throw new Error('not called'); }, saveFeedback: async () => { throw new Error('not called'); }, createHandoff,
    };
    render(<App mode="real" transport={transport} />);
    await screen.findByRole('button', { name: 'Передать специалисту нашего сервиса' });
    fireEvent.click(screen.getByRole('button', { name: 'Передать специалисту нашего сервиса' }));
    fireEvent.click(screen.getByRole('button', { name: 'Да, передать' }));
    await vi.waitFor(() => expect(createHandoff).toHaveBeenCalledTimes(1));
    expect(createHandoff.mock.calls[0][0]).toBe('case');
    expect(createHandoff.mock.calls[0][1]).toMatchObject({ expected_case_version: 11 });
    expect(await screen.findByText('Ожидаем ответа специалиста нашего сервиса')).toBeTruthy();
  });

  it('shows outcome_applied=false as saved feedback without claiming Case closure', async () => {
    localStorage.setItem('tenderhack.current-case-id', 'case');
    const answer = { message_id: 'answer', case_id: 'case', seq: 1, role: 'assistant' as const, kind: 'answer' as const, responder_type: 'ai' as const, answer_origin: 'rag' as const, content: 'Актуальный AI ответ', created_at: 'now' };
    const getCase = vi.fn(async () => ({ case: { case_id: 'case', session_id: 'session', status: 'awaiting_feedback' as const, case_version: 5, clarification_count: 0, created_at: 'now', updated_at: 'now' }, messages: [answer] }));
    const transport: TenderHackTransport = {
      mode: 'real', createSession: async () => ({ session_id: 'session', created_at: 'now', expires_at: 'later' }),
      sendMessage: async () => { throw new Error('not called'); }, getRequest: async () => { throw new Error('not called'); }, getCase,
      getSource: async () => { throw new Error('not called'); },
      saveFeedback: async (input) => ({ feedback_id: 'feedback', message_id: input.message_id, case_version: 5, case_status: 'awaiting_feedback', outcome_applied: false, outcome_reason: 'STALE_MESSAGE' }),
      createHandoff: async () => { throw new Error('not called'); },
    };
    render(<App mode="real" transport={transport} />);
    expect(await screen.findAllByText('Актуальный AI ответ')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Решён' }));
    expect((await screen.findByRole('status')).textContent).toContain('Оценка сохранена, но статус текущего обращения не изменился');
    expect(screen.queryByText('Обращение завершено. Начните новую тему.')).toBeNull();
  });
});
