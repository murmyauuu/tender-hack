import { FormEvent, useMemo, useState } from 'react';
import { resolveFrontendMode, type FrontendMode, type TenderHackTransport } from './apiTransport';
import type { ErrorDetail, FeedbackInput, Message, RequestView, SourceRecord } from './generated';
import { fixtureNames, mockTransport, type ScenarioName } from './mockTransport';
import { useRealChat } from './useRealChat';
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
  if (request.status !== 'queued' && request.status !== 'processing') return null;
  return <section className="progress" aria-live="polite"><span className="pulse" aria-hidden="true" /><div><strong>{request.progress ? progressText[request.progress] : 'Обрабатываю запрос'}</strong><small>Пожалуйста, не закрывайте страницу</small></div></section>;
}

function CandidateNotice({ request }: { request: RequestView }) {
  const candidates = request.candidate_sources ?? [];
  if (!candidates.length || request.status === 'final') return null;
  return <section className="candidate" data-testid="candidate"><span className="eyebrow">Возможный материал · ещё не ответ</span><strong>{candidates[0].title}</strong><p>Проверяем применимость к вашей ситуации. Этот материал пока не подтверждает решение.</p></section>;
}

function Feedback({ message, operator, mode, onSubmit }: { message: Message; operator: boolean; mode: FrontendMode; onSubmit: (input: FeedbackInput) => Promise<void> }) {
  const [saved, setSaved] = useState('');
  const [solved, setSolved] = useState<boolean | null>(null);
  const submit = async (body: FeedbackInput, label: string) => {
    setSaved('');
    try { await onSubmit(body); setSaved(label); } catch { setSaved('Не удалось сохранить оценку'); }
  };
  return <div className="feedback" aria-label="Оценка ответа">
    <span>Ответ был полезен?</span><div className="feedback-row"><button onClick={() => void submit({ message_id: message.message_id, useful: true, reason_codes: [] }, 'Полезность сохранена')}>Да</button><button onClick={() => void submit({ message_id: message.message_id, useful: false, reason_codes: [] }, 'Полезность сохранена')}>Нет</button></div>
    <span>Вопрос решён?</span><div className="feedback-row">{[true, false].map((value) => <button className={solved === value ? 'selected' : ''} key={String(value)} onClick={() => { setSolved(value); void submit({ message_id: message.message_id, solved: value, reason_codes: [] }, 'Результат сохранён'); }}>{value ? 'Решён' : 'Ещё нет'}</button>)}</div>
    {operator && <div className="rating"><span>Оценка специалиста</span>{[1, 2, 3, 4, 5].map((rating) => <button key={rating} aria-label={`${rating} из 5`} onClick={() => void submit({ message_id: message.message_id, specialist_rating: rating, reason_codes: [] }, 'Оценка специалиста сохранена')}>{rating}</button>)}</div>}
    {saved && <small role="status">{saved.startsWith('Не') ? '⚠' : '✓'} {saved}{mode === 'mock' ? ' в mock transport' : ''}</small>}
  </div>;
}

function AnswerCard({ message, mode, onSource, onFeedback }: { message: Message; mode: FrontendMode; onSource: (id: string) => void; onFeedback: (input: FeedbackInput) => Promise<void> }) {
  const operator = message.responder_type === 'operator' && message.answer_origin === 'operator';
  const sourceIds = message.source_ids ?? [];
  const structured = message.structured_content;
  return <article className={`message assistant ${operator ? 'operator' : ''}`}><span className="eyebrow">{operator ? 'Ответ специалиста' : message.answer_origin === 'card' ? 'Проверенный сценарий' : 'Ответ по инструкции'}</span><p>{structured?.summary ?? message.content}</p>{!operator && <>
    <section className="answer-section source-first"><h3>Источник</h3>{sourceIds.length ? sourceIds.map((id) => <button className="source-link" key={id} onClick={() => onSource(id)}>Открыть источник · {id}</button>) : <p className="muted">Источник не указан.</p>}</section>
    <section className="answer-section"><h3>Условия</h3>{structured?.conditions?.length ? <ul>{structured.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul> : <p className="muted">Отдельные условия не переданы.</p>}</section>
    <section className="answer-section"><h3>Шаги</h3>{structured?.steps?.length ? <ol>{structured.steps.map((step) => <li key={step}>{step}</li>)}</ol> : <ol><li>{message.content}</li></ol>}</section>
  </>}<Feedback message={message} operator={operator} mode={mode} onSubmit={onFeedback} /></article>;
}

function SourceDrawer({ source, sourceId, loading, onClose }: { source: SourceRecord | null; sourceId: string; loading: boolean; onClose: () => void }) {
  return <aside className="drawer" role="dialog" aria-label="Источник"><button className="close" onClick={onClose}>Закрыть</button><span className="eyebrow">Источник</span><h2>{source?.title ?? sourceId}</h2>{loading ? <p>Загружаю источник…</p> : source ? <><p>{source.excerpt}</p>{source.section_path && <p className="muted">Раздел: {source.section_path}</p>}{source.url && <a href={source.url} target="_blank" rel="noreferrer">Открыть оригинал</a>}</> : <div className="empty-source"><strong>Карточка источника недоступна</strong><p>URL, PDF, дату и версию не додумываем.</p></div>}</aside>;
}

function ErrorNotice({ error, preservedInput }: { error: ErrorDetail; preservedInput: boolean }) {
  const stale = error.code === 'STALE_CASE_VERSION' || error.code === 'CASE_BUSY' || error.code === 'CASE_CLOSED';
  return <section className={`error ${stale ? 'stale' : ''}`} role="alert"><span className="eyebrow">{stale ? 'Состояние обращения изменилось' : 'Техническая ошибка'}</span><h3>{error.message}</h3><p>{preservedInput ? 'Введённый текст сохранён. Проверьте обновлённое обращение и отправьте его повторно только вручную.' : error.retryable ? 'Можно повторить действие вручную. Запрос не выдаётся за успешно обработанный.' : 'Повтор сейчас недоступен.'}</p></section>;
}

function MessageHistory({ messages, mode, policyClosed, onSource, onFeedback }: { messages: Message[]; mode: FrontendMode; policyClosed: boolean; onSource: (id: string) => void; onFeedback: (input: FeedbackInput) => Promise<void> }) {
  return <>{messages.map((message) => message.kind === 'answer'
    ? <AnswerCard key={message.message_id} message={message} mode={mode} onSource={onSource} onFeedback={onFeedback} />
    : <article key={message.message_id} className={`message ${message.role} ${message.kind}`}><span className="eyebrow">{message.role === 'user' ? 'Вы' : message.kind === 'clarification' ? 'Нужно уточнение' : policyClosed ? 'Правила общения' : 'Помощник'}</span><p>{message.content}</p></article>)}</>;
}

function Header({ mode }: { mode: FrontendMode }) {
  return <header><a className="brand" href="#top"><span>Т</span><div>TenderHack<small>помощник поставщика</small></div></a><div className={`mode ${mode}`}><i /> {mode === 'real' ? 'Реальный API' : 'Демо на mock-данных'}</div></header>;
}

function MockApp() {
  const [scenario, setScenario] = useState<ScenarioName>('answer');
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [text, setText] = useState('');
  const [sent, setSent] = useState('');
  const caseView = useMemo(() => mockTransport.getCase(scenario), [scenario]);
  const request = useMemo(() => mockTransport.getRequest(scenario), [scenario]);
  const error = useMemo(() => mockTransport.getError(scenario), [scenario]);
  const submit = (event: FormEvent) => { event.preventDefault(); if (!text.trim()) return; void mockTransport.sendMessage(text.trim()); setSent(text.trim()); setText(''); };
  const policyClosed = caseView?.case.status === 'closed_policy';
  const resolved = caseView?.case.status === 'resolved';
  const saveFeedback = async (input: FeedbackInput) => { await mockTransport.saveFeedback(input, caseView?.case.case_version ?? 1, caseView?.case.status ?? 'open'); };
  return <><Header mode="mock" /><main id="top">
    <aside className="scenario-panel"><span className="eyebrow">Frozen fixtures C0</span><h1>Сценарии интерфейса</h1><p>Переключайте состояния без подключения к реальному API.</p><nav>{scenarios.map((item) => <button key={item.id} className={scenario === item.id ? 'active' : ''} onClick={() => { setScenario(item.id); setSourceId(null); }}>{item.label}</button>)}</nav><small>Fixtures: {fixtureNames.length}/8 подключены напрямую</small></aside>
    <section className="chat"><div className="chat-heading"><div><span className="eyebrow">Обращение</span><h2>Чем помочь по работе с закупками?</h2></div><button className="new-topic" onClick={() => { setSent(''); setText(''); }}>Новая тема</button></div><div className="messages">
      <MessageHistory messages={caseView?.messages ?? []} mode="mock" policyClosed={Boolean(policyClosed)} onSource={setSourceId} onFeedback={saveFeedback} />
      {sent && <article className="message user"><span className="eyebrow">Вы · mock</span><p>{sent}</p></article>}{request && <RequestProgress request={request} />}{request && <CandidateNotice request={request} />}
      {caseView?.case.status === 'handoff_offered' && <button className="handoff" onClick={() => void mockTransport.handoff(caseView.case.case_id)}>Передать специалисту нашего сервиса</button>}
      {caseView?.ticket && <section className="ticket"><span className="eyebrow">Обращение {caseView.ticket.ticket_id.slice(0, 8)}</span><h3>В очереди специалиста нашего сервиса</h3><p>Линия поддержки: {caseView.ticket.route?.support_line ?? caseView.case.route?.support_line ?? 'требует уточнения'}</p><p>Рекомендованный адресат: {caseView.ticket.route?.recommended_recipient ?? caseView.case.route?.recommended_recipient ?? 'Адресат требует уточнения'}</p></section>}
      {error && <ErrorNotice error={error.error} preservedInput={scenario === 'stale'} />}
    </div><form className="composer" onSubmit={submit}><label htmlFor="question">Сообщение</label><textarea id="question" value={text} onChange={(event) => setText(event.target.value)} placeholder="Опишите вопрос…" disabled={policyClosed || resolved} /><button type="submit" disabled={policyClosed || resolved || !text.trim()}>Отправить</button><small>{policyClosed ? 'Обращение закрыто по правилам общения.' : resolved ? 'Обращение завершено. Начните новую тему.' : 'В демо сообщение остаётся только в mock transport.'}</small></form></section>
  </main>{sourceId && <SourceDrawer source={null} sourceId={sourceId} loading={false} onClose={() => setSourceId(null)} />}</>;
}

function RealApp({ transport }: { transport?: TenderHackTransport }) {
  const model = useRealChat(transport);
  const [text, setText] = useState('');
  const [sourceId, setSourceId] = useState<string | null>(null);
  const submit = async (event: FormEvent) => { event.preventDefault(); if (await model.sendMessage(text)) setText(''); };
  const openSource = (id: string) => { setSourceId(id); void model.openSource(id); };
  const policyClosed = model.caseView?.case.status === 'closed_policy';
  const resolved = model.caseView?.case.status === 'resolved';
  const requestError = model.request?.status === 'error' ? model.request.error : null;
  return <><Header mode="real" /><main id="top">
    <aside className="scenario-panel real-status"><span className="eyebrow">A02 transport</span><h1>Реальный диалог</h1><p>Сессия, история и ответы загружаются с API. Cookie остаётся HttpOnly; localStorage хранит только идентификатор текущего обращения.</p><div className={`connection ${model.connection}`}>{model.connection === 'ready' ? 'API подключён' : model.connection === 'connecting' ? 'Подключение…' : 'API недоступен'}</div><small>Полный RAG E2E ожидает runtime A03 и реальный dense index.</small></aside>
    <section className="chat"><div className="chat-heading"><div><span className="eyebrow">Обращение</span><h2>Чем помочь по работе с закупками?</h2></div><button className="new-topic" onClick={() => { model.newTopic(); setText(''); setSourceId(null); }}>Новая тема</button></div><div className="messages">
      <MessageHistory messages={model.caseView?.messages ?? []} mode="real" policyClosed={Boolean(policyClosed)} onSource={openSource} onFeedback={model.saveFeedback} />
      {model.request && <RequestProgress request={model.request} />}{model.request && <CandidateNotice request={model.request} />}
      {requestError && <ErrorNotice error={{ ...requestError, trace_id: 'request-stored', current_case_version: null }} preservedInput={false} />}
      {model.error && <ErrorNotice error={model.error} preservedInput={['STALE_CASE_VERSION', 'CASE_BUSY', 'CASE_CLOSED', 'QUEUE_FULL', 'STORAGE_UNAVAILABLE', 'NETWORK_ERROR'].includes(model.error.code)} />}
      {!model.caseView && !model.request && model.connection === 'ready' && <section className="empty-chat"><strong>Начните новую тему</strong><p>После принятия запроса история будет сохранена сервером и восстановится после обновления страницы.</p></section>}
    </div><form className="composer" onSubmit={(event) => void submit(event)}><label htmlFor="question">Сообщение</label><textarea id="question" value={text} onChange={(event) => setText(event.target.value)} placeholder="Опишите вопрос…" disabled={model.connection !== 'ready' || policyClosed || resolved || model.sending} /><button type="submit" disabled={model.connection !== 'ready' || policyClosed || resolved || model.sending || !text.trim()}>{model.sending ? 'Отправляю…' : 'Отправить'}</button><small>{policyClosed ? 'Обращение закрыто по правилам общения.' : resolved ? 'Обращение завершено. Начните новую тему.' : 'При 409, 429, 503 и сетевой ошибке введённый текст останется в поле.'}</small></form></section>
  </main>{sourceId && <SourceDrawer source={model.source} sourceId={sourceId} loading={model.sourceLoading} onClose={() => { setSourceId(null); model.closeSource(); }} />}</>;
}

export default function App({ mode = resolveFrontendMode(), transport }: { mode?: FrontendMode; transport?: TenderHackTransport }) {
  return mode === 'real' ? <RealApp transport={transport} /> : <MockApp />;
}
