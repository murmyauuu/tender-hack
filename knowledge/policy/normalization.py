"""Нормализация текста ТОЛЬКО для поиска совпадений policy-правил.

Инварианты модуля:

* исходный текст никогда не изменяется и не возвращается наружу изменённым —
  функции принимают ``str`` и возвращают отдельные списки кандидатов;
* нормализация детерминирована: одинаковый вход даёт одинаковый выход;
* используется только stdlib (``re``, ``unicodedata``) — ни LLM, ни embeddings,
  ни сети.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Служебный символ-заполнитель. Занимает позицию любого разделителя внутри
#: слова или замаскированной буквы. В пользовательском тексте не встречается.
SENTINEL = "\x01"

_CYRILLIC_RE = re.compile(r"[а-яё]")
_ALNUM_RE = re.compile(r"[^\W_]", re.UNICODE)


@dataclass(frozen=True)
class MatchCandidate:
    """Кандидат для сопоставления с правилом.

    ``text`` — нормализованная строка над алфавитом ``[а-я a-z 0-9 SENTINEL]``.
    ``origin`` — как кандидат получен: ``word`` (одно слово исходного текста)
    или ``merged`` (склеенный ряд коротких слов — защита от пробелов внутри
    слова). ``has_cyrillic`` нужен для правил, привязанных к алфавиту.
    """

    text: str
    origin: str
    has_cyrillic: bool


def _as_candidates(
    variants: list[str], origin: str, has_cyrillic: bool
) -> list[MatchCandidate]:
    """Убирает дубликаты и пустые варианты, сохраняя порядок."""
    result: list[MatchCandidate] = []
    seen: set[str] = set()
    for variant in variants:
        text = variant.strip(SENTINEL)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(MatchCandidate(text=text, origin=origin, has_cyrillic=has_cyrillic))
    return result


class Normalizer:
    """Компилирует конфигурацию нормализации и готовит кандидатов."""

    def __init__(self, config: dict) -> None:
        norm = config["normalization"]
        self._fold_yo: bool = bool(norm.get("fold_yo", True))
        self._max_run: int = int(norm.get("max_char_run", 3))
        self._zero_width: tuple[str, ...] = tuple(norm.get("zero_width", ()))
        self._homoglyphs: dict[str, str] = dict(norm.get("homoglyph_map", {}))
        self._digits: dict[str, str] = dict(norm.get("digit_map", {}))
        merge = norm.get("word_merge", {})
        self._merge_max_words = int(merge.get("max_words", 5))
        self._merge_max_word_len = int(merge.get("max_word_len", 3))
        self._merge_require_short = int(merge.get("require_short_word_len", 2))

        self._char_map = str.maketrans({**self._homoglyphs, **self._digits})
        self._run_re = re.compile(r"(.)\1{" + str(self._max_run) + r",}")
        self._tech_spans = [
            (span["id"], re.compile(span["pattern"]))
            for span in config.get("technical_spans", [])
        ]

    # ------------------------------------------------------------------ шаги

    def strip_technical(self, text: str) -> tuple[str, list[str]]:
        """Гасит технические конструкции (URL, GUID, пути, идентификаторы, коды).

        Заменяет их пробелом, чтобы гомоглифы и склейка не собрали из кода
        ложное совпадение. Возвращает (текст для матчинга, id сработавших
        технических шаблонов).
        """
        hit_ids: list[str] = []
        result = text
        for span_id, pattern in self._tech_spans:
            result, count = pattern.subn(" ", result)
            if count:
                hit_ids.append(span_id)
        return result, hit_ids

    def fold(self, text: str) -> str:
        """Unicode/регистр/ё/повторы. Без склейки и без подмены символов."""
        folded = unicodedata.normalize("NFKC", text)
        for zw in self._zero_width:
            folded = folded.replace(zw, "")
        folded = folded.casefold()
        if self._fold_yo:
            folded = folded.replace("ё", "е")
        return self._run_re.sub(lambda m: m.group(1) * self._max_run, folded)

    def _prepare_word(self, word: str) -> list[MatchCandidate]:
        """Одно слово исходного текста -> 1..2 кандидата.

        Все не буквенно-цифровые символы внутри слова становятся SENTINEL:
        движок правил трактует SENTINEL и как пропускаемый разделитель
        (``х.у.й``), и как маску одной буквы (``х*й``).

        Цифра в слове с кириллицей читается двумя способами, поэтому кандидатов
        может быть два: цифра-как-буква (``пи3дец`` -> ``пиздец``) и
        цифра-как-маска (``п3здец`` -> ``п?здец``). Цифры вне карты замен
        всегда маска (``бл9дь``).
        """
        chars: list[str] = []
        for ch in word:
            chars.append(ch if _ALNUM_RE.match(ch) else SENTINEL)
        raw = "".join(chars)
        letters = raw.replace(SENTINEL, "")
        if not letters:
            return []
        has_cyrillic = bool(_CYRILLIC_RE.search(letters))
        if not has_cyrillic:
            # Гомоглифы и цифры-как-буквы применяем только к словам, где уже
            # есть кириллица. Чисто латинские токены (english, identifiers,
            # base64) не переписываются — это главный барьер от false positives.
            return _as_candidates([raw], "word", False)

        mapped = "".join(
            self._char_map.get(ord(ch), ch) if ch.isdigit() or ch in self._homoglyphs
            else ch
            for ch in raw
        )
        mapped = "".join(SENTINEL if ch.isdigit() else ch for ch in mapped)
        masked = "".join(
            SENTINEL if ch.isdigit() else self._char_map.get(ord(ch), ch)
            for ch in raw
        )
        return _as_candidates([mapped, masked], "word", True)

    def _merged_candidates(self, words: list[MatchCandidate]) -> list[MatchCandidate]:
        """Склейка рядов коротких слов — защита от пробелов внутри слова.

        Склеиваются только ряды длиной 2..max_words, где каждое слово не длиннее
        ``max_word_len`` и хотя бы одно слово не длиннее ``require_short_word_len``.
        Длинные слова не склеиваются никогда, поэтому произвольного склеивания
        предложения в одну строку не происходит.
        """
        merged: list[MatchCandidate] = []
        n = len(words)
        for start in range(n):
            if len(words[start].text.replace(SENTINEL, "")) > self._merge_max_word_len:
                continue
            run: list[MatchCandidate] = []
            for index in range(start, min(n, start + self._merge_max_words)):
                word = words[index]
                if len(word.text.replace(SENTINEL, "")) > self._merge_max_word_len:
                    break
                run.append(word)
                if len(run) < 2:
                    continue
                if not any(
                    len(w.text.replace(SENTINEL, "")) <= self._merge_require_short
                    for w in run
                ):
                    continue
                merged.append(
                    MatchCandidate(
                        text="".join(w.text for w in run),
                        origin="merged",
                        has_cyrillic=any(w.has_cyrillic for w in run),
                    )
                )
        return merged

    # ----------------------------------------------------------------- вывод

    def candidates(self, text: str) -> tuple[list[MatchCandidate], list[str]]:
        """Полный конвейер: technical -> fold -> слова -> склейки."""
        cleaned, tech_ids = self.strip_technical(text)
        folded = self.fold(cleaned)
        words: list[MatchCandidate] = []
        primary: list[MatchCandidate] = []
        for chunk in folded.split():
            variants = self._prepare_word(chunk)
            if not variants:
                continue
            words.extend(variants)
            primary.append(variants[0])
        return words + self._merged_candidates(primary), tech_ids

    def plain_text(self, text: str) -> str:
        """Нормализованный текст со пробелами вместо пунктуации.

        Используется правилами explicit_human_request, которые работают по
        словам и порядку слов, а не по посимвольной маскировке.
        """
        cleaned, _ = self.strip_technical(text)
        folded = self.fold(cleaned)
        spaced = re.sub(r"[^\w]+", " ", folded, flags=re.UNICODE)
        return re.sub(r"\s+", " ", spaced).strip()
