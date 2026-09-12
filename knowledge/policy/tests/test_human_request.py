"""Категории: human request positive, ambiguous human request negative."""

from __future__ import annotations

import pytest

POSITIVE = [
    ("Соедините меня с оператором", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Переключите на человека", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Позовите специалиста", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Передайте обращение оператору", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Прошу перевести на сотрудника поддержки", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Переведите в поддержку", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Свяжите меня со специалистом", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Вызовите консультанта", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Эскалируйте обращение оператору", "POL.HUMAN.TRANSFER_REQUEST"),
    ("Мне нужен оператор", "POL.HUMAN.NEED_PERSON"),
    ("Хочу поговорить с живым человеком", "POL.HUMAN.LIVE_PERSON"),
    ("Дайте живого человека", "POL.HUMAN.LIVE_PERSON"),
    ("Есть тут живой человек?", "POL.HUMAN.LIVE_PERSON"),
    ("Я хочу общаться не с ботом", "POL.HUMAN.NOT_BOT"),
    ("оператор", "POL.HUMAN.TARGET_ONLY"),
    ("Оператора, пожалуйста", "POL.HUMAN.TARGET_ONLY"),
    ("человека!", "POL.HUMAN.TARGET_ONLY"),
]


@pytest.mark.parametrize(("text", "rule_id"), POSITIVE)
def test_explicit_human_request_is_detected(policy, text: str, rule_id: str) -> None:
    result = policy.check(text)
    assert result.explicit_human_request is True
    assert rule_id in result.matched_rule_ids
    assert result.profanity is False


AMBIGUOUS = [
    # Общее недовольство и жалоба — не подтверждение передачи.
    "это не работает",
    "ужасный сервис",
    "я очень недоволен качеством поддержки",
    "почему так долго отвечаете",
    "хочу написать жалобу",
    "ваш бот бесполезен",
    "мне нужна помощь",
    "кто мне поможет с УПД",
    "поддержка не отвечает",
    "ничего не понятно, всё сломано",
    # Вопрос про контакты — knowledge-вопрос, а не передача.
    "как связаться с оператором?",
    "где найти телефон поддержки",
    "какой номер телефона службы поддержки",
    "как написать в поддержку",
    "какой режим работы у поддержки",
    # Упоминание человека без просьбы.
    "оператор мне вчера ответил неправильно",
    "специалисты компании подготовили заявку",
    "менеджер заказчика согласовал позицию",
    # Явный отказ от передачи.
    "мне не нужен оператор, я сам разберусь",
    "не надо оператора",
    # Предметные запросы, где маркер есть, а адресата-человека нет.
    "хочу оформить оферту",
    "нужен документ по 44-ФЗ",
    "требуется подписать УПД",
    "дайте инструкцию по актированию",
]


@pytest.mark.parametrize("text", AMBIGUOUS)
def test_ambiguous_phrases_do_not_confirm_handoff(policy, text: str) -> None:
    result = policy.check(text)
    assert result.explicit_human_request is False, result.matched_rule_ids


def test_request_in_second_sentence_is_detected(policy) -> None:
    text = "Оферта не загружается. Соедините меня с оператором, пожалуйста."
    result = policy.check(text)
    assert result.explicit_human_request is True


def test_howto_question_does_not_suppress_real_request_in_other_sentence(
    policy,
) -> None:
    text = "Как связаться с оператором? Переведите меня на человека."
    result = policy.check(text)
    assert result.explicit_human_request is True
    assert "POL.HUMAN.TRANSFER_REQUEST" in result.matched_rule_ids
