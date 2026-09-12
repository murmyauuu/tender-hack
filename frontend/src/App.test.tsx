import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import { ApiError, type TenderHackTransport } from './apiTransport';
import type { AcceptedRequest, ChatInput } from './generated';
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
    select('Ticket'); expect(screen.getByText('В очереди специалиста нашего сервиса')).toBeTruthy();
    select('Operator reply'); expect(screen.getByText('Ответ специалиста в тестовом сценарии.')).toBeTruthy();
    select('Policy closure'); expect(screen.getByText(/обнаружена нецензурная лексика/)).toBeTruthy();
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
    select('Operator reply');
    expect(screen.getByText('Оценка специалиста')).toBeTruthy();
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

  it('restores a saved Case and renders duplicate message ids only once', async () => {
    localStorage.setItem('tenderhack.current-case-id', 'case');
    const restoredMessage = {
      message_id: 'message', case_id: 'case', seq: 1, role: 'user' as const,
      kind: 'question' as const, content: 'Восстановленный вопрос', created_at: 'now',
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
    };
    render(<App mode="real" transport={transport} />);
    expect(await screen.findAllByText('Восстановленный вопрос')).toHaveLength(1);
    expect(getCase).toHaveBeenCalledWith('case');
  });
});
