import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from './App';
import { mockTransport } from './mockTransport';

const select = (name: string) => fireEvent.click(screen.getByRole('button', { name }));

describe('TenderHack fixture UI', () => {
  it('renders all frozen fixture scenarios and transitional states', () => {
    render(<App />);
    expect(screen.getAllByText('Тестовый ответ по инструкции.')).toHaveLength(2);
    select('Queued'); expect(screen.getByText('Запрос в очереди')).toBeTruthy();
    select('Retrieval'); expect(screen.getByText('Ищу подходящую инструкцию')).toBeTruthy();
    select('Candidate source'); expect(screen.getByTestId('candidate').textContent).toContain('ещё не ответ');
    select('Clarification'); expect(screen.getByText('Уточните, вы поставщик или заказчик?')).toBeTruthy();
    select('Handoff offered'); expect(screen.getByText('Передать специалисту нашего сервиса')).toBeTruthy();
    select('Ticket'); expect(screen.getByText('В очереди специалиста нашего сервиса')).toBeTruthy();
    select('Operator reply'); expect(screen.getByText('Ответ специалиста в тестовом сценарии.')).toBeTruthy();
    select('Policy closure'); expect(screen.getByText(/обнаружена нецензурная лексика/)).toBeTruthy();
    select('Generic error'); expect(screen.getByText('Хранилище временно недоступно')).toBeTruthy();
    select('Stale/version'); expect(screen.getByText('Состояние обращения изменилось')).toBeTruthy();
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
