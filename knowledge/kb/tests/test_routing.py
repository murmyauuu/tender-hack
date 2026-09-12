"""C04: маршрутизация (topic/subtopic/line/recipient) и расширение OOS.

Юнит-тесты на синтетических `EvidenceItem`/тексте запроса проверяют
`knowledge/kb/routing.py` детерминированно и не зависят от конкретного
состояния реального снимка. Интеграционные тесты внизу гоняют `retrieve()`
целиком на реальном снимке C02/C03, как и `test_retrieval_pipeline.py`.
"""

from __future__ import annotations

import asyncio

from tenderhack_contracts.models import EvidenceItem, GateDecision, QueryContext

from knowledge.kb.retrieval import decide_gate, run_pipeline
from knowledge.kb.routing import (
    build_routing_result,
    decide_support_line,
    detect_defect_signals,
    extract_recipient,
    match_topic,
)
from knowledge.kb.store import SqliteKnowledgeStore


def _evidence(**overrides) -> EvidenceItem:
    base = dict(
        evidence_id="ev:test:0",
        source_id="portal:1:1",
        original_ids=["orig1"],
        parent_id="portal:1",
        source_type="portal_kb",
        title="Заголовок",
        version=None,
        source_date=None,
        section_path=None,
        page_from=None,
        page_to=None,
        text="Текст ответа.",
        conditions=[],
        audience_raw=None,
        applicable_roles=[],
        role_verified=False,
        content_status="complete",
        eligibility_reason=None,
        retrieval_method="fts",
        score=1.0,
    )
    base.update(overrides)
    return EvidenceItem(**base)


# ------------------------------------------------------------------ match_topic


def test_match_topic_exact_full_keyword_containment():
    """Совпадение — по нормализованным СТЕМАМ (та же русская нормализация,
    что и C02/C03 FTS, `knowledge/kb/normalize.py`), не по словоформе.
    Стеммер здесь простой (Snowball-подобный, без словаря) и не всегда
    сводит вербальные и отглагольные формы к одному стему при исторических
    чередованиях согласных (восстановить/восстановление,
    расторгнуть/расторжение) — это ограничение C02-нормализатора, не этого
    модуля; поэтому тест использует отглагольную форму, совпадающую с
    формой в taxonomy, как и реальные вопросы часто её используют."""
    m = match_topic("Требуется восстановление доступа к личному кабинету")
    assert m.subtopic_id == "ST04"
    assert m.topic_id == "TH1"
    assert m.subtopic == "Восстановление доступа"
    assert not m.is_ambiguous


def test_match_topic_no_overlap_returns_null_not_guessed():
    m = match_topic("Расскажи анекдот про кота")
    assert m.topic_id is None
    assert m.subtopic_id is None
    assert not m.is_ambiguous


def test_match_topic_empty_query_returns_null():
    m = match_topic("")
    assert m.topic_id is None


def test_match_topic_distinctive_code_fallback_finds_rdik_subtopic():
    """«РДИК_0009» не содержит остальных слов описательной подтемы
    («Формирование УПД (вопросы по ошибкам РДИК)») — резервное правило по
    уникальному коду обязано сработать (см. C03-handoff §2.4 про РДИК)."""
    m = match_topic("Сработал интеграционный контроль РДИК_0009. Что делать?")
    assert m.subtopic_id == "ST75"
    assert m.topic_id == "TH8"
    assert not m.is_ambiguous


def test_match_topic_generic_common_word_is_not_a_distinctive_fallback():
    """Регрессия найденной и исправленной во время разработки проблемы:
    «поставщик» единственный раз встречается в тексте одной конкретной
    подтемы («Снятие блокировки с поставщика»), но это обычное частотное
    слово предметной области — оно НЕ должно ложно маршрутизировать любой
    supplier-вопрос в эту подтему. Резерв допускает только
    аббревиатуры/коды (is_abbreviation_or_code), не обычные существительные."""
    m = match_topic("Как поставщику зарегистрироваться на Портале?")
    assert m.subtopic_id != "ST19", "generic word 'поставщик' must not act as a distinctive keyword"


def test_match_topic_consultation_ambiguous_across_five_themes():
    """«Консультация» — буквально одна и та же подтема в 5 разных темах
    (C00_input_audit §6.2). Совпадение возможно, но обязано быть отмечено
    как ambiguous, а не тихо выбирать одну тему наугад."""
    m = match_topic("Нужна консультация")
    assert m.subtopic == "Консультация"
    assert m.is_ambiguous


def test_match_topic_second_pass_basis_source_ids_from_evidence():
    evidence = [
        _evidence(
            evidence_id="ev:1", source_id="portal:559773:1",
            title="Что делать, если срок блокировки истек",
            text="Срок блокировки истек, обратитесь в службу контроля качества.",
        ),
        _evidence(evidence_id="ev:2", source_id="portal:other:1", title="Не по теме", text="Другой текст."),
    ]
    m = match_topic("Срок блокировки истек, кабинет всё ещё заблокирован", evidence=evidence)
    assert m.subtopic_id == "ST86"
    assert m.basis_source_ids == ["portal:559773:1"]


# -------------------------------------------------------------- defect signals


def test_bare_ne_rabotaet_alone_is_not_a_defect_signal():
    """Требование задания буквально: одна фраза «не работает» сама по себе
    НЕ достаточна для L3."""
    s = detect_defect_signals("Личный кабинет не работает.")
    assert s.has_malfunction_phrase
    assert not s.is_probable_defect


def test_missing_attachment_alone_is_not_a_defect_signal():
    s = detect_defect_signals("Забыл прикрепить скриншот ошибки, что делать?")
    assert s.has_missing_attachment_mention
    assert not s.is_probable_defect


def test_quoted_error_plus_recurrence_is_a_defect_signal():
    s = detect_defect_signals(
        "При отправке УПД появляется ошибка «Внутренняя ошибка сервера 500», "
        "и так происходит постоянно, независимо от браузера."
    )
    assert s.has_error_quote
    assert s.has_recurrence_language
    assert s.is_probable_defect


def test_malfunction_plus_recurrence_is_a_defect_signal():
    s = detect_defect_signals("Кабинет не работает каждый раз при входе третий день подряд.")
    assert s.has_malfunction_phrase
    assert s.has_recurrence_language
    assert s.is_probable_defect


def test_known_validation_code_alone_is_not_a_defect_signal():
    """РДИК-коды — документированные контроли, не дефект по умолчанию
    (C03-handoff §2.4/§8)."""
    s = detect_defect_signals("Сработал интеграционный контроль РДИК_0474 при отправке УПД.")
    assert s.has_known_validation_code
    assert not s.is_probable_defect


def test_quoted_error_alone_without_recurrence_is_not_a_defect_signal():
    """DEV-004-подобный случай: конкретная цитируемая ошибка при входе, но
    без признаков воспроизводимости — не L3 (остаётся L1/L2 triage)."""
    s = detect_defect_signals(
        'При авторизации по электронной подписи появляется ошибка «Сертификат не зарегистрирован».'
    )
    assert s.has_error_quote
    assert not s.has_recurrence_language
    assert not s.is_probable_defect


# ------------------------------------------------------------------ recipient


def test_extract_recipient_from_referral_phrase_in_evidence_text():
    evidence = [
        _evidence(
            evidence_id="ev:sel", source_id="portal:559773:1",
            text="По вопросам блокировки необходимо обратиться в службу контроля "
                 "качества Портала поставщиков по форме обратной связи.",
        )
    ]
    recipient, basis, rule_id = extract_recipient(evidence, selected_ids=["ev:sel"])
    assert recipient == "службу контроля качества Портала поставщиков по форме обратной связи"
    assert basis == ["portal:559773:1"]
    assert rule_id == "ROUTE.RECIPIENT.REFERRAL_PHRASE"


def test_extract_recipient_none_when_no_referral_phrase_present():
    evidence = [_evidence(text="Просто описание процесса без указания адресата.")]
    recipient, basis, rule_id = extract_recipient(evidence, selected_ids=[])
    assert recipient is None
    assert basis == []
    assert rule_id is None


def test_extract_recipient_ignores_non_selected_candidates_entirely():
    """Не-selected candidate с фразой-рефералом не должен становиться
    источником recommended_recipient — иначе адресат перестаёт быть
    привязан к реально показанному пользователю основанию ответа."""
    evidence = [
        _evidence(evidence_id="ev:other", source_id="s-other",
                  text="Обратитесь в отдел А по общим вопросам."),
        _evidence(evidence_id="ev:sel", source_id="s-selected",
                  text="Просто текст без указания адресата.", score=0.5),
    ]
    recipient, basis, _ = extract_recipient(evidence, selected_ids=["ev:sel"])
    assert recipient is None
    assert basis == []


def test_extract_recipient_only_considers_top_scored_selected_evidence():
    """Регрессия найденной и исправленной во время разработки проблемы:
    при FTS-fallback (нет dense-индекса, см. C03-handoff §6) в selected
    попадает не только topически точный источник, но и сопутствующий с
    более низким score, который случайно тоже содержит фразу-реферал не по
    теме вопроса (реальный кейс: вопрос про код РДИК_0009 vs посторонняя
    selected-статья про истёкший срок блокировки ЛК). Признак адресата
    берётся ТОЛЬКО из наивысшего по score selected evidence, а не из всего
    selected-набора."""
    evidence = [
        _evidence(evidence_id="ev:top", source_id="s-top", score=10.0,
                  text="Инструкция по устранению ошибки: выполните шаги 1-2-3."),
        _evidence(evidence_id="ev:secondary", source_id="s-secondary", score=1.0,
                  text="Несвязанная статья: обратитесь в службу контроля качества."),
    ]
    recipient, basis, rule_id = extract_recipient(
        evidence, selected_ids=["ev:top", "ev:secondary"]
    )
    assert recipient is None
    assert basis == []
    assert rule_id is None


# ------------------------------------------------------------- support line


def test_decide_support_line_defect_signal_forces_l3_regardless_of_topic():
    topic = match_topic("Как изменить наименование организации на Портале?")  # любой/нет topic
    s = detect_defect_signals(
        "Кабинет не работает каждый раз при входе, ошибка «Timeout 504» повторяется постоянно."
    )
    line = decide_support_line(topic, s)
    assert line.support_line == "L3"
    assert not line.is_ambiguous


def test_decide_support_line_no_topic_basis_is_null_not_l2():
    topic = match_topic("Расскажи анекдот про кота")
    s = detect_defect_signals("Расскажи анекдот про кота")
    line = decide_support_line(topic, s)
    assert line.support_line is None
    assert not line.is_ambiguous


def test_decide_support_line_l1_theme_with_error_quote_triages_to_l2():
    topic = match_topic("Требуется восстановление доступа к личному кабинету")
    assert topic.topic_id == "TH1"
    s = detect_defect_signals(
        'При восстановлении доступа к личному кабинету появляется ошибка «Сертификат не найден».'
    )
    line = decide_support_line(topic, s)
    assert line.support_line == "L2"
    assert not line.is_ambiguous  # L1/L2 triage сам по себе не помечается ambiguous


def test_decide_support_line_l2_theme_plain_how_to_stays_l2_not_ambiguous():
    topic = match_topic("Как выполнить расторжение контракта?")
    assert topic.topic_id == "TH4"
    s = detect_defect_signals("Как выполнить расторжение контракта?")
    line = decide_support_line(topic, s)
    assert line.support_line == "L2"
    assert not line.is_ambiguous


def test_decide_support_line_l2_theme_with_error_but_no_recurrence_is_ambiguous():
    topic = match_topic("Как выполнить расторжение контракта?")
    s = detect_defect_signals('При расторжении контракта появляется ошибка «Документ не найден».')
    line = decide_support_line(topic, s)
    assert line.support_line == "L2"
    assert line.is_ambiguous


def test_decide_support_line_ambiguous_topic_forces_l2_triage():
    topic = match_topic("Нужна консультация")
    assert topic.is_ambiguous
    s = detect_defect_signals("Нужна консультация")
    line = decide_support_line(topic, s)
    assert line.support_line == "L2"
    assert line.is_ambiguous


# --------------------------------------------------------- build_routing_result


def test_build_routing_result_fills_all_fields_without_changing_contract_shape():
    evidence = [
        _evidence(
            evidence_id="ev:1", source_id="portal:559773:1",
            title="Что делать, если срок блокировки истек",
            text="Обратитесь в службу контроля качества Портала поставщиков.",
        )
    ]
    route = build_routing_result(
        "Срок блокировки истек, а личный кабинет все ещё заблокирован.", evidence, ["ev:1"]
    )
    assert route.topic_id == "TH9"
    assert route.subtopic_id == "ST86"
    assert route.support_line == "L1"
    assert route.recommended_recipient == "службу контроля качества Портала поставщиков"
    assert route.basis_source_ids == ["portal:559773:1"]
    assert route.rule_id is not None
    assert route.is_probable_defect is False


def test_build_routing_result_on_out_of_scope_text_leaves_everything_null():
    route = build_routing_result("Расскажи анекдот про кота", [], [])
    assert route.topic_id is None
    assert route.subtopic_id is None
    assert route.support_line is None
    assert route.recommended_recipient is None
    assert route.basis_source_ids == []
    assert route.is_probable_defect is False
    assert route.is_ambiguous is False


# --------------------------------------------------------------- integration


def _query(text: str, *, confirmed_facts=None, clarification_count: int = 0) -> QueryContext:
    return QueryContext(
        text=text,
        confirmed_facts=confirmed_facts or {},
        recent_user_messages=[],
        clarification_count=clarification_count,
        trace_id="test-trace-routing",
    )


def test_integration_route_populated_on_real_kb_answer_allowed(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query(
                    "Срок блокировки истек, а личный кабинет все ещё заблокирован. Что делать?",
                    confirmed_facts={"role": "supplier"},
                )
            )
        )
        assert result.decision == GateDecision.ANSWER_ALLOWED
        assert result.route.subtopic_id == "ST86"
        assert result.route.support_line == "L1"
        assert result.route.recommended_recipient is not None
    finally:
        store.close()


def test_integration_role_clarify_still_works_route_is_still_present(snapshot_dir):
    """C03's role-clarification не должна быть сломана добавлением routing:
    RoutingResult всегда присутствует (контракт не Optional), даже когда
    gate ещё ждёт уточнение роли."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(_query("Нужна ли МЧД индивидуальному предпринимателю для подписания документов?"))
        )
        assert result.decision == GateDecision.CLARIFY
        assert result.route is not None
    finally:
        store.close()


def test_integration_missing_attachment_never_forces_l3_on_real_kb(snapshot_dir):
    """DEV-015-подобный случай на реальном снимке: gold source incomplete
    (ссылка на отсутствующий рисунок) не должен создавать необоснованный L3
    (missing attachment сам по себе не признак L3, §10)."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(
                _query(
                    "Как вернуть УПД в статус «Черновик» при электронном актировании через ЕИС?",
                    confirmed_facts={"role": "supplier"},
                )
            )
        )
        assert result.route.support_line != "L3"
        assert result.route.is_probable_defect is False
    finally:
        store.close()


def test_integration_bare_ne_rabotaet_on_real_kb_never_yields_l3(snapshot_dir):
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(
            store.retrieve(_query("Личный кабинет не работает.", confirmed_facts={"role": "supplier"}))
        )
        assert result.route.support_line != "L3"
        assert result.route.is_probable_defect is False
    finally:
        store.close()


def test_integration_out_of_scope_extended_for_genuinely_unrelated_query(snapshot_dir):
    """Расширение C04 узкого OOS-сигнала C03: содержательные токены есть, но
    ни FTS/exact/dense, ни taxonomy не находят вообще ничего общего с
    запросом — честный OUT_OF_SCOPE, а не ESCALATE/NO_EVIDENCE."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(store.retrieve(_query("Расскажи анекдот про программиста и кота")))
        assert result.decision == GateDecision.OUT_OF_SCOPE
    finally:
        store.close()


def test_integration_greeting_out_of_scope_regression_not_broken(snapshot_dir):
    """Узкий сигнал C03 (пустой/приветственный запрос) не должен быть
    сломан расширением C04."""
    store = SqliteKnowledgeStore(snapshot_dir)
    try:
        result = asyncio.run(store.retrieve(_query("Привет!")))
        assert result.decision == GateDecision.OUT_OF_SCOPE
    finally:
        store.close()


def test_decide_gate_out_of_scope_extension_requires_both_no_hits_and_no_topic(snapshot_dir):
    """`has_any_dense_or_exact_hit=True` не должно давать OUT_OF_SCOPE даже
    если groups пуст по другой причине — расширение срабатывает только
    когда буквально ничего не найдено нигде."""
    import sqlite3

    from tenderhack_contracts.models import GateDecision as _GD

    db = f"{snapshot_dir}/knowledge.sqlite"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        outcome = decide_gate(
            "Совершенно случайный текст без содержательного совпадения",
            groups=[],
            role_blocked_needs_role=False,
            role_blocked_mismatch=False,
            unknown_identifiers=[],
            clarification_count=0,
            has_any_dense_or_exact_hit=True,
            conn=conn,
        )
        assert outcome.decision != _GD.OUT_OF_SCOPE
    finally:
        conn.close()
