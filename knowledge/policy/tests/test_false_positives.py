"""Категории: false positives и technical strings.

Ни один benign-кейс не должен блокироваться. Совпадение обязано опираться на
границу слова/токена, а не на вхождение подстроки куда угодно.
"""

from __future__ import annotations

import pytest

# Обычные русские слова и слова с похожими подстроками.
ORDINARY_WORDS = [
    "страховка оформлена",
    "сухой закон",
    "ухудшение качества связи",
    "требование заказчика по контракту",
    "хлеб и соль",
    "он взял это на себя",
    "тебя не слышно",
    "лебедь, рак и щука",
    "ребенок записан",
    "щебень фракции 20-40",
    "дебет и кредит",
    "жеребец",
    "небеса",
    "серебро 925",
    "верба",
    "плебей",
    "стебель растения",
    "гребень волны",
    "мудрость решения",
    "мудрый подход",
    "команда поставщика",
    "гондола подъемника",
    "пизанская башня",
    "поезд задерживается",
    "объезд закрыт",
    "подъезд номер 3",
    "отъезд перенесен",
    "изъять позицию из оферты",
    "въезд на территорию",
    "духи в подарочной упаковке",
    "сукно для бильярда",
    "сучок на доске",
    "сук дерева обрезан",
    "спишите остаток",
    "обед с 13 до 14",
    "надоест ждать",
    "херсонес",
    "херес сухой",
    "херувим",
    "Хуан Карлос",
    "хутор",
    "хуже некуда",
    "похудеть на 5 кг",
    "неухоженный участок",
    "блюдо дня",
    "бляха-муха",
    "область применения",
    "суконная фабрика",
]

# Технические сообщения, стектрейсы, названия полей, коды, URL, GUID.
TECHNICAL_STRINGS = [
    "https://zakupki.mos.ru/api/Cssp/Sku/Get?id=12345",
    "www.mos.ru/support",
    "Написал на support@zakupki.mos.ru, ответа нет",
    "GUID 2f8a1c3e-4b5d-4a6f-8c9e-0d1e2f3a4b5c не найден",
    "case_id=22222222-2222-4222-8222-222222222222",
    "0x1F4AB2C9",
    "ошибка в поле case_version при POST /api/v1/cases",
    "поле source_ids пришло пустым",
    "sourceIds пустой массив",
    "active_request_id is null",
    'File "app.py", line 42, in handler',
    "Traceback (most recent call last): ValueError: invalid literal",
    "tenderhack_backend.app:app не стартует",
    "C:\\Users\\user\\Downloads\\report.xlsx не открывается",
    "/var/knowledge/index.npy отсутствует",
    "HTTP 500 Internal Server Error",
    "СТЕ-1234567 не проходит модерацию",
    "по 44-ФЗ и 223-ФЗ разные правила",
    "ИНН 7701234567 не найден",
    "ОКПД2 26.20.11",
    "КБК 000 0000 0000000 000",
    "ГОСТ Р 51141",
    "1С не выгружает YML",
    "base64 декодируется с ошибкой",
    "proxy не отвечает",
    "oxygen sensor",
    "Подтема запроса: Электронное актирование/УПД",
    "snapshot_id=mock-c0, contracts_version=2.0.0-c0",
    "SHA-256 439e7041b233498a894a9eab41917e07e79109408e1f09b7cbb96668c1b8df2c",
    "3D-модель не загружается",
]

AMBIGUOUS_COMPLAINTS = [
    "это не работает",
    "ужасный сервис",
    "я очень недоволен качеством поддержки",
    "почему так долго отвечаете",
    "это вообще не решение",
    "верните деньги",
    "он не мог войти в систему",
    "в то же время заявка висит",
    "я не бу ду ждать",
    "то же самое повторяется",
    "поедем дальше по инструкции",
]


@pytest.mark.parametrize("text", ORDINARY_WORDS)
def test_ordinary_words_are_not_blocked(policy, text: str) -> None:
    result = policy.check(text)
    assert result.profanity is False, result.matched_rule_ids


@pytest.mark.parametrize("text", TECHNICAL_STRINGS)
def test_technical_strings_are_not_blocked(policy, text: str) -> None:
    result = policy.check(text)
    assert result.profanity is False, result.matched_rule_ids


@pytest.mark.parametrize("text", AMBIGUOUS_COMPLAINTS)
def test_complaints_without_profanity_are_not_blocked(policy, text: str) -> None:
    result = policy.check(text)
    assert result.profanity is False, result.matched_rule_ids


def test_substring_alone_never_matches(policy) -> None:
    """Корень внутри чужого слова без морфологической границы не срабатывает."""
    # "еб" внутри "требование"/"хлебозавод", "ху" внутри "ухудшение" —
    # ни одно из этих вхождений не стоит на позиции префикс+корень.
    for text in ("требование", "хлебозавод", "ухудшение", "себестоимость", "тебе"):
        assert policy.check(text).profanity is False, text


def test_empty_and_whitespace_are_clean(policy) -> None:
    for text in ("", " ", "\n\t", "...", "!!!", "***"):
        result = policy.check(text)
        assert result.profanity is False
        assert result.explicit_human_request is False
        assert result.matched_rule_ids == []
