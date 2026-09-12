import { FormEvent, useMemo, useState } from 'react';
import type { FeedbackInput, Message, RequestView } from './generated';
import { fixtureNames, mockTransport, type ScenarioName } from './mockTransport';
import './styles.css';

const scenarios: Array<{ id: ScenarioName; label: string }> = [
  { id: 'queued', label: 'Queued' }, { id: 'retrieving', label: 'Retrieval' },
  { id: 'candidate', label: 'Candidate source' }, { id: 'answer', label: 'RAG answer' },
  { id: 'clarify', label: 'Clarification' }, { id: 'handoff_offered', label: 'Handoff offered' },
  { id: 'ticket', label: 'Ticket' }, { id: 'operator', label: 'Operator reply' },
  { id: 'policy', label: 'Policy closure' }, { id: 'error', label: 'Generic error' },
  { id: 'stale', label: 'Stale/version' },
];

const progressText: Record<NonNullable<RequestView['progress']>, string> = {
  queued: 'Запрос в очереди', retrieving: 'Ищу подходящую инструкцию',
  sources_found: 'Найден материал. Проверяю, подходит ли он к вашей ситуации',
  generating: 'Готовлю ответ по найденным материалам',
};

function RequestProgress({ request }: { request: RequestView }) {
  return <section className="progress" aria-live="polite"><span className="pulse" aria-hidden="true" /><div><strong>{request.progress ? progressText[request.progress] : 'Обрабатываю запрос'}</strong><small>Пожалуйста, не закрывайте страницу</small></div></section>;
}

function CandidateNotice({ request }: { request: RequestView }) {
  const candidates = request.candidate_sources ?? [];
  if (!candidates.length) return null;
  return <section className="candidate" data-testid="candidate"><span className="eyebrow">Возможный материал · ещё не ответ</span><strong>{candidates[0].title}</strong><p>Проверяем применимость к вашей ситуации. Этот материал пока не подтверждает решение.</p></section>;
}

type FeedbackStatus = Parameters<typeof mockTransport.saveFeedback>[2];

function Feedback({ message, operator, caseVersion, caseStatus }: { message: Message; operator: boolean; caseVersion: number; caseStatus: FeedbackStatus }) {
  const [saved, setSaved] = useState('');
  const [solved, setSolved] = useState<boolean | null>(null);
  const submit = async (body: FeedbackInput, label: string) => { await mockTransport.saveFeedback(body, caseVersion, caseStatus); setSaved(label); };
  return <div className="feedback" aria-label="Оценка ответа">
    <span>Ответ был полезен?</span><div className="feedback-row"><button onClick={() => submit({ message_id: message.message_id, useful: true, reason_codes: [] }, 'Полезность сохранена')}>Да</button><button onClick={() => submit({ message_id: message.message_id, useful: false, reason_codes: [] }, 'Полезность сохранена')}>Нет</button></div>
    <span>Вопрос решён?</span><div className="feedback-row">{[true, false].map((value) => <button className={solved === value ? 'selected' : ''} key={String(value)} onClick={() => { setSolved(value); void submit({ message_id: message.message_id, solved: value, reason_codes: [] }, 'Результат сохранён'); }}>{value ? 'Решён' : 'Ещё нет'}</button>)}</div>
    {operator && <div className="rating"><span>Оценка специалиста</span>{[1, 2, 3, 4, 5].map((rating) => <button key={rating} aria-label={`${rating} из 5`} onClick={() => void submit({ message_id: message.message_id, specialist_rating: rating, reason_codes: [] }, 'Оценка специалиста сохранена')}>{rating}</button>)}</div>}
    {saved && <small role="status">✓ {saved} в mock transport</small>}
  </div>;
}

function AnswerCard({ message, caseVersion, caseStatus, onSource }: { message: Message; caseVersion: number; caseStatus: FeedbackStatus; onSource: (id: string) => void }) {
  const operator = message.responder_type === 'operator' && message.answer_origin === 'operator';
  const sourceIds = message.source_ids ?? [];
  return <article className={`message assistant ${operator ? 'operator' : ''}`}><span className="eyebrow">{operator ? 'Ответ специалиста' : message.answer_origin === 'card' ? 'Проверенный сценарий' : 'Ответ по инструкции'}</span><p>{message.content}</p>{!operator && <>
    <section className="answer-section source-first"><h3>Источник</h3>{sourceIds.length ? sourceIds.map((id) => <button className="source-link" key={id} onClick={() => onSource(id)}>Открыть источник · {id}</button>) : <p className="muted">Источник не указан.</p>}</section>
    <section className="answer-section"><h3>Условия</h3><p className="muted">В frozen fixture C0 условия отдельно не переданы.</p></section>
    <section className="answer-section"><h3>Шаги</h3><ol><li>{message.content}</li></ol></section>
  </>}<Feedback message={message} operator={operator} caseVersion={caseVersion} caseStatus={caseStatus} /></article>;
}

function SourceDrawer({ sourceId, onClose }: { sourceId: string; onClose: () => void }) {
  const source = mockTransport.getSource(sourceId);
  return <aside className="drawer" role="dialog" aria-label="Источник"><button className="close" onClick={onClose}>Закрыть</button><span className="eyebrow">Источник</span><h2>{source?.title ?? sourceId}</h2>{source ? <p>{source.excerpt}</p> : <div className="empty-source"><strong>Карточка источника недоступна</strong><p>C0 не содержит frozen SourceRecord для этого идентификатора. URL, PDF, дату и версию не додумываем.</p></div>}</aside>;
}

export default function App() {
  const [scenario, setScenario] = useState<ScenarioName>('answer');
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [text, setText] = useState(''); const [sent, setSent] = useState('');
  const caseView = useMemo(() => mockTransport.getCase(scenario), [scenario]);
  const request = useMemo(() => mockTransport.getRequest(scenario), [scenario]);
  const error = useMemo(() => mockTransport.getError(scenario), [scenario]);
  const submit = (event: FormEvent) => { event.preventDefault(); if (!text.trim()) return; void mockTransport.sendMessage(text.trim()); setSent(text.trim()); setText(''); };
  const policyClosed = caseView?.case.status === 'closed_policy'; const resolved = caseView?.case.status === 'resolved';
  return <div className="app-shell"><header><a className="brand" href="#top"><span>Т</span><div>TenderHack<small>помощник поставщика</small></div></a><div className="mode"><i /> Демо на mock-данных</div></header><main id="top">
    <aside className="scenario-panel"><span className="eyebrow">Frozen fixtures C0</span><h1>Сценарии интерфейса</h1><p>Переключайте состояния без подключения к реальному API.</p><nav>{scenarios.map((item) => <button key={item.id} className={scenario === item.id ? 'active' : ''} onClick={() => { setScenario(item.id); setSourceId(null); }}>{item.label}</button>)}</nav><small>Fixtures: {fixtureNames.length}/8 подключены напрямую</small></aside>
    <section className="chat"><div className="chat-heading"><div><span className="eyebrow">Обращение</span><h2>Чем помочь по работе с закупками?</h2></div><button className="new-topic" onClick={() => { setSent(''); setText(''); }}>Новая тема</button></div><div className="messages">
      {(caseView?.messages ?? []).map((message) => message.kind === 'answer' ? <AnswerCard key={message.message_id} message={message} caseVersion={caseView!.case.case_version} caseStatus={caseView!.case.status} onSource={setSourceId} /> : <article key={message.message_id} className={`message ${message.role} ${message.kind}`}><span className="eyebrow">{message.role === 'user' ? 'Вы' : message.kind === 'clarification' ? 'Нужно уточнение' : policyClosed ? 'Правила общения' : 'Помощник'}</span><p>{message.content}</p></article>)}
      {sent && <article className="message user"><span className="eyebrow">Вы · mock</span><p>{sent}</p></article>}{request && <RequestProgress request={request} />}{request && <CandidateNotice request={request} />}
      {caseView?.case.status === 'handoff_offered' && <button className="handoff" onClick={() => void mockTransport.handoff(caseView.case.case_id)}>Передать специалисту нашего сервиса</button>}
      {caseView?.ticket && <section className="ticket"><span className="eyebrow">Обращение {caseView.ticket.ticket_id.slice(0, 8)}</span><h3>В очереди специалиста нашего сервиса</h3><p>Линия поддержки: {caseView.ticket.route?.support_line ?? caseView.case.route?.support_line ?? 'требует уточнения'}</p><p>Рекомендованный адресат: {caseView.ticket.route?.recommended_recipient ?? caseView.case.route?.recommended_recipient ?? 'Адресат требует уточнения'}</p></section>}
      {error && <section className={`error ${scenario === 'stale' ? 'stale' : ''}`} role="alert"><span className="eyebrow">{scenario === 'stale' ? 'Версия обращения изменилась' : 'Техническая ошибка'}</span><h3>{error.error.message}</h3><p>{scenario === 'stale' ? 'Обновите обращение перед повторным действием. Введённый текст сохранён.' : error.error.retryable ? 'Попробуйте повторить действие. Запрос не выдаётся за успешно обработанный.' : 'Повтор сейчас недоступен.'}</p>{error.error.retryable && <button>Повторить</button>}</section>}
    </div><form className="composer" onSubmit={submit}><label htmlFor="question">Сообщение</label><textarea id="question" value={text} onChange={(event) => setText(event.target.value)} placeholder={caseView?.ticket?.status === 'waiting_user' ? 'Ответить специалисту…' : 'Опишите вопрос…'} disabled={policyClosed || resolved} /><button type="submit" disabled={policyClosed || resolved || !text.trim()}>Отправить</button><small>{policyClosed ? 'Обращение закрыто по правилам общения.' : resolved ? 'Обращение завершено. Начните новую тему.' : caseView?.ticket?.status === 'waiting_user' ? 'Сообщение будет направлено специалисту.' : 'В демо сообщение остаётся только в mock transport.'}</small></form></section>
  </main>{sourceId && <SourceDrawer sourceId={sourceId} onClose={() => setSourceId(null)} />}</div>;
}
