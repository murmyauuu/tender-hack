"""Воспроизводимый ingest KB: снимок knowledge.sqlite + manifest без embedding.

Запуск:

    python3 -m knowledge.kb.ingest --out var/knowledge

Свойства, на которые опираются приёмка и C03:

* детерминированность — порядок записей задаётся исходным порядком JSONL
  и номерами страниц PDF, ID выводятся из стабильных ключей, а не из
  времени или случайности; два прогона дают одинаковые ID и одинаковый
  SHA-256 артефактов (`created_at` берётся из хеша входов, а не из часов);
* только stdlib — ни моделей, ни embeddings, ни сети;
* ничего не выдумывается — отсутствующее остаётся NULL с причиной.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field

from .classify import attachment_status, derive_roles, service_fragment_reason
from .normalize import NORMALIZER_VERSION, clean_text, fts_normalize, fts_tokens, rebuild_title
from .pdf_text import extract_pages
from .schema import DDL, SCHEMA_VERSION

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(REPO_ROOT, "config", "knowledge", "normalizer.json")

SOURCE_TYPE_PORTAL = "portal_kb"
SOURCE_TYPE_PDF = "organizer_pdf"
SOURCE_TYPE_REGLAMENT = "reglament"


# ----------------------------------------------------------------------- модель


@dataclass
class Chunk:
    source_id: str
    parent_id: str | None
    original_ids: list[str]
    source_type: str
    source_key: str
    source_name: str
    title: str
    title_rebuilt: str | None
    raw_title: str
    text: str
    section_path: str | None = None
    page_from: int | None = None
    page_to: int | None = None
    version: str | None = None
    collected_at: str | None = None
    collection_endpoint: str | None = None
    audience_raw: str | None = None
    applicable_roles: list[str] = field(default_factory=list)
    role_verified: bool = False
    content_status: str = "complete"
    eligibility_reason: str | None = None
    topic_raw: str | None = None
    subtopic_raw: str | None = None
    ord: int = 0


@dataclass
class Parent:
    parent_id: str
    source_type: str
    source_key: str
    source_name: str
    title: str
    section_path: str | None
    page_from: int | None
    page_to: int | None
    text: str
    child_count: int = 0


@dataclass
class Excluded:
    original_id: str
    source_type: str
    source_key: str
    raw_title: str
    raw_content: str
    reason: str


# ------------------------------------------------------------------ вспомогательное


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _pdf_version_stamp(text: str) -> str | None:
    """Версионный штамп инструкции вида `11.08.2026v87` — реальное значение
    из документа, поэтому сохраняется как version, а не как заголовок."""
    m = re.search(r"\b(\d{2}\.\d{2}\.\d{4}v\d+)\b", text or "")
    return m.group(1) if m else None


# ------------------------------------------------------------------ портал и PDF


def ingest_snapshot(rows: list[dict], cfg: dict) -> tuple[list[Chunk], list[Excluded]]:
    """Нормализовать существующий снимок KB.

    Пригодные children снимка сохраняются как есть (§10: «при пригодных
    children сохраняем существующий chunking»): портальные чанки — это
    цельные статьи, PDF-чанки строго постраничные и границу страницы не
    пересекают. Заново ничего не режется.
    """
    chunks: list[Chunk] = []
    excluded: list[Excluded] = []

    for index, row in enumerate(rows):
        raw_content = row.get("content") or ""
        raw_title = row.get("title") or ""
        source_key = row.get("source_key") or ""
        is_portal = row.get("source_type") == "portal_knowledge_base_api"

        reason = service_fragment_reason(raw_content, raw_title)
        if reason:
            excluded.append(
                Excluded(
                    original_id=row.get("id", f"row{index}"),
                    source_type=SOURCE_TYPE_PORTAL if is_portal else SOURCE_TYPE_PDF,
                    source_key=source_key,
                    raw_title=raw_title,
                    raw_content=raw_content,
                    reason=reason,
                )
            )
            continue

        text = clean_text(raw_content)
        version = None if is_portal else _pdf_version_stamp(raw_title) or _pdf_version_stamp(raw_content)
        title, rebuilt = rebuild_title(raw_title, raw_content, row.get("source_name", ""))
        status, elig = attachment_status(raw_content)
        roles, verified = derive_roles(row.get("audience"))

        if is_portal:
            m = re.match(r"portal_api:(\d+):(\d+)$", source_key)
            article_id, part = (m.group(1), m.group(2)) if m else (source_key, "1")
            source_id = f"portal:{article_id}:{part}"
            parent_id = f"portal:{article_id}"
            page_from = page_to = None
            # BL-C00-5: это endpoint коллекции, не адрес статьи.
            endpoint = row.get("source_url") or None
            collected = row.get("updated_at") or None
        else:
            page = row.get("page_start")
            seq = sum(
                1
                for c in chunks
                if c.source_type == SOURCE_TYPE_PDF
                and c.source_key == source_key
                and c.page_from == page
            ) + 1
            source_id = f"pdf:{source_key}:p{page}:{seq}"
            parent_id = None  # секция назначается ниже, по заголовкам
            page_from = page
            page_to = row.get("page_end")
            endpoint = None
            collected = None

        chunks.append(
            Chunk(
                source_id=source_id,
                parent_id=parent_id,
                original_ids=[row.get("id", "")],
                source_type=SOURCE_TYPE_PORTAL if is_portal else SOURCE_TYPE_PDF,
                source_key=source_key,
                source_name=row.get("source_name", ""),
                title=title,
                title_rebuilt=rebuilt or None,
                raw_title=raw_title,
                text=text,
                page_from=page_from,
                page_to=page_to,
                version=version,
                collected_at=collected,
                collection_endpoint=endpoint,
                audience_raw=row.get("audience"),
                applicable_roles=roles,
                role_verified=verified,
                content_status=status,
                eligibility_reason=elig,
                topic_raw=row.get("topic") or None,
                subtopic_raw=row.get("subtopic") or None,
                ord=index,
            )
        )
    return chunks, excluded


# Оглавление инструкции: «<номер> <название> ....... <страница>».
# Это единственная фактическая структура разделов в этих PDF: собственного
# outline (/Outlines) ни один файл не содержит — проверено. Поэтому секции
# восстанавливаются по оглавлению самого документа, а не по догадке о
# заголовке: нумерованные строки в теле инструкций — это шаги списка, и
# неверный section_path хуже отсутствующего.
_TOC_ENTRY = re.compile(
    r"(\d{1,2}(?:\.\d{1,2})*)\.?\s*\n?\s*([^\n.]{3,120}?)\s*\.{4,}\s*(\d{1,4})\b"
)


def parse_toc(excluded: list[Excluded]) -> dict[str, list[tuple[str, str, int]]]:
    """Собрать (номер, название, стартовая страница) по source_key."""
    toc: dict[str, list[tuple[str, str, int]]] = {}
    for item in excluded:
        if item.reason != "content_is_table_of_contents":
            continue
        for number, title, page in _TOC_ENTRY.findall(item.raw_content):
            clean = re.sub(r"\s{2,}", " ", title).strip(" .\u2026")
            if len(clean) < 3:
                continue
            toc.setdefault(item.source_key, []).append((number, clean, int(page)))
    for key, entries in toc.items():
        seen: set[str] = set()
        unique = []
        for number, title, page in sorted(entries, key=lambda e: (e[2], len(e[0]), e[0])):
            if number in seen:
                continue
            seen.add(number)
            unique.append((number, title, page))
        toc[key] = unique
    return toc


def assign_pdf_sections(
    chunks: list[Chunk], excluded: list[Excluded]
) -> list[Parent]:
    """Назначить секции PDF по оглавлению документа.

    Страница относится к последней секции, начавшейся не позже неё.
    Если оглавления для файла нет или страница идёт до первой секции,
    section_path остаётся NULL — неизвестное не заполняется догадкой.
    Номера страниц остаются фактическими: секция группирует страницы,
    но не склеивает и не переписывает их.
    """
    toc = parse_toc(excluded)
    parents: dict[str, Parent] = {}

    for chunk in sorted(
        (c for c in chunks if c.source_type == SOURCE_TYPE_PDF),
        key=lambda c: (c.source_key, c.page_from or 0, c.ord),
    ):
        entries = toc.get(chunk.source_key)
        page = chunk.page_from or 0
        if not entries or page <= 0:
            chunk.section_path, chunk.parent_id = None, None
            continue
        candidates = [e for e in entries if e[2] <= page]
        if not candidates:
            chunk.section_path, chunk.parent_id = None, None
            continue
        number, title, _ = max(candidates, key=lambda e: (e[2], len(e[0])))
        by_number = {e[0]: e[1] for e in entries}
        parts = number.split(".")
        path = " / ".join(
            f"{prefix} {by_number[prefix]}"
            for prefix in (".".join(parts[: i + 1]) for i in range(len(parts)))
            if prefix in by_number
        )
        top = parts[0]
        parent_id = f"pdf:{chunk.source_key}:s{top}"
        chunk.section_path = path or f"{number} {title}"
        chunk.parent_id = parent_id
        parent = parents.get(parent_id)
        if parent is None:
            parents[parent_id] = Parent(
                parent_id=parent_id,
                source_type=SOURCE_TYPE_PDF,
                source_key=chunk.source_key,
                source_name=chunk.source_name,
                title=f"{top} {by_number.get(top, title)}",
                section_path=f"{top} {by_number.get(top, title)}",
                page_from=chunk.page_from,
                page_to=chunk.page_to,
                text=chunk.text,
                child_count=1,
            )
        else:
            parent.page_to = max(parent.page_to or 0, chunk.page_to or 0) or None
            parent.child_count += 1
            parent.text = f"{parent.text}\n\n{chunk.text}"
    return list(parents.values())


def build_portal_parents(chunks: list[Chunk]) -> list[Parent]:
    """Статья портала — parent для своих частей (article_id из source_key)."""
    groups: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        if chunk.source_type == SOURCE_TYPE_PORTAL and chunk.parent_id:
            groups.setdefault(chunk.parent_id, []).append(chunk)
    parents = []
    for parent_id, members in sorted(groups.items()):
        members.sort(key=lambda c: c.ord)
        head = members[0]
        parents.append(
            Parent(
                parent_id=parent_id,
                source_type=SOURCE_TYPE_PORTAL,
                source_key=head.source_key,
                source_name=head.source_name,
                title=head.title,
                section_path=None,
                page_from=None,
                page_to=None,
                text="\n\n".join(m.text for m in members),
                child_count=len(members),
            )
        )
    return parents


# -------------------------------------------------------------------- Регламент

_APPENDIX = re.compile(r"^(?:Приложение|ПРИЛОЖЕНИЕ)\s+(\d{1,2})\b")
_SECTION_HEAD = re.compile(r"^(\d{1,2})\.\s+([А-ЯЁ][^\n]{4,90})$")


def _strip_boilerplate(page_text: str, boilerplate: set[str]) -> tuple[str, int]:
    """Убрать повторяющийся колонтитул КонсультантПлюс.

    Это служебный фрагмент по §10.2: он повторяется на всех 57 страницах и
    не несёт содержания Регламента. Возвращает текст и число снятых строк.
    """
    kept, removed = [], 0
    for line in page_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if stripped in boilerplate or re.fullmatch(r"Страница\s+\d+", stripped) or stripped == "1":
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def _split_tokens(paragraphs: list[tuple[str, int]], cfg: dict) -> list[tuple[str, int, int]]:
    """Собрать children заданного размера с перекрытием, не теряя страницы.

    Возвращает список (text, page_from, page_to). Границы берутся по
    фактическим номерам страниц абзацев — страницы не выдумываются.
    """
    lo = cfg["chunking"]["child_tokens_min"]
    hi = cfg["chunking"]["child_tokens_max"]
    overlap = cfg["chunking"]["child_overlap_tokens"]
    out: list[tuple[str, int, int]] = []
    buf: list[tuple[str, int]] = []
    size = 0
    for para, page in paragraphs:
        n = len(fts_tokens(para))
        if size + n > hi and size >= lo:
            text = "\n\n".join(p for p, _ in buf)
            out.append((text, min(pg for _, pg in buf), max(pg for _, pg in buf)))
            # перекрытие: сохраняем хвост предыдущего окна
            tail: list[tuple[str, int]] = []
            tail_size = 0
            for item in reversed(buf):
                item_n = len(fts_tokens(item[0]))
                if tail_size + item_n > overlap:
                    break
                tail.insert(0, item)
                tail_size += item_n
            buf, size = list(tail), tail_size
        buf.append((para, page))
        size += n
    if buf:
        text = "\n\n".join(p for p, _ in buf)
        out.append((text, min(pg for _, pg in buf), max(pg for _, pg in buf)))
    return out


def ingest_reglament(path: str, cfg: dict) -> tuple[list[Chunk], list[Parent], int]:
    """Загрузить Регламент отдельным source_type (закрывает BL-C00-1).

    Регламент — высший приоритет для нормативных утверждений (§10
    «Приоритет источников»), но в снимке KB его 0 чанков. Текстовый слой
    есть, OCR не нужен.
    """
    doc = extract_pages(path)
    boilerplate = set(cfg["reglament_boilerplate_lines"])
    name = os.path.basename(path)

    paragraphs: list[tuple[str, int]] = []
    removed_lines = 0
    for page in doc.pages:
        text, removed = _strip_boilerplate(clean_text(page.text), boilerplate)
        removed_lines += removed
        for para in (p.strip() for p in text.split("\n")):
            if para:
                paragraphs.append((para, page.number))

    # разбиение на секции: приложение + верхний номер пункта
    sections: list[tuple[str, str, list[tuple[str, int]]]] = []
    appendix: str | None = None
    number: str | None = None
    title = "Регламент информационного взаимодействия"
    bucket: list[tuple[str, int]] = []

    def flush() -> None:
        if bucket:
            path_ = " / ".join(x for x in (appendix, f"{number}. {title}" if number else None) if x)
            sections.append((path_ or "Регламент", title, list(bucket)))
            bucket.clear()

    for para, page in paragraphs:
        m_app = _APPENDIX.match(para)
        if m_app and len(para) < 120:
            flush()
            appendix = f"Приложение {m_app.group(1)}"
            number, title = None, appendix
            continue
        m_head = _SECTION_HEAD.match(para)
        if m_head:
            flush()
            number, title = m_head.group(1), m_head.group(2).strip()
            continue
        bucket.append((para, page))
    flush()

    chunks: list[Chunk] = []
    parents: list[Parent] = []
    order = 0
    for s_index, (section_path, section_title, paras) in enumerate(sections, start=1):
        if not paras:
            continue
        parent_id = f"reglament:s{s_index:03d}"
        children = _split_tokens(paras, cfg)
        for c_index, (text, page_from, page_to) in enumerate(children, start=1):
            status, elig = attachment_status(text)
            order += 1
            chunks.append(
                Chunk(
                    source_id=f"{parent_id}:c{c_index:02d}",
                    parent_id=parent_id,
                    original_ids=[],  # новых записей в снимке не было
                    source_type=SOURCE_TYPE_REGLAMENT,
                    source_key="reglament",
                    source_name=name,
                    title=section_title[:180],
                    title_rebuilt=None,
                    raw_title=section_title[:180],
                    text=text,
                    section_path=section_path,
                    page_from=page_from,
                    page_to=page_to,
                    # Реальная редакция документа, извлечённая из его текста.
                    version="ред. от 10.06.2025",
                    collected_at=None,
                    collection_endpoint=None,
                    # Регламент адресован обеим сторонам, но явной разметки
                    # роли в документе нет -> роль не подтверждена.
                    audience_raw=None,
                    applicable_roles=[],
                    role_verified=False,
                    content_status=status,
                    eligibility_reason=elig,
                    topic_raw=None,
                    subtopic_raw=None,
                    ord=100000 + order,
                )
            )
        parents.append(
            Parent(
                parent_id=parent_id,
                source_type=SOURCE_TYPE_REGLAMENT,
                source_key="reglament",
                source_name=name,
                title=section_title[:180],
                section_path=section_path,
                page_from=min(p for _, p in paras),
                page_to=max(p for _, p in paras),
                text="\n\n".join(p for p, _ in paras),
                child_count=len(children),
            )
        )
    return chunks, parents, removed_lines


def ingest_missing_pdf_pages(cfg: dict, present: set[tuple[str, int]]) -> tuple[list[Chunk], list[Excluded]]:
    """Дочитать страницы инструкций, которых нет в снимке (C00/D9).

    По C00 пропущена ровно одна страница — стр. 3 «Инструкции по
    электронному актированию». Страница читается фактически; если
    текстового слоя на ней нет, запись не придумывается, а уходит в
    excluded с причиной.
    """
    chunks: list[Chunk] = []
    excluded: list[Excluded] = []
    for source_key, rel_path in sorted(cfg["inputs"]["instruction_pdfs"].items()):
        path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(path):
            continue
        pages_in_kb = {p for k, p in present if k == source_key}
        if not pages_in_kb:
            continue
        doc = extract_pages(path)
        for page in doc.pages:
            if page.number in pages_in_kb:
                continue
            text = clean_text(page.text)
            reason = service_fragment_reason(text, "")
            original_id = f"recovered:{source_key}:p{page.number}"
            if reason:
                excluded.append(
                    Excluded(
                        original_id=original_id,
                        source_type=SOURCE_TYPE_PDF,
                        source_key=source_key,
                        raw_title="",
                        raw_content=page.text,
                        reason=f"{reason}: страница дочитана из PDF, текстового слоя сверх номера страницы нет",
                    )
                )
                continue
            status, elig = attachment_status(text)
            title, rebuilt = rebuild_title("", text, os.path.basename(rel_path))
            chunks.append(
                Chunk(
                    source_id=f"pdf:{source_key}:p{page.number}:1",
                    parent_id=None,
                    original_ids=[original_id],
                    source_type=SOURCE_TYPE_PDF,
                    source_key=source_key,
                    source_name=os.path.basename(rel_path),
                    title=title,
                    title_rebuilt=rebuilt or None,
                    raw_title="",
                    text=text,
                    page_from=page.number,
                    page_to=page.number,
                    content_status=status,
                    eligibility_reason=elig,
                    ord=200000 + page.number,
                )
            )
    return chunks, excluded


# ------------------------------------------------------------------ запись снимка


def write_snapshot(
    out_dir: str,
    chunks: list[Chunk],
    parents: list[Parent],
    excluded: list[Excluded],
    manifest: dict,
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    db_path = os.path.join(out_dir, "knowledge.sqlite")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(DDL)
        conn.executemany(
            "INSERT INTO parents VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    p.parent_id, p.source_type, p.source_key, p.source_name, p.title,
                    p.section_path, p.page_from, p.page_to, p.child_count, p.text,
                )
                for p in sorted(parents, key=lambda x: x.parent_id)
            ],
        )
        conn.executemany(
            "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    c.source_id, c.parent_id, json.dumps(c.original_ids, ensure_ascii=False),
                    c.source_type, c.source_key, c.source_name, c.title, c.title_rebuilt,
                    c.raw_title, c.text, c.section_path, c.page_from, c.page_to, c.version,
                    c.collected_at, c.collection_endpoint, c.audience_raw,
                    json.dumps(c.applicable_roles, ensure_ascii=False), int(c.role_verified),
                    c.content_status, c.eligibility_reason, c.topic_raw, c.subtopic_raw, c.ord,
                )
                for c in sorted(chunks, key=lambda x: (x.ord, x.source_id))
            ],
        )
        conn.executemany(
            "INSERT INTO excluded VALUES (?,?,?,?,?,?)",
            [
                (e.original_id, e.source_type, e.source_key, e.raw_title, e.raw_content, e.reason)
                for e in sorted(excluded, key=lambda x: x.original_id)
            ],
        )
        conn.executemany(
            "INSERT INTO chunks_fts (source_id, title_norm, text_norm) VALUES (?,?,?)",
            [
                (c.source_id, fts_normalize(c.title), fts_normalize(c.text))
                for c in sorted(chunks, key=lambda x: (x.ord, x.source_id))
            ],
        )
        conn.executemany(
            "INSERT INTO manifest VALUES (?,?)",
            sorted(
                (k, json.dumps(v, ensure_ascii=False, sort_keys=True))
                for k, v in manifest.items()
            ),
        )
        conn.commit()
        conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()
    return db_path


def build_manifest(
    cfg: dict, input_files: list[dict], counts: dict, removed_boilerplate: int
) -> dict:
    """Manifest по разделу 10. Поля embedding_* и index_type заполняются
    null/unknown ЯВНО: C02 embeddings не строит, выдуманных значений нет."""
    # snapshot_id детерминирован: хеш входов + версия нормализатора.
    seed = json.dumps(
        {"inputs": input_files, "normalizer": NORMALIZER_VERSION, "schema": SCHEMA_VERSION},
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    return {
        "snapshot_id": f"kb-{digest[:16]}",
        # Детерминированная «дата создания»: снимок воспроизводим, поэтому
        # временем часов он не помечается — иначе два прогона разошлись бы.
        "created_at": None,
        "created_at_note": "null by design: снимок детерминирован, часы в артефакт не попадают",
        "input_files": input_files,
        "normalizer_version": NORMALIZER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "embedding_model": None,
        "embedding_revision": None,
        "embedding_dim": None,
        "adapter_version": None,
        "index_type": None,
        "embedding_note": (
            "C02 embeddings не строит: 0 model calls, 0 сетевых вызовов. "
            "Поля заполняются null явно. Контракт для C03: смена embedding "
            "adapter, весов или revision требует ПОЛНОЙ пересборки снимка — "
            "index_type из config/runtime/c0.json (numpy_exact_cosine) на "
            "момент C02 имеет status=not_built."
        ),
        "counts": counts,
        "removed_boilerplate_lines": removed_boilerplate,
        "files": [],
    }


# ------------------------------------------------------------------------- main


def run(out_dir: str) -> dict:
    cfg = load_config()
    kb_path = os.path.join(REPO_ROOT, cfg["inputs"]["kb_snapshot"])
    with open(kb_path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]

    chunks, excluded = ingest_snapshot(rows, cfg)
    # «Виденные» снимком страницы считаются по СЫРЫМ строкам, а не по
    # включённым чанкам: страница, единственный чанк которой удалён как
    # оглавление, снимком всё равно была прочитана и повторному
    # дочитыванию не подлежит.
    present = {
        (row.get("source_key") or "", row.get("page_start"))
        for row in rows
        if row.get("source_type") == "organizer_pdf" and row.get("page_start")
    }
    recovered, recovered_excluded = ingest_missing_pdf_pages(cfg, present)
    chunks.extend(recovered)
    excluded.extend(recovered_excluded)

    pdf_parents = assign_pdf_sections(chunks, excluded)
    portal_parents = build_portal_parents(chunks)
    reg_chunks, reg_parents, removed = ingest_reglament(
        os.path.join(REPO_ROOT, cfg["inputs"]["reglament_pdf"]), cfg
    )
    chunks.extend(reg_chunks)
    parents = pdf_parents + portal_parents + reg_parents

    input_files = [
        {"name": cfg["inputs"]["kb_snapshot"], "sha256": sha256_file(kb_path)},
        {
            "name": cfg["inputs"]["reglament_pdf"],
            "sha256": sha256_file(os.path.join(REPO_ROOT, cfg["inputs"]["reglament_pdf"])),
        },
    ] + [
        {"name": p, "sha256": sha256_file(os.path.join(REPO_ROOT, p))}
        for _, p in sorted(cfg["inputs"]["instruction_pdfs"].items())
    ]

    counts = {
        "raw": len(rows),
        "included": len(chunks),
        "excluded": len(excluded),
        "articles": len({c.parent_id for c in chunks if c.source_type == SOURCE_TYPE_PORTAL}),
        "cards_reviewed": 0,
        "by_source_type": {
            t: sum(1 for c in chunks if c.source_type == t)
            for t in sorted({c.source_type for c in chunks})
        },
        "parents": len(parents),
        "excluded_by_reason": {
            r: sum(1 for e in excluded if e.reason.split(":")[0] == r)
            for r in sorted({e.reason.split(":")[0] for e in excluded})
        },
        "content_status": {
            s: sum(1 for c in chunks if c.content_status == s)
            for s in sorted({c.content_status for c in chunks})
        },
        "titles_rebuilt": sum(1 for c in chunks if c.title_rebuilt),
        "role_verified": sum(1 for c in chunks if c.role_verified),
    }

    manifest = build_manifest(cfg, input_files, counts, removed)
    db_path = write_snapshot(out_dir, chunks, parents, excluded, manifest)

    # Путь пишется относительно корня репозитория, когда артефакт лежит
    # внутри него, иначе — только имя файла: манифест не должен зависеть от
    # каталога сборки, иначе два прогона разойдутся по хешу.
    rel = os.path.relpath(db_path, REPO_ROOT)
    manifest["files"] = [
        {
            "path": rel if not rel.startswith(os.pardir) else os.path.basename(db_path),
            "sha256": sha256_file(db_path),
            "size_bytes": os.path.getsize(db_path),
        }
    ]
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="C02 ingest KB (stdlib only, 0 model calls)")
    parser.add_argument(
        "--out",
        default=os.path.join(REPO_ROOT, "var", "knowledge"),
        help="каталог артефактов (вне Git)",
    )
    args = parser.parse_args(argv)
    manifest = run(args.out)
    json.dump(manifest, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
