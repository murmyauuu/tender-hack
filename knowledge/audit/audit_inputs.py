#!/usr/bin/env python3
"""C00 — аудит реальных входов KB. Только чтение, только stdlib.

Ничего не скачивает, ничего не меняет в raw-входах, не строит индекс.
Запуск из корня репозитория:

    python3 knowledge/audit/audit_inputs.py > knowledge/audit/c00_inventory.json

Всё, что не удалось измерить фактически, остаётся null/"unknown".
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import statistics
import sys
import zipfile
import zlib
from xml.etree import ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB_JSONL = "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl"
API_REPORT = "TenderHack_KnowledgeBase/api_report.json"
HISTORY_XLSX = "НН 2026/Выгрузка СТП за 2026.xlsx"
TAXONOMY_XLSX = "НН 2026/Темы_подтемы_обращений.xlsx"
REGLAMENT_PDF = "Регламент_информационного_взаимодействия-4.pdf"
INSTRUCTION_PDFS = [
    "НН 2026/Инструкция по работе с Порталом для поставщика.pdf",
    "НН 2026/Инструкция по работе с Порталом для заказчика.pdf",
    "НН 2026/Инструкция по созданию оферты и СТЕ.pdf",
    "НН 2026/Инструкция по электронному актированию.pdf",
    "НН 2026/Инструкция по формированию YML.pdf",
    "НН 2026/Инструкция по работе с машиночитаемыми доверенностями.pdf",
]
# source_key организатора -> имя PDF, по фактическому source_name в KB
PDF_SOURCE_KEYS = {
    "supplier_instruction": "НН 2026/Инструкция по работе с Порталом для поставщика.pdf",
    "customer_instruction": "НН 2026/Инструкция по работе с Порталом для заказчика.pdf",
    "offer_ste": "НН 2026/Инструкция по созданию оферты и СТЕ.pdf",
    "electronic_acceptance": "НН 2026/Инструкция по электронному актированию.pdf",
    "yml": "НН 2026/Инструкция по формированию YML.pdf",
    "mchd": "НН 2026/Инструкция по работе с машиночитаемыми доверенностями.pdf",
}

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def rel(path: str) -> str:
    return os.path.join(REPO, path)


def sha256(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_facts(path: str) -> dict:
    full = rel(path)
    exists = os.path.exists(full)
    return {
        "path": path,
        "exists": exists,
        "size_bytes": os.path.getsize(full) if exists else None,
        "sha256": sha256(full),
    }


# --------------------------------------------------------------------------- KB


def load_kb() -> list[dict]:
    rows, bad = [], 0
    with open(rel(KB_JSONL), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"warning: {bad} unparsable JSONL lines", file=sys.stderr)
    return rows


def audit_kb(rows: list[dict]) -> dict:
    portal = [r for r in rows if r["source_type"] == "portal_knowledge_base_api"]
    pdf = [r for r in rows if r["source_type"] == "organizer_pdf"]

    article_ids = collections.Counter()
    for r in portal:
        m = re.match(r"portal_api:(\d+):(\d+)$", r["source_key"])
        if m:
            article_ids[m.group(1)] += 1

    def empties(field: str) -> int:
        return sum(1 for r in rows if r.get(field) in (None, "", "null"))

    def lengths(subset: list[dict]) -> dict:
        L = [len(r["content"]) for r in subset]
        return {
            "n": len(subset),
            "chars_min": min(L),
            "chars_median": int(statistics.median(L)),
            "chars_max": max(L),
            "chars_mean": int(statistics.mean(L)),
            "under_200_chars": sum(1 for x in L if x < 200),
            "under_100_chars": sum(1 for x in L if x < 100),
        }

    # классы дефектов
    defects = collections.Counter()
    for r in rows:
        content, title = r["content"].strip(), r["title"]
        if re.fullmatch(r"\d{1,4}", content):
            defects["content_is_page_number_only"] += 1
        if len(content) < 40:
            defects["content_under_40_chars"] += 1
        if re.search(r"\.{5,}\s*\d+", title) or re.search(r"\.{5,}\s*\d+", content):
            defects["toc_dot_leader"] += 1
        if title.strip().lower() in ("содержание", "оглавление"):
            defects["toc_heading"] += 1
        if re.search(r"\.(pdf|docx?|xlsx?)$", title.strip(), re.I):
            defects["title_is_filename"] += 1
        if re.search(r"(Рисунок|Рис\.)\s*\d+", content):
            defects["references_figure_not_in_kb"] += 1
        if re.search(r"(Приложени[ея]|см\.\s|смотри)", content):
            defects["pointer_or_attachment_mention"] += 1

    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    by_content = collections.defaultdict(int)
    for r in rows:
        by_content[hashlib.sha1(norm(r["content"]).encode()).hexdigest()] += 1

    # покрытие страниц PDF
    pages_in_kb = collections.defaultdict(set)
    for r in pdf:
        pages_in_kb[r["source_key"]].add(r["page_start"])

    return {
        "rows_total": len(rows),
        "by_source_type": dict(collections.Counter(r["source_type"] for r in rows)),
        "id_unique": len(set(r["id"] for r in rows)),
        "source_key_unique": len(set(r["source_key"] for r in rows)),
        "portal_unique_article_ids": len(article_ids),
        "portal_chunks_per_article": dict(
            sorted(collections.Counter(article_ids.values()).items())
        ),
        "empty_field_counts": {k: empties(k) for k in rows[0].keys()},
        "audience_values": dict(collections.Counter(r["audience"] for r in rows)),
        "topic_distinct": len(set(r["topic"] for r in rows)),
        "subtopic_distinct_portal": len(set(r["subtopic"] for r in portal)),
        "source_url_distinct": dict(collections.Counter(r["source_url"] for r in portal)),
        "updated_at_distinct_portal": dict(
            collections.Counter(r["updated_at"] for r in portal)
        ),
        "length_stats": {"organizer_pdf": lengths(pdf), "portal": lengths(portal)},
        "defect_counts": dict(defects.most_common()),
        "exact_duplicate_content_groups": sum(1 for v in by_content.values() if v > 1),
        "chunk_spans_multiple_pages": sum(
            1 for r in pdf if r["page_start"] != r["page_end"]
        ),
        "pdf_pages_present_in_kb": {k: len(v) for k, v in sorted(pages_in_kb.items())},
    }


# -------------------------------------------------------------------------- PDF


def probe_pdf(path: str) -> dict:
    full = rel(path)
    if not os.path.exists(full):
        return {"path": path, "exists": False}
    blob = open(full, "rb").read()
    m = re.search(rb"%PDF-(\d\.\d)", blob[:1024])
    counts = [
        int(x)
        for x in re.findall(rb"/Type\s*/Pages\b[^>]{0,400}?/Count\s+(\d+)", blob, re.S)
    ] + [
        int(x)
        for x in re.findall(rb"/Count\s+(\d+)[^>]{0,400}?/Type\s*/Pages\b", blob, re.S)
    ]
    page_objs = len(re.findall(rb"/Type\s*/Page[^s]", blob))
    text_ops, decoded = 0, 0
    for m2 in re.finditer(rb"stream\r?\n", blob):
        start = m2.end()
        end = blob.find(b"endstream", start)
        if end < 0:
            continue
        try:
            data = zlib.decompress(blob[start:end])
        except zlib.error:
            continue
        decoded += 1
        text_ops += len(re.findall(rb"\bT[Jj]\b", data))
        if decoded > 400:
            break
    return {
        "path": path,
        "exists": True,
        "size_bytes": len(blob),
        "sha256": sha256(full),
        "pdf_version": m.group(1).decode() if m else None,
        "encrypted": bool(re.search(rb"/Encrypt\b", blob)),
        "pages": max(counts) if counts else page_objs or None,
        "page_objects": page_objs,
        "embedded_images": len(re.findall(rb"/Subtype\s*/Image", blob)),
        "text_operators_sampled": text_ops,
        "has_text_layer": text_ops > 0,
    }


# ------------------------------------------------------------------------- XLSX


def read_sheet(path: str, sheet: str = "xl/worksheets/sheet1.xml", limit: int | None = None):
    z = zipfile.ZipFile(rel(path))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
    rows = []
    for _, el in ET.iterparse(z.open(sheet), events=("end",)):
        if el.tag != NS + "row":
            continue
        cells = {}
        for c in el.iter(NS + "c"):
            col = re.match(r"([A-Z]+)", c.get("r")).group(1)
            t, v, inline = c.get("t"), c.find(NS + "v"), c.find(NS + "is")
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr" and inline is not None:
                val = "".join(x.text or "" for x in inline.iter(NS + "t"))
            else:
                val = v.text if v is not None else None
            cells[col] = val
        rows.append(cells)
        el.clear()
        if limit and len(rows) >= limit:
            break
    return rows


def audit_taxonomy() -> dict:
    rows = read_sheet(TAXONOMY_XLSX)
    themes, current, pairs = {}, None, 0
    for row in rows[3:]:
        theme, sub = row.get("B"), row.get("C")
        if theme:
            current = theme.strip()
        if sub and sub.strip():
            themes.setdefault(current, []).append(sub.strip())
            pairs += 1
    return {
        "rows_total": len(rows),
        "header_row_index": 3,
        "columns": ["№", "Тема обращений", "Подтема обращений"],
        "themes": len(themes),
        "subtopic_rows": pairs,
        "subtopics_distinct": len(set(s for v in themes.values() for s in v)),
        "theme_to_subtopic_count": {k: len(v) for k, v in themes.items()},
        "has_support_line_column": False,
        "has_addressee_column": False,
    }


def audit_history() -> dict:
    rows = read_sheet(HISTORY_XLSX)
    header, data = rows[0], rows[1:]
    subtopic_re = re.compile(r"^Подтема запроса:\s*([^/]+)/", re.S)
    subtopics, matched = collections.Counter(), 0
    for r in data:
        m = subtopic_re.match((r.get("E") or "").strip())
        if m:
            subtopics[m.group(1).strip()] += 1
            matched += 1
    blob = [(r.get("E") or "") + " " + (r.get("F") or "") for r in data]
    pii = {
        "email": r"[\w.\-]+@[\w\-]+\.[a-zA-Z]{2,}",
        "phone": r"(?:\+7|8)[\s\-(]?\d{3}[\s\-)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}",
        "inn_labelled": r"\bИНН[\s:]*\d{10,12}\b",
        "guid": r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    }
    return {
        "columns": [header[k] for k in sorted(header)],
        "rows_data": len(data),
        "status_values": dict(collections.Counter(r.get("D") for r in data)),
        "impact_values": dict(collections.Counter(r.get("A") for r in data)),
        "theme_distinct": len(set(r.get("C") for r in data)),
        "description_empty": sum(1 for r in data if not (r.get("E") or "").strip()),
        "resolution_empty": sum(1 for r in data if not (r.get("F") or "").strip()),
        "unique_description_resolution_pairs": len(
            set((r.get("E"), r.get("F")) for r in data)
        ),
        "subtopic_prefix_matched_rows": matched,
        "subtopic_prefix_unmatched_rows": len(data) - matched,
        "subtopics_distinct_in_history": len(subtopics),
        "pii_row_counts": {
            k: sum(1 for b in blob if re.search(p, b, re.I)) for k, p in pii.items()
        },
    }


def crosswalk(tax: dict, hist_subtopics: set[str]) -> dict:
    rows = read_sheet(TAXONOMY_XLSX)
    themes, subs, current = set(), set(), None
    for row in rows[3:]:
        if row.get("B"):
            current = row["B"].strip()
            themes.add(current)
        if row.get("C") and row["C"].strip():
            subs.add(row["C"].strip())
    hrows = read_sheet(HISTORY_XLSX)[1:]
    theme_counts = collections.Counter((r.get("C") or "").strip() for r in hrows)
    matched = {t: c for t, c in theme_counts.items() if t in themes}
    return {
        "taxonomy_themes": len(themes),
        "history_theme_values_distinct": len(theme_counts),
        "history_themes_matching_taxonomy": len(matched),
        "history_rows_covered_by_taxonomy_themes": sum(matched.values()),
        "history_rows_outside_taxonomy_themes": len(hrows) - sum(matched.values()),
        "subtopics_in_history_not_in_taxonomy": sorted(hist_subtopics - subs),
        "subtopics_in_taxonomy_not_in_history": sorted(subs - hist_subtopics),
    }


def main() -> None:
    rows = load_kb()
    hist_rows = read_sheet(HISTORY_XLSX)[1:]
    subtopic_re = re.compile(r"^Подтема запроса:\s*([^/]+)/", re.S)
    hist_subtopics = set()
    for r in hist_rows:
        m = subtopic_re.match((r.get("E") or "").strip())
        if m:
            hist_subtopics.add(m.group(1).strip())

    tax = audit_taxonomy()
    report = {
        "task_id": "C00",
        "generated_by": "knowledge/audit/audit_inputs.py",
        "repo_relative_paths": True,
        "files": {
            "kb_jsonl": file_facts(KB_JSONL),
            "kb_api_report": file_facts(API_REPORT),
            "kb_summary": file_facts("TenderHack_KnowledgeBase/TenderHack_KnowledgeBase_summary.txt"),
            "history_xlsx": file_facts(HISTORY_XLSX),
            "taxonomy_xlsx": file_facts(TAXONOMY_XLSX),
            "reglament_pdf": file_facts(REGLAMENT_PDF),
            "instruction_pdfs": [file_facts(p) for p in INSTRUCTION_PDFS],
        },
        "kb": audit_kb(rows),
        "api_report_claims": json.load(open(rel(API_REPORT), encoding="utf-8")),
        "pdf_probe": {
            "reglament": probe_pdf(REGLAMENT_PDF),
            "instructions": [probe_pdf(p) for p in INSTRUCTION_PDFS],
        },
        "taxonomy": tax,
        "history": audit_history(),
        "crosswalk": crosswalk(tax, hist_subtopics),
    }

    # покрытие страниц PDF: факт vs KB
    cov = {}
    for key, pdf_path in PDF_SOURCE_KEYS.items():
        probe = probe_pdf(pdf_path)
        in_kb = report["kb"]["pdf_pages_present_in_kb"].get(key, 0)
        total = probe.get("pages")
        cov[key] = {
            "pdf": pdf_path,
            "pdf_pages": total,
            "pages_present_in_kb": in_kb,
            "pages_missing": (total - in_kb) if total else None,
        }
    report["pdf_page_coverage"] = cov
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
