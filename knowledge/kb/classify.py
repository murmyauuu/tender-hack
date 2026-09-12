"""Классификация записей KB: служебный мусор, полнота, роли.

Каждое решение возвращается вместе с причиной. Запись никогда не
выбрасывается «по длине»: короткий полезный ответ портала обязан выжить
(§10.2, C00 — 57 таких записей). Критерии повторяют замеры C00 (D5, D6, D8),
чтобы counts C02 сходились с аудитом.
"""

from __future__ import annotations

import re

__all__ = [
    "service_fragment_reason",
    "attachment_status",
    "derive_roles",
    "AUDIENCE_IS_NOT_ROLE",
]

# ---------------------------------------------------------------- служебный мусор

_DOT_LEADER = re.compile(r"\.{4,}")
_PAGE_NUMBER_ONLY = re.compile(r"^\s*\d{1,4}\s*$")
_BLANK_PAGE = re.compile(r"^[\s\d]*$")


def service_fragment_reason(content: str, title: str = "") -> str | None:
    """Причина исключения служебного фрагмента либо None.

    Классы взяты из C00/D5 и проверяются в порядке специфичности:
    номер страницы вместо содержания и строка оглавления по точкам-лидерам.
    Длина сама по себе критерием не является.
    """
    body = (content or "").strip()
    if not body:
        return "empty_content"
    # Оглавление проверяется первым: строка оглавления часто имеет
    # точки-лидеры в title, а в content — только номер страницы, и такая
    # запись принадлежит обоим классам сразу.
    if _DOT_LEADER.search(body) or _DOT_LEADER.search(title or ""):
        return "content_is_table_of_contents"
    if _PAGE_NUMBER_ONLY.match(body):
        return "content_is_page_number_only"
    if _BLANK_PAGE.match(body):
        return "content_is_blank_page"
    return None


# ------------------------------------------------------------------- полнота

_FIGURE_REF = re.compile(r"\b(?:Рисун(?:ок|ке|ка)|Рис\.)\s*\d+", re.I)
_POINTER_REF = re.compile(r"\b(?:Приложени[еяию]|см\.\s|смотри\s)", re.I)


def attachment_status(content: str) -> tuple[str, str | None]:
    """Вернуть (content_status, eligibility_reason).

    * ссылка на отсутствующий рисунок -> incomplete (C00/D6: 776 чанков);
      изображения в снимок KB не переносились ни разу, поэтому ссылка
      заведомо не разрешается. Отсутствующий скриншот не считается
      прочитанным (§10.7);
    * ссылка на приложение/«см.» без самого приложения -> pointer:
      указатель не обосновывает отсутствующее содержание (§10.5).
    """
    body = content or ""
    has_figure = bool(_FIGURE_REF.search(body))
    has_pointer = bool(_POINTER_REF.search(body))
    if has_figure:
        return "incomplete", "MISSING_ATTACHMENT: ссылка на рисунок, изображение отсутствует в снимке"
    if has_pointer:
        return "pointer", "POINTER: ссылка на приложение/другой раздел, содержание не включено"
    return "complete", None


# ---------------------------------------------------------------------- роли

# `instruction` — это sectionType выгрузки, а не роль пользователя (§10.4,
# C00/D4: 192 записи). `general` и пусто тоже не означают «все роли».
AUDIENCE_IS_NOT_ROLE = {"instruction", "general", ""}

_ROLE_MAP = {"supplier": "supplier", "customer": "customer"}


def derive_roles(audience_raw: str | None) -> tuple[list[str], bool]:
    """Вернуть (applicable_roles, role_verified).

    Роль признаётся только для явных значений supplier/customer.
    Всё остальное -> пустой список и role_verified=False: unknown остаётся
    unknown и не превращается в «все роли».
    """
    raw = (audience_raw or "").strip().lower()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    roles = [_ROLE_MAP[p] for p in parts if p in _ROLE_MAP]
    if not roles:
        return [], False
    return sorted(set(roles)), True
