"""Детерминированная нормализация текста KB.

Два отдельных слоя, их нельзя смешивать:

* `clean_text` / `rebuild_title` — приведение читаемого текста и заголовка,
  результат хранится и показывается человеку;
* `fts_normalize` — приведение словоформ для лексического поиска, результат
  идёт только в FTS-индекс.

Русская морфология (D12/BL-C00-6 по FTS). Дефолтный `unicode61` словоформы
не сводит: по замеру C00 «контракт» 110, «контракта» 351, «контракту» 61,
«оферта» 42, «оферты» 183 — это пять разных ключей вместо двух. Английский
Porter здесь подставлять запрещено (§10 «Поиск»), поэтому реализовано
русское усечение окончаний по алгоритму Snowball для русского языка:
области RV/R2, затем последовательно PERFECTIVE GERUND, REFLEXIVE,
ADJECTIVAL, VERB, NOUN, далее «и», DERIVATIONAL и SUPERLATIVE.
Алгоритм полностью детерминирован и не зависит от словаря, поэтому два
прогона ingest дают побитово одинаковый индекс.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "clean_text",
    "rebuild_title",
    "fts_normalize",
    "fts_tokens",
    "stem_ru",
    "NORMALIZER_VERSION",
]

NORMALIZER_VERSION = "c02-normalizer-1.0.0"

_VOWELS = "аеиоуыэюя"
_TOKEN_RE = re.compile(r"[0-9a-zA-Zа-яёА-ЯЁ]+(?:[-_./][0-9a-zA-Zа-яёА-ЯЁ]+)*")

_PERFECTIVE_1 = ("вшись", "вши", "вшийся", "в")          # после а/я
_PERFECTIVE_2 = ("ившись", "ывшись", "ивши", "ывши", "ив", "ыв")
_ADJECTIVE = (
    "ыми", "ими", "его", "ому", "ему", "ого", "ых", "их", "ый", "ой", "ий",
    "ая", "яя", "ое", "ее", "ые", "ие", "ым", "им", "ом", "ем", "ую", "юю",
    "ей", "ой", "ah",
)
_PARTICIPLE_1 = ("ем", "нн", "вш", "ющ", "щ")             # после а/я
_PARTICIPLE_2 = ("ивш", "ывш", "ующ")
_REFLEXIVE = ("ся", "сь")
_VERB_1 = (
    "ешь", "ete", "йте", "ла", "на", "ли", "ем", "ло", "но", "ет", "ют",
    "ны", "ть", "й", "л", "н",
)
_VERB_2 = (
    "ейте", "уйте", "ила", "ыла", "ена", "ите", "или", "ыли", "ило", "ыло",
    "ено", "ует", "уют", "ены", "ить", "ыть", "ишь", "ила", "ыла", "ей",
    "уй", "ит", "ыт", "им", "ым", "ен", "ил", "ыл", "ыв", "ив",
)
_NOUN = (
    "иями", "ями", "ами", "ией", "иям", "ием", "иях", "ах", "ях", "ам", "ям",
    "ов", "ей", "ий", "ие", "ия", "ию", "ью", "ом", "ем", "ых", "ой", "ые",
    "ем", "ах", "ия", "а", "е", "и", "й", "о", "у", "ы", "ь", "ю", "я",
)
_DERIVATIONAL = ("ост", "ость")
_SUPERLATIVE = ("ейше", "ейш")


def _regions(word: str) -> tuple[int, int]:
    """RV — после первой гласной; R2 — по определению Snowball."""
    rv = len(word)
    for i, ch in enumerate(word):
        if ch in _VOWELS:
            rv = i + 1
            break
    r1 = len(word)
    for i in range(1, len(word)):
        if word[i] not in _VOWELS and word[i - 1] in _VOWELS:
            r1 = i + 1
            break
    r2 = len(word)
    for i in range(r1 + 1, len(word)):
        if word[i] not in _VOWELS and word[i - 1] in _VOWELS:
            r2 = i + 1
            break
    return rv, r2


def _strip(word: str, start: int, endings: tuple[str, ...], after: str = "") -> str | None:
    """Снять самое длинное подходящее окончание в пределах области."""
    for end in sorted(endings, key=len, reverse=True):
        if not word.endswith(end):
            continue
        cut = len(word) - len(end)
        if cut < start:
            continue
        if after:
            if cut == 0 or word[cut - 1] not in after:
                continue
            cut -= 1
            return word[:cut] + word[cut : cut + 1] if False else word[: cut + 1]
        return word[:cut]
    return None


def stem_ru(word: str) -> str:
    """Основа русского слова. Детерминированно, без словаря."""
    word = word.lower().replace("ё", "е")
    if not word or not any(c in _VOWELS for c in word):
        return word
    rv, r2 = _regions(word)

    # Шаг 1: perfective gerund -> иначе reflexive, затем adjectival/verb/noun
    step = _strip(word, rv, _PERFECTIVE_2)
    if step is None:
        step = _strip(word, rv, _PERFECTIVE_1, after="ая")
    if step is not None:
        word = step
    else:
        refl = _strip(word, rv, _REFLEXIVE)
        if refl is not None:
            word = refl
        adj = _strip(word, rv, _ADJECTIVE)
        if adj is not None:
            word = adj
            part = _strip(word, rv, _PARTICIPLE_2)
            if part is None:
                part = _strip(word, rv, _PARTICIPLE_1, after="ая")
            if part is not None:
                word = part
        else:
            verb = _strip(word, rv, _VERB_2)
            if verb is None:
                verb = _strip(word, rv, _VERB_1, after="ая")
            if verb is not None:
                word = verb
            else:
                noun = _strip(word, rv, _NOUN)
                if noun is not None:
                    word = noun

    # Шаг 2: убрать «и»
    if word.endswith("и"):
        cut = len(word) - 1
        if cut >= rv:
            word = word[:cut]

    # Шаг 3: derivational в области R2
    rv, r2 = _regions(word)
    der = _strip(word, r2, _DERIVATIONAL)
    if der is not None:
        word = der

    # Шаг 4: «нн» -> «н», superlative, мягкий знак
    if word.endswith("нн"):
        word = word[:-1]
    elif word.endswith("ь"):
        word = word[:-1]
    else:
        sup = _strip(word, rv, _SUPERLATIVE)
        if sup is not None:
            word = sup
            if word.endswith("нн"):
                word = word[:-1]
    return word


def fts_tokens(text: str) -> list[str]:
    """Безопасные токены для FTS: без служебных символов синтаксиса FTS5.

    Регистр исходного токена сохраняется — он нужен, чтобы отличить
    аббревиатуру (ИНН, СТЕ, УПД, КЭП) от обычного слова.
    """
    text = unicodedata.normalize("NFKC", text or "")
    return [m.group(0) for m in _TOKEN_RE.finditer(text)]


_CYR_WORD = re.compile(r"^[а-яё]+$")


def _is_abbreviation(token: str) -> bool:
    """Аббревиатура: короткий полностью прописной токен из кириллицы."""
    return (
        len(token) <= 6
        and token.isupper()
        and bool(re.fullmatch(r"[А-ЯЁ]+", token))
    )


def _normalize_token(token: str) -> str:
    """Один токен: морфология только для обычных русских слов."""
    if _is_abbreviation(token):
        return token.lower().replace("ё", "е")
    lowered = token.lower().replace("ё", "е")
    if _CYR_WORD.match(lowered):
        return stem_ru(lowered)
    # составной токен (прайс-лист, п.1.2, yml-12): нормализуем части
    if re.search(r"[-_./]", lowered):
        parts = re.split(r"([-_./])", lowered)
        return "".join(
            stem_ru(p) if _CYR_WORD.match(p) and not _is_abbreviation(p) else p
            for p in parts
        )
    return lowered


def fts_normalize(text: str) -> str:
    """Строка для FTS-индекса: единая русская нормализация словоформ.

    Латиница, цифры и аббревиатуры не стеммируются — коды, аббревиатуры и
    номера полей должны оставаться точными (§10 «Поиск»: exact IDs
    выделяются до морфологии).
    """
    return " ".join(_normalize_token(tok) for tok in fts_tokens(text))


# ------------------------------------------------------------------ читаемый текст

_SOFT_HYPHEN = "­"


def clean_text(text: str) -> str:
    """Привести извлечённый текст к читаемому виду без потери содержания.

    Склеивает разрывы, порождённые построчным показом текста в PDF, и
    схлопывает повторные пробелы. Слова и знаки не удаляются.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).replace(_SOFT_HYPHEN, "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in text.split("\n")]
    out: list[str] = []
    for ln in lines:
        if not ln:
            if out and out[-1] != "":
                out.append("")
            continue
        if (
            out
            and out[-1]
            and not re.search(r"[.:;!?»)]$", out[-1])
            and not re.match(r"^[-–—•*]|^\d+[.)]\s|^[А-ЯЁ]{4,}", ln)
            and len(out[-1]) < 200
        ):
            out[-1] = f"{out[-1]} {ln}".strip()
        else:
            out.append(ln)
    text = "\n".join(out)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_DOT_LEADER = re.compile(r"\.{4,}")


def rebuild_title(raw_title: str, content: str, source_name: str = "") -> tuple[str, str]:
    """Вернуть (title, reason). Заголовок восстанавливается, когда исходный
    непригоден: имя файла, точки-лидеры оглавления, версионный штамп,
    пустая строка. Текст заголовка не выдумывается — он всегда берётся из
    фактического содержания записи.
    """
    title = unicodedata.normalize("NFKC", (raw_title or "")).strip()
    reason = ""

    def first_sentence(body: str) -> str:
        body = clean_text(body)
        for line in body.split("\n"):
            line = _DOT_LEADER.sub(" ", line).strip(" .…")
            line = re.sub(r"\s{2,}", " ", line)
            if len(line) >= 12 and re.search(r"[А-Яа-яЁё]{3,}", line):
                return line[:180].strip()
        return ""

    if re.search(r"\.(pdf|docx?|xlsx?|pptx?)$", title, re.I):
        reason = "title_was_filename"
    elif _DOT_LEADER.search(title):
        reason = "title_was_toc_line"
    elif re.fullmatch(r"[\d.]{6,}\s*v?\d*", title):
        reason = "title_was_version_stamp"
    elif not title:
        reason = "title_was_empty"
    elif len(title) < 4:
        reason = "title_too_short"

    if reason:
        rebuilt = first_sentence(content)
        if rebuilt:
            return rebuilt, reason
        return (title or source_name or "unknown"), f"{reason}_no_replacement_in_content"

    title = _DOT_LEADER.sub(" ", title)
    return re.sub(r"\s{2,}", " ", title).strip(), ""
