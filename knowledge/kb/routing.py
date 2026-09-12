"""Маршрутизация и уточнение knowledge-поведения (C04, §10 «Routing»).

Заполняет `RoutingResult` внутри `KnowledgeResult` (см. `knowledge/kb/retrieval.py`),
который до этой задачи оставался нейтральным (`RoutingResult()` от C03).
Только stdlib (`re`, `dataclasses`, `json`) — файл лежит в `knowledge/kb/` и
подпадает под сканирование `test_no_model_calls.py`. Никакой модели/LLM,
никакого обучаемого классификатора на 86 классов: topic/subtopic — точное
совпадение нормализованных ключевых слов реального справочника
(`config/knowledge/taxonomy.json`, сгенерирован `taxonomy_build.py` из
`НН 2026/Темы_подтемы_обращений.xlsx`, 9 тем / 86 строк / 82 уникальные
подтемы — ничего сверх этого не изобретается).

Два прохода (§10 «Routing»):

1. Первый — дешёвые детерминированные признаки самого текста запроса:
   совпадение с taxonomy (`match_topic`), признаки технического дефекта
   (`detect_defect_signals`), известные валидационные коды (РДИК),
   явное упоминание missing attachment (не считается признаком дефекта).
2. Второй — проверенная metadata уже найденных `KnowledgeResult.candidates`
   (заголовок/текст evidence, не второй embedding): подтверждает совпадение
   темы (`basis_source_ids`) и извлекает `recommended_recipient`, если сама
   статья явно называет адресата («обратитесь в …») — это не выдуманный
   справочник (которого нет, BL-C00-2), а буквальный текст источника.

L1/L2/L3 — разделены по §10:
  L1: навигация/вход/регистрация/простой how-to.
  L2: методология, договоры/УПД, сложное заполнение.
  L3: только сочетание признаков воспроизводимого технического дефекта.
Неопределённость L1/L2 → L2 triage. Неопределённость L2/L3 без технических
оснований → L2 triage + is_ambiguous=True. При отсутствии оснований вообще
— support_line=null (не автоматический L2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tenderhack_contracts.models import EvidenceItem, ReasonCode, RoutingResult

from knowledge.kb.lexical import is_abbreviation_or_code
from knowledge.kb.normalize import fts_normalize, fts_tokens
from knowledge.kb.taxonomy_build import TaxonomyRow, load_taxonomy

__all__ = [
    "TopicMatch",
    "DefectSignals",
    "match_topic",
    "detect_defect_signals",
    "extract_recipient",
    "decide_support_line",
    "build_routing_result",
]

# --------------------------------------------------------------- taxonomy match

try:
    _TAXONOMY_ROWS: list[TaxonomyRow] = load_taxonomy()
except FileNotFoundError:  # защитный fallback: config не собран в этом окружении
    _TAXONOMY_ROWS = []

_SUBTOPIC_KEYWORDS: dict[str, frozenset[str]] = {
    row.subtopic_id: frozenset(t for t in fts_normalize(row.subtopic).split() if t)
    for row in _TAXONOMY_ROWS
}

# Резервное правило (§10 «первый проход — дешёвые признаки»): некоторые
# taxonomy-подтемы сформулированы описательно («Формирование УПД (вопросы
# по ошибкам РДИК)»), а реальный вопрос называет только код/аббревиатуру
# («РДИК_0009») без остальных слов подтемы. Полное совпадение всех
# ключевых слов (основной путь ниже) тогда не сработает.
#
# Кандидаты на «уникальный признак» берутся ТОЛЬКО из токенов исходной
# подтемы, которые сами являются аббревиатурой/кодом (`is_abbreviation_or_code`
# из lexical.py — то же правило, что и для exact-ID в запросе, не второй
# способ разбора). Обычные русские существительные (даже редко
# встречающиеся в taxonomy, например «поставщик», «кабинет», «срок») в этот
# резерв НЕ попадают — иначе частое бытовое слово, которое просто
# статистически встретилось в тексте только одной подтемы, ложно
# «специализировало» бы её и подтягивало бы к ней совершенно не связанные
# реальные вопросы (проверено и отклонено во время разработки: «поставщик»
# как «уникальный» токен подтемы про закупки ловил вообще все supplier-
# вопросы). Абревиатура/код, встречающаяся ровно в одной подтеме всей
# taxonomy — это буквальный, единственный в taxonomy идентификатор понятия
# (РДИК, YML), не эвристика по смыслу.
_MIN_DISTINCTIVE_KEYWORD_LEN = 3
_COMPOUND_SPLIT_RE = re.compile(r"[_\-./]")


def _split_compound_tokens(tokens: frozenset[str]) -> frozenset[str]:
    """Дополнить набор токенов частями составных (`рдик_0009` -> `рдик`,
    `0009`) — только для taxonomy-matching в этом модуле, не меняет
    lexical.py/exact-ID разбор."""
    expanded = set(tokens)
    for tok in tokens:
        expanded.update(p for p in _COMPOUND_SPLIT_RE.split(tok) if p)
    return frozenset(expanded)


_ABBREVIATION_KEYWORD_DOC_FREQ: dict[str, int] = {}
_ABBREVIATION_KEYWORD_TO_SUBTOPICS: dict[str, set[str]] = {}
for _row in _TAXONOMY_ROWS:
    for _raw_tok in fts_tokens(_row.subtopic):
        if not is_abbreviation_or_code(_raw_tok):
            continue
        _norm = fts_normalize(_raw_tok)
        if not _norm:
            continue
        _ABBREVIATION_KEYWORD_DOC_FREQ[_norm] = _ABBREVIATION_KEYWORD_DOC_FREQ.get(_norm, 0) + 1
        _ABBREVIATION_KEYWORD_TO_SUBTOPICS.setdefault(_norm, set()).add(_row.subtopic_id)

_DISTINCTIVE_KEYWORD_TO_SUBTOPIC: dict[str, str] = {
    kw: next(iter(subtopic_ids))
    for kw, subtopic_ids in _ABBREVIATION_KEYWORD_TO_SUBTOPICS.items()
    if _ABBREVIATION_KEYWORD_DOC_FREQ.get(kw) == 1 and len(kw) >= _MIN_DISTINCTIVE_KEYWORD_LEN
}

try:
    import json as _json
    from pathlib import Path as _Path

    _ROUTING_LINES_PATH = (
        _Path(__file__).resolve().parents[2] / "config" / "knowledge" / "routing_lines.json"
    )
    _ROUTING_LINES = _json.loads(_ROUTING_LINES_PATH.read_text(encoding="utf-8"))
    _THEME_DEFAULT_LINE: dict[str, str] = _ROUTING_LINES["theme_default_line"]
    _SUBTOPIC_LINE_OVERRIDES: dict[str, str] = {
        sid: entry["line"] for sid, entry in _ROUTING_LINES["subtopic_overrides"].items()
    }
except FileNotFoundError:
    _THEME_DEFAULT_LINE = {}
    _SUBTOPIC_LINE_OVERRIDES = {}


@dataclass(frozen=True)
class TopicMatch:
    topic_id: str | None
    subtopic_id: str | None
    theme: str | None
    subtopic: str | None
    is_ambiguous: bool
    matched_keywords: list[str]
    basis_source_ids: list[str] = field(default_factory=list)


_EMPTY_TOPIC_MATCH = TopicMatch(
    topic_id=None, subtopic_id=None, theme=None, subtopic=None,
    is_ambiguous=False, matched_keywords=[], basis_source_ids=[],
)


def _finalize_topic_match(
    best: list[TaxonomyRow], matched_keywords_by_row: dict[str, frozenset[str]], evidence: list[EvidenceItem] | None
) -> TopicMatch:
    distinct_subtopic_texts = {r.subtopic for r in best}
    distinct_theme_ids = {r.theme_id for r in best}
    is_ambiguous = len(distinct_subtopic_texts) > 1 or len(distinct_theme_ids) > 1
    chosen = min(best, key=lambda r: r.row_no)
    keywords = sorted(matched_keywords_by_row[chosen.subtopic_id])

    basis_source_ids: list[str] = []
    if evidence:
        kw_set = _SUBTOPIC_KEYWORDS[chosen.subtopic_id]
        for ev in evidence:
            ev_tokens = frozenset(fts_normalize(f"{ev.title} {ev.text[:800]}").split())
            if kw_set <= ev_tokens:
                basis_source_ids.append(ev.source_id)

    return TopicMatch(
        topic_id=chosen.theme_id,
        subtopic_id=chosen.subtopic_id,
        theme=chosen.theme,
        subtopic=chosen.subtopic,
        is_ambiguous=is_ambiguous,
        matched_keywords=keywords,
        basis_source_ids=basis_source_ids,
    )


def match_topic(query_text: str, evidence: list[EvidenceItem] | None = None) -> TopicMatch:
    """Первый проход, основной путь: нормализованное точное совпадение ВСЕХ
    ключевых слов подтемы (короткие taxonomy-подтемы 1-3 слова, полное
    вхождение даёт высокую точность без обучения классификатора).

    Резервный путь (если основной не дал ни одного кандидата): уникальный
    для всей taxonomy ключевой признак (`_DISTINCTIVE_KEYWORD_TO_SUBTOPIC`,
    например «рдик») — покрывает случаи, когда вопрос называет только код,
    а не остальные слова описательной подтемы (см. комментарий выше).

    Второй проход: если совпадение найдено, проверяем title/text уже
    найденных `evidence` (переданных C03's `retrieve()`, без нового
    embedding) на то же ключевое множество — совпавшие evidence идут в
    `basis_source_ids`.
    """
    if not _TAXONOMY_ROWS:
        return _EMPTY_TOPIC_MATCH
    query_tokens = frozenset(fts_normalize(query_text).split())
    if not query_tokens:
        return _EMPTY_TOPIC_MATCH

    candidates: list[TaxonomyRow] = []
    for row in _TAXONOMY_ROWS:
        kw = _SUBTOPIC_KEYWORDS.get(row.subtopic_id)
        if not kw:
            continue
        if kw <= query_tokens:
            candidates.append(row)

    if candidates:
        max_len = max(len(_SUBTOPIC_KEYWORDS[r.subtopic_id]) for r in candidates)
        best = [r for r in candidates if len(_SUBTOPIC_KEYWORDS[r.subtopic_id]) == max_len]
        return _finalize_topic_match(best, _SUBTOPIC_KEYWORDS, evidence)

    expanded_tokens = _split_compound_tokens(query_tokens)
    hit_subtopic_ids = {
        _DISTINCTIVE_KEYWORD_TO_SUBTOPIC[t]
        for t in expanded_tokens
        if t in _DISTINCTIVE_KEYWORD_TO_SUBTOPIC
    }
    if not hit_subtopic_ids:
        return _EMPTY_TOPIC_MATCH
    rows_by_id = {r.subtopic_id: r for r in _TAXONOMY_ROWS}
    fallback_best = [rows_by_id[sid] for sid in hit_subtopic_ids]
    matched_subset = {
        sid: frozenset(_SUBTOPIC_KEYWORDS[sid] & expanded_tokens) for sid in hit_subtopic_ids
    }
    return _finalize_topic_match(fallback_best, matched_subset, evidence)


# ------------------------------------------------------------- defect signals

# Известные валидационные коды интеграционного контроля (документированы КБ,
# упоминание кода само по себе НЕ признак дефекта — это ожидаемая
# методология заполнения УПД, см. C03-handoff §2.4 и taxonomy ST-подтему
# «Формирование УПД (вопросы по ошибкам РДИК)»).
_KNOWN_VALIDATION_CODE_RE = re.compile(r"\bРДИК[_-]?\d+\b", re.IGNORECASE)

# Категория A: явно процитированное сообщение об ошибке рядом со словом
# «ошибка» (а не любые кавычки в тексте вообще).
_ERROR_QUOTE_RE = re.compile(
    r"ошибк[а-яё]*[^.!?«\"]{0,12}[«\"]([^»\"]{3,160})[»\"]", re.IGNORECASE
)

# Категория B: явная воспроизводимость/инцидент — многократность, не
# единичное упоминание слова «ошибка».
_RECURRENCE_RE = re.compile(
    r"\b(постоянно|каждый\s+раз|всегда|стабильно|систематически|регулярно|"
    r"повторно|снова\s+и\s+снова|уже\s+не\s+первый\s+раз)\b",
    re.IGNORECASE,
)
_INCIDENT_RE = re.compile(
    r"\b(завис(ает|ла|ло)|перестал[аи]?\s+работать|вылета(ет|ла)|"
    r"выдаёт\s+ошибку\s+сервера|500\s*(ошибка|error)?|сервис\s+недоступен|"
    r"сломал(ся|ась|ось))\b",
    re.IGNORECASE,
)

# Категория C: одна лишь общая формула «не работает» — по заданию НЕ
# достаточна сама по себе (используется только вместе с категорией B).
_MALFUNCTION_RE = re.compile(
    r"\bне\s+(работает|открывается|проходит|грузится|загружается|"
    r"сохраняется|подписывается|отправляется|формируется|запускается)\b",
    re.IGNORECASE,
)

# Missing attachment — по заданию явно НЕ признак L3, поэтому выделяется
# отдельно и никогда не участвует в is_probable_defect.
_MISSING_ATTACHMENT_RE = re.compile(
    r"(не\s+прилож[а-яё]*|нет\s+вложени[а-яё]*|отсутствует\s+(скриншот|файл|"
    r"вложени[а-яё]*|прикреплен[а-яё]*)|забыл[а]?\s+прикрепить)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DefectSignals:
    has_error_quote: bool
    has_recurrence_language: bool
    has_malfunction_phrase: bool
    has_missing_attachment_mention: bool
    has_known_validation_code: bool

    @property
    def is_probable_defect(self) -> bool:
        """L3 требует СОЧЕТАНИЯ признаков (§10): либо процитированная
        конкретная ошибка ВМЕСТЕ с языком воспроизводимости/инцидента,
        либо общая формула поломки ВМЕСТЕ с тем же языком воспроизводимости.
        Ни один признак сам по себе (в т.ч. голое «не работает» или
        известный валидационный код РДИК) L3 не даёт."""
        recurrence = self.has_recurrence_language
        return recurrence and (self.has_error_quote or self.has_malfunction_phrase)


def detect_defect_signals(query_text: str) -> DefectSignals:
    return DefectSignals(
        has_error_quote=bool(_ERROR_QUOTE_RE.search(query_text)),
        has_recurrence_language=bool(
            _RECURRENCE_RE.search(query_text) or _INCIDENT_RE.search(query_text)
        ),
        has_malfunction_phrase=bool(_MALFUNCTION_RE.search(query_text)),
        has_missing_attachment_mention=bool(_MISSING_ATTACHMENT_RE.search(query_text)),
        has_known_validation_code=bool(_KNOWN_VALIDATION_CODE_RE.search(query_text)),
    )


# ------------------------------------------------------------------ recipient

# «Обратитесь в …» / «обращение в …» — деterministic извлечение адресата,
# буквально из текста уже найденного evidence (не из выдуманного
# справочника, которого нет — BL-C00-2 подтверждён C00 и A00).
_RECIPIENT_REFERRAL_RE = re.compile(
    r"(?:обрат(?:иться|итесь)|направ(?:ить|ьте)\s+обращени[ея])\s+в\s+([^.,;:\n]{4,160})",
    re.IGNORECASE,
)


def extract_recipient(evidence: list[EvidenceItem], selected_ids: list[str]) -> tuple[str | None, list[str], str | None]:
    """Вернуть (recipient, basis_source_ids, rule_id). Ищет буквальную фразу
    «обратитесь в / направьте обращение в …» ТОЛЬКО в тексте
    наивысшего по score среди selected evidence (главного основания
    ответа) — не во всём selected-наборе и тем более не в остальных
    candidates.

    Причина узкого выбора (найдено и исправлено во время разработки):
    при FTS-fallback (нет реального dense-индекса, C03-handoff §6) в
    selected-набор попадает не только topически точная статья, но и
    сопутствующие с более низким score — например, для вопроса про код
    РДИК_0009 среди 5 selected оказалась статья про истёкший срок
    блокировки ЛК, которая, как оказалось, тоже содержит фразу
    «обратитесь в …», но совершенно не по теме вопроса. Если бы поиск шёл
    по всему selected-набору, такой посторонний referral обгонял бы честный
    null. Топ-1 (наиболее релевантный по score источник) — единственный
    достаточно надёжный кандидат для этого детерминированного правила."""
    selected_set = set(selected_ids)
    selected_evidence = [e for e in evidence if e.evidence_id in selected_set]
    if not selected_evidence:
        return None, [], None
    top = max(selected_evidence, key=lambda e: e.score)
    match = _RECIPIENT_REFERRAL_RE.search(top.text)
    if not match:
        return None, [], None
    recipient = match.group(1).strip().rstrip(".")
    return recipient, [top.source_id], "ROUTE.RECIPIENT.REFERRAL_PHRASE"


# --------------------------------------------------------------- support line


@dataclass(frozen=True)
class LineDecision:
    support_line: str | None
    is_ambiguous: bool
    rule_id: str | None


def decide_support_line(topic: TopicMatch, defect: DefectSignals) -> LineDecision:
    """§10: L3 только по сочетанию технических признаков — приоритетно
    относительно taxonomy-подсказки. Иначе используется theme/subtopic
    default с overrides (config/knowledge/routing_lines.json). При
    отсутствии topic-совпадения вообще — support_line=null, не
    автоматический L2 (по заданию)."""
    if defect.is_probable_defect:
        # Технический дефект перекрывает любую taxonomy-подсказку по линии,
        # но НЕ перекрывает topic/subtopic (тема вопроса не меняется).
        return LineDecision(support_line="L3", is_ambiguous=False, rule_id="ROUTE.LINE.L3_DEFECT_SIGNALS")

    if topic.subtopic_id is None:
        # Нет вообще никаких оснований для темы -> нет оснований для линии.
        return LineDecision(support_line=None, is_ambiguous=False, rule_id=None)

    baseline = _SUBTOPIC_LINE_OVERRIDES.get(topic.subtopic_id) or _THEME_DEFAULT_LINE.get(topic.topic_id)
    if baseline is None:
        return LineDecision(support_line=None, is_ambiguous=False, rule_id=None)

    if topic.is_ambiguous:
        # Неопределённость темы (напр. «Консультация» в 5 темах, или
        # taxonomy tie между двумя разными подтемами) -> L2 triage +
        # ambiguity, без выдумывания точной линии (§10).
        return LineDecision(support_line="L2", is_ambiguous=True, rule_id="ROUTE.LINE.AMBIGUOUS_TOPIC_L2_TRIAGE")

    if baseline == "L1" and (defect.has_malfunction_phrase or defect.has_error_quote):
        # Есть некоторый технический сигнал, но недостаточный для L3 (нет
        # recurrence/incident языка) -> неопределённость L1/L2 разрешается
        # в пользу L2 triage (§10: «Неопределённость L1/L2 → L2 triage»).
        return LineDecision(support_line="L2", is_ambiguous=False, rule_id="ROUTE.LINE.L1_L2_UNCERTAIN_TRIAGE")

    if baseline == "L2" and (defect.has_error_quote or defect.has_malfunction_phrase) and not defect.has_recurrence_language:
        # Технический сигнал есть, но не хватает признака воспроизводимости
        # для L3 -> L2 triage + ambiguity (§10: «L2/L3 без технических
        # оснований → L2 triage с ambiguity»). has_missing_attachment
        # сюда осознанно не входит: сам факт «нет вложения» не двигает
        # решение к L3/ambiguity (§10: «Missing attachment не означает L3»).
        return LineDecision(support_line="L2", is_ambiguous=True, rule_id="ROUTE.LINE.L2_L3_UNCERTAIN_AMBIGUOUS")

    rule_id = "ROUTE.LINE.SUBTOPIC_OVERRIDE" if topic.subtopic_id in _SUBTOPIC_LINE_OVERRIDES else "ROUTE.LINE.THEME_DEFAULT"
    return LineDecision(support_line=baseline, is_ambiguous=False, rule_id=rule_id)


# ------------------------------------------------------------------ orchestrator


def build_routing_result(
    query_text: str,
    evidence: list[EvidenceItem],
    selected_evidence_ids: list[str],
) -> RoutingResult:
    """Собрать реальный `RoutingResult` (вместо нейтрального от C03).

    Ничего не меняет в форме контракта — те же поля `RoutingResult`,
    заполненные по детерминированным правилам этого модуля."""
    topic = match_topic(query_text, evidence)
    defect = detect_defect_signals(query_text)
    line = decide_support_line(topic, defect)
    recipient, recipient_basis, recipient_rule = extract_recipient(evidence, selected_evidence_ids)

    basis_source_ids = sorted(set(topic.basis_source_ids) | set(recipient_basis))
    rule_id = line.rule_id or recipient_rule

    reason_codes: list[ReasonCode] = []

    return RoutingResult(
        topic_id=topic.topic_id,
        subtopic_id=topic.subtopic_id,
        support_line=line.support_line,
        recommended_recipient=recipient,
        basis_source_ids=basis_source_ids,
        rule_id=rule_id,
        is_probable_defect=defect.is_probable_defect,
        is_ambiguous=line.is_ambiguous,
        reason_codes=reason_codes,
    )
