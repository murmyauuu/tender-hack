"""Извлечение текстового слоя PDF средствами стандартной библиотеки.

Зачем свой парсер. C00 (`knowledge/audit/audit_inputs.py`) уже читал PDF
через `zlib` + regex по content stream: так были получены число страниц и
факт наличия текстового слоя (операторы Tj/TJ). C00 при этом не приводил
глифы к Unicode, потому что для аудита это не требовалось. C02 обязан
загрузить Регламент (BL-C00-1) и пропущенную стр. 3 (D9) реальным текстом,
поэтому подход C00 продолжен до декодирования, а не заменён новой
зависимостью: на профиле M тяжёлые пакеты ставить запрещено, и в окружении
нет ни pypdf, ни pdfminer, ни PyObjC/Quartz.

Поддерживается ровно то, что фактически встречается во входных PDF
(проверено пробой: PDF 1.7, /Filter /FlateDecode, /Type /ObjStm,
шрифты Type0+Identity-H с /ToUnicode и TrueType+WinAnsiEncoding):

* объекты собираются прямым сканированием `N G obj ... endobj`
  и раскрытием потоков объектов (/Type /ObjStm);
* порядок страниц берётся обходом дерева /Pages -> /Kids;
* текст декодируется по /ToUnicode CMap (bfchar/bfrange), при её
  отсутствии — по /Encoding /WinAnsiEncoding.

Неизвестный код глифа даёт "" и учитывается в `undecoded`, а не заменяется
догадкой: непрочитанное остаётся непрочитанным.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

__all__ = ["PdfDocument", "PdfPage", "extract_pages"]

_OBJ_RE = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b")
_WINANSI_HIGH = {
    0x80: "€", 0x82: "‚", 0x83: "ƒ", 0x84: "„",
    0x85: "…", 0x86: "†", 0x87: "‡", 0x88: "ˆ",
    0x89: "‰", 0x8A: "Š", 0x8B: "‹", 0x8C: "Œ",
    0x8E: "Ž", 0x91: "‘", 0x92: "’", 0x93: "“",
    0x94: "”", 0x95: "•", 0x96: "–", 0x97: "—",
    0x98: "˜", 0x99: "™", 0x9A: "š", 0x9B: "›",
    0x9C: "œ", 0x9E: "ž", 0x9F: "Ÿ",
}


@dataclass
class PdfPage:
    number: int
    text: str
    undecoded: int = 0


@dataclass
class PdfDocument:
    path: str
    pages: list[PdfPage] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)


# --------------------------------------------------------------- низкий уровень


def _find_objects(blob: bytes) -> dict[int, bytes]:
    """Тело каждого объекта по номеру. При повторах побеждает последний
    (инкрементальные обновления PDF дописываются в конец файла)."""
    objects: dict[int, bytes] = {}
    for m in _OBJ_RE.finditer(blob):
        num = int(m.group(1))
        end = blob.find(b"endobj", m.end())
        objects[num] = blob[m.end() : end if end >= 0 else len(blob)]
    return objects


def _dict_slice(body: bytes) -> bytes:
    """Внешний словарь << ... >> с учётом вложенности."""
    start = body.find(b"<<")
    if start < 0:
        return b""
    depth, i = 0, start
    while i < len(body) - 1:
        pair = body[i : i + 2]
        if pair == b"<<":
            depth += 1
            i += 2
            continue
        if pair == b">>":
            depth -= 1
            i += 2
            if depth == 0:
                return body[start:i]
            continue
        i += 1
    return body[start:]


def _stream_bytes(body: bytes) -> bytes | None:
    m = re.search(rb"stream\r?\n", body)
    if not m:
        return None
    end = body.rfind(b"endstream")
    raw = body[m.end() : end if end >= 0 else len(body)]
    try:
        return zlib.decompress(raw)
    except zlib.error:
        try:  # усечённый/битый хвост потока
            return zlib.decompressobj().decompress(raw)
        except zlib.error:
            return None


def _expand_object_streams(objects: dict[int, bytes]) -> dict[int, bytes]:
    """Раскрыть /Type /ObjStm: объекты внутри них адресуются как обычные."""
    out = dict(objects)
    for body in objects.values():
        head = _dict_slice(body)
        if b"/ObjStm" not in head:
            continue
        data = _stream_bytes(body)
        if data is None:
            continue
        n_m = re.search(rb"/N\s+(\d+)", head)
        first_m = re.search(rb"/First\s+(\d+)", head)
        if not (n_m and first_m):
            continue
        n, first = int(n_m.group(1)), int(first_m.group(1))
        nums = [int(x) for x in re.findall(rb"(\d+)", data[:first])]
        pairs = list(zip(nums[0::2], nums[1::2]))[:n]
        for idx, (obj_num, offset) in enumerate(pairs):
            start = first + offset
            stop = first + pairs[idx + 1][1] if idx + 1 < len(pairs) else len(data)
            out.setdefault(obj_num, data[start:stop])
    return out


def _resolve(objects: dict[int, bytes], token: bytes) -> bytes:
    """Развернуть косвенную ссылку `N 0 R` в тело объекта."""
    m = re.fullmatch(rb"\s*(\d+)\s+\d+\s+R\s*", token)
    if not m:
        return token
    return objects.get(int(m.group(1)), b"")


# ------------------------------------------------------------------- ToUnicode


def _parse_cmap(data: bytes) -> dict[int, str]:
    """CMap /ToUnicode: секции bfchar и bfrange."""
    cmap: dict[int, str] = {}

    def utf16be(hex_text: bytes) -> str:
        raw = bytes.fromhex(hex_text.decode("ascii"))
        try:
            return raw.decode("utf-16-be", errors="ignore")
        except UnicodeDecodeError:
            return ""

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            cmap[int(src, 16)] = utf16be(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
        ):
            start, stop, base = int(lo, 16), int(hi, 16), int(dst, 16)
            for i in range(start, min(stop, start + 65535) + 1):
                cmap[i] = chr(base + i - start)
        # форма <lo> <hi> [ <d1> <d2> ... ]
        for lo, _hi, items in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.S
        ):
            start = int(lo, 16)
            for off, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", items)):
                cmap[start + off] = utf16be(dst)
    return cmap


@dataclass
class _Font:
    two_byte: bool = False
    cmap: dict[int, str] = field(default_factory=dict)

    def decode(self, raw: bytes) -> tuple[str, int]:
        out, missing = [], 0
        if self.two_byte:
            codes = [
                int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw) - 1, 2)
            ]
        else:
            codes = list(raw)
        for code in codes:
            ch = self.cmap.get(code)
            if ch is None:
                if self.two_byte:
                    missing += 1
                    continue
                ch = _WINANSI_HIGH.get(code) or (chr(code) if 32 <= code < 127 else "")
                if not ch:
                    missing += 1
            out.append(ch)
        return "".join(out), missing


def _build_fonts(objects: dict[int, bytes], resources: bytes) -> dict[bytes, _Font]:
    fonts: dict[bytes, _Font] = {}
    res = _dict_slice(resources)
    m = re.search(rb"/Font\s*(<<.*|\d+\s+\d+\s+R)", res, re.S)
    if not m:
        return fonts
    font_dict = _dict_slice(_resolve(objects, m.group(1)) if b"R" == m.group(1)[-1:] else m.group(1))
    for name, ref in re.findall(rb"(/[A-Za-z0-9#+._-]+)\s+(\d+\s+\d+\s+R)", font_dict):
        body = _resolve(objects, ref)
        if not body:
            continue
        head = _dict_slice(body)
        font = _Font(two_byte=b"/Identity-H" in head or b"/Type0" in head)
        tu = re.search(rb"/ToUnicode\s+(\d+\s+\d+\s+R)", head)
        if tu:
            data = _stream_bytes(_resolve(objects, tu.group(1)))
            if data:
                font.cmap = _parse_cmap(data)
        if not font.cmap and not font.two_byte:
            font.cmap = {c: chr(c) for c in range(32, 127)} | _WINANSI_HIGH
        fonts[name] = font
    return fonts


# -------------------------------------------------------------- content stream

_STR_TOKEN = re.compile(rb"<([0-9A-Fa-f\s]*)>|\(((?:\\.|[^\\)])*)\)", re.S)


def _unescape_literal(raw: bytes) -> bytes:
    out, i = bytearray(), 0
    mapping = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12}
    while i < len(raw):
        if raw[i : i + 1] == b"\\" and i + 1 < len(raw):
            nxt = raw[i + 1 : i + 2]
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
            elif nxt.isdigit():
                oct_digits = raw[i + 1 : i + 4]
                m = re.match(rb"[0-7]{1,3}", oct_digits)
                if m:
                    out.append(int(m.group(0), 8) & 0xFF)
                    i += 1 + len(m.group(0))
                else:
                    i += 2
            elif nxt == b"\n":
                i += 2
            else:
                out += nxt
                i += 2
        else:
            out += raw[i : i + 1]
            i += 1
    return bytes(out)


def _render_content(data: bytes, fonts: dict[bytes, _Font]) -> tuple[str, int]:
    """Выдать текст страницы по операторам показа текста.

    Разрывы строк берутся из операторов позиционирования (Td/TD/T*/TJ-сдвиг),
    а не из координат: этого достаточно для читаемого текстового слоя и не
    требует полной модели графического состояния.
    """
    lines: list[str] = []
    current: list[str] = []
    font = _Font(cmap={c: chr(c) for c in range(32, 127)} | _WINANSI_HIGH)
    undecoded = 0

    def flush() -> None:
        if current:
            lines.append("".join(current))
            current.clear()

    for m in re.finditer(
        rb"/([A-Za-z0-9#+._-]+)\s+[-\d.]+\s+Tf"
        rb"|(\[(?:[^\[\]\\]|\\.)*\])\s*TJ"
        rb"|(<[0-9A-Fa-f\s]*>|\((?:\\.|[^\\)])*\))\s*(Tj|')"
        rb"|(T\*|TD|Td)"
        rb"|(BT|ET)",
        data,
        re.S,
    ):
        if m.group(1) is not None:
            font = fonts.get(b"/" + m.group(1), font)
        elif m.group(2) is not None:
            for sm in _STR_TOKEN.finditer(m.group(2)):
                raw = (
                    bytes.fromhex(re.sub(rb"\s", b"", sm.group(1)).decode("ascii") or "00")
                    if sm.group(1) is not None
                    else _unescape_literal(sm.group(2))
                )
                text, miss = font.decode(raw)
                undecoded += miss
                current.append(text)
            # большой отрицательный сдвиг внутри TJ трактуем как пробел
            for gap in re.findall(rb"(-\d{3,})", m.group(2)):
                if int(gap) < -150:
                    current.append(" ")
                    break
        elif m.group(3) is not None:
            tok = m.group(3)
            raw = (
                bytes.fromhex(re.sub(rb"\s", b"", tok[1:-1]).decode("ascii") or "00")
                if tok.startswith(b"<")
                else _unescape_literal(tok[1:-1])
            )
            text, miss = font.decode(raw)
            undecoded += miss
            current.append(text)
            if m.group(4) == b"'":
                flush()
        elif m.group(5) is not None:
            flush()
        elif m.group(6) == b"ET":
            flush()
    flush()
    return "\n".join(lines), undecoded


# ------------------------------------------------------------------ дерево страниц


def _page_refs(objects: dict[int, bytes]) -> list[int]:
    """Номера объектов страниц в порядке документа (обход /Pages -> /Kids)."""
    root = None
    for num, body in objects.items():
        head = _dict_slice(body)
        if b"/Type" in head and b"/Catalog" in head:
            m = re.search(rb"/Pages\s+(\d+)\s+\d+\s+R", head)
            if m:
                root = int(m.group(1))
                break
    order: list[int] = []
    seen: set[int] = set()

    def walk(num: int, depth: int = 0) -> None:
        if num in seen or depth > 64:
            return
        seen.add(num)
        head = _dict_slice(objects.get(num, b""))
        if re.search(rb"/Type\s*/Page[^s]", head + b" "):
            order.append(num)
            return
        kids = re.search(rb"/Kids\s*\[(.*?)\]", head, re.S)
        if kids:
            for ref in re.findall(rb"(\d+)\s+\d+\s+R", kids.group(1)):
                walk(int(ref), depth + 1)

    if root is not None:
        walk(root)
    if not order:  # запасной путь: прямой отбор объектов страниц
        order = sorted(
            num
            for num, body in objects.items()
            if re.search(rb"/Type\s*/Page[^s]", _dict_slice(body) + b" ")
        )
    return order


def extract_pages(path: str) -> PdfDocument:
    """Постранично извлечь текстовый слой PDF. Только stdlib."""
    blob = open(path, "rb").read()
    objects = _expand_object_streams(_find_objects(blob))
    doc = PdfDocument(path=path)

    for index, num in enumerate(_page_refs(objects), start=1):
        body = objects.get(num, b"")
        head = _dict_slice(body)
        res_m = re.search(rb"/Resources\s*(<<|\d+\s+\d+\s+R)", head)
        resources = b""
        if res_m:
            if res_m.group(1) == b"<<":
                resources = _dict_slice(head[res_m.start(1) :])
            else:
                resources = _resolve(objects, head[res_m.start(1) : res_m.end(1)])
        fonts = _build_fonts(objects, resources)

        chunks: list[bytes] = []
        cm = re.search(rb"/Contents\s*(\[.*?\]|\d+\s+\d+\s+R)", head, re.S)
        if cm:
            token = cm.group(1)
            refs = re.findall(rb"(\d+)\s+\d+\s+R", token)
            for ref in refs:
                data = _stream_bytes(objects.get(int(ref), b""))
                if data:
                    chunks.append(data)
        text, undecoded = _render_content(b"\n".join(chunks), fonts)
        doc.pages.append(PdfPage(number=index, text=text, undecoded=undecoded))
    return doc
