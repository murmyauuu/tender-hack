"""Условный exact/FTS поиск по кодам, полям и аббревиатурам (§10 «Поиск»).

«Exact IDs выделяются до морфологии» — до вызова `fts_normalize`, который
уже снимает окончания обычных слов, но не трогает аббревиатуры и коды
(`knowledge/kb/normalize.py`). Здесь используется та же нормализация: этот
модуль не изобретает второй способ разбора текста на токены.

Только stdlib (`re`) — этот файл лежит прямо в `knowledge/kb/` и подпадает
под сканирование `test_no_model_calls.py`.
"""

from __future__ import annotations

import re

from knowledge.kb.normalize import fts_normalize, fts_tokens

__all__ = [
    "detect_exact_identifiers",
    "is_abbreviation_or_code",
]

# Аббревиатура: короткий (<=6) полностью прописной кириллический токен —
# то же правило, что и в classify.py (ИНН, СТЕ, УПД, КЭП, МЧД, ОГРН, ЭДО, ЭП).
_CYR_ABBREVIATION = re.compile(r"^[А-ЯЁ]{2,6}$")
# Латинская аббревиатура/код: YML, UPD, коды форматов.
_LAT_ABBREVIATION = re.compile(r"^[A-Z]{2,6}$")
# Составной код вида YML-12, СТЕ-04, ГОСТ-Р-52535.
_HYPHEN_CODE = re.compile(r"^[A-ZА-ЯЁ]{2,10}(?:-[A-ZА-ЯЁ0-9]{1,10})+$")
# Номер пункта/статьи: 1.2, 10.3.1.
_CLAUSE_NUMBER = re.compile(r"^\d{1,3}(?:\.\d{1,3}){1,3}$")


def is_abbreviation_or_code(token: str) -> bool:
    """Токен похож на код/аббревиатуру, а не на обычное слово запроса."""
    if not token:
        return False
    if _CYR_ABBREVIATION.match(token) or _LAT_ABBREVIATION.match(token):
        return True
    if _HYPHEN_CODE.match(token):
        return True
    if _CLAUSE_NUMBER.match(token):
        return True
    return False


def detect_exact_identifiers(text: str) -> list[str]:
    """Найти в тексте запроса токены-кандидаты на exact ID/код/аббревиатуру.

    Возвращает исходные (не нормализованные регистром) токены — по ним потом
    идёт точный/FTS поиск в `retrieval.py`. Порядок появления в тексте
    сохраняется, дубликаты убраны.
    """
    seen: list[str] = []
    for token in fts_tokens(text):
        if is_abbreviation_or_code(token) and token not in seen:
            seen.append(token)
    return seen


def exact_identifier_fts_query(identifier: str) -> str:
    """Нормализованный FTS-ключ для одной аббревиатуры/кода."""
    return fts_normalize(identifier)
