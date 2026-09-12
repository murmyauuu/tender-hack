#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D01: build evaluation/history/pairs_manifest.json from the real raw export.

Read-only over data/raw inputs. No text of the pairs is written to the repo:
only hashes, row references and sanitized topic/subtopic raw labels.

Dependencies: pandas, openpyxl (read-only usage).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HISTORY_XLSX = ROOT / "НН 2026" / "Выгрузка СТП за 2026.xlsx"
TAXONOMY_XLSX = ROOT / "НН 2026" / "Темы_подтемы_обращений.xlsx"
OUT_MANIFEST = ROOT / "evaluation" / "history" / "pairs_manifest.json"
OUT_PICK_REPORT = ROOT / "evaluation" / "history" / "pairs_selection_report.json"

HISTORY_SHA = "8159199e23214439ba26554d821c7c37b087f3188bc02949d989e8fbc63d83c9"
TAXONOMY_SHA = "f5649e083b5f0c13cf346e26387064aca2c33edb9c9e7ceee1c3cc4641f5d05a"

# Training examples from D00 (must NOT be in final 30 / reserve), 0-based row indices.
TRN_ROWS = {0, 4452, 2677, 11957, 12574, 24029, 17047, 22653}

PREFIX_RE = re.compile(r"^\s*Подтема запроса:\s*(.*?)\s*/\s*(.*)$", re.S)

DIGITS_INN = re.compile(r"(?i)(ИНН|ИНС|ИПП|КПП|ОГРН|ОКПО|ГИД|УИД|нюм)\s*[:=#]?\s*\d[\d\s\-]{5,}")
GUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\d)(?:\+7|8|7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)")
CONTRACT_NUM = re.compile(r"(?i)(№|номер|id|идентификатор)\s*\d{5,}")
UUID_HEX = re.compile(r"\b[0-9a-fA-F]{16,}\b")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s


def clean_desc(s: str) -> str:
    """Remove the 'Подтема запроса: <sub>/' prefix; keep the question text."""
    m = PREFIX_RE.match(str(s))
    if m:
        return norm(m.group(2))
    return norm(s)


def strip_pii(s: str) -> str:
    s = EMAIL.sub("<email>", s)
    s = PHONE.sub("<phone>", s)
    s = GUID.sub("<guid>", s)
    s = UUID_HEX.sub("<hex>", s)
    s = DIGITS_INN.sub(r"\1 <num>", s)
    return s


def de_pii_label(label: str) -> str:
    """Sanitize topic/subtopic raw labels to keep only non-sensitive wording."""
    label = strip_pii(str(label)).strip()
    label = re.sub(r"\s+", " ", label)
    return label[:120]


def main() -> None:
    df = pd.read_excel(HISTORY_XLSX)
    df.columns = [str(c) for c in df.columns]
    n_rows = len(df)

    extracted = df["Описание"].str.extract(PREFIX_RE)
    subtopic_series = extracted[0].fillna("").str.strip()
    question_series = extracted[1].fillna(df["Описание"]).map(clean_desc)
    resolution_series = df["Решение"].map(norm)

    validity = (question_series.str.len() >= 25) & (resolution_series.str.len() >= 40)

    recs = []
    for idx in range(n_rows):
        recs.append(
            {
                "row_index": int(idx),
                "topic_raw": de_pii_label(df.at[idx, "Тема"]),
                "subtopic_raw": de_pii_label(subtopic_series[idx]),
                "q": question_series[idx],
                "r": resolution_series[idx],
                "valid": bool(validity[idx]),
            }
        )

    # exact dedup on (q, r)
    seen_exact: set[tuple[str, str]] = set()
    dedup = []
    for rec in recs:
        key = (rec["q"], rec["r"])
        if key in seen_exact:
            continue
        seen_exact.add(key)
        dedup.append(rec)

    # near dedup on normalized question (same scenario paraphrases), keep longest resolution
    normq: dict[str, list] = {}
    for rec in dedup:
        nq = re.sub(r"[^\w\s]", "", rec["q"].lower())
        nq = re.sub(r"\s+", " ", nq).strip()
        normq.setdefault(nq, []).append(rec)
    grouped = []
    for nq, group in normq.items():
        group.sort(key=lambda r: len(r["r"]), reverse=True)
        grouped.append(group)

    eligible = [g[0] for g in grouped]
    eligible = [r for r in eligible if r["valid"]]
    eligible_rows = {r["row_index"] for r in eligible} - TRN_ROWS
    candidates = [r for r in eligible if r["row_index"] in eligible_rows]

    # stratified candidates by subtopic_raw (empty subtopic -> 'NO_SUBTOPIC')
    def subkey(r):
        return r["subtopic_raw"] or "NO_SUBTOPIC"

    from collections import Counter, defaultdict

    by_sub: dict[str, list] = defaultdict(list)
    for r in candidates:
        by_sub[subkey(r)].append(r)
    sub_counts = Counter({k: len(v) for k, v in by_sub.items()})

    # deterministic pool ordering: subtopic frequency desc, then row_index asc
    pool = []
    for k in sorted(by_sub, key=lambda k: (-len(by_sub[k]), k)):
        for r in sorted(by_sub[k], key=lambda r: r["row_index"]):
            pool.append((k, r))

    # Manual curated list of the 30 selected pair_ids with row_index (single source of truth for B04/D03).
    # Rows are 0-based indices into the raw xlsx data rows (after the header row).
    # Near-duplicate rows (same norm-group) appear only once; TRN rows excluded.
    selected_rows = [
        ("HIST-0001", 80),
        ("HIST-0002", 83),
        ("HIST-0003", 149),
        ("HIST-0004", 15),
        ("HIST-0005", 25),
        ("HIST-0006", 147),
        ("HIST-0007", 70),
        ("HIST-0008", 93),
        ("HIST-0009", 122),
        ("HIST-0010", 47),
        ("HIST-0011", 39),
        ("HIST-0012", 3),
        ("HIST-0013", 4),
        ("HIST-0014", 59),
        ("HIST-0015", 65),
        ("HIST-0016", 67),
        ("HIST-0017", 121),
        ("HIST-0018", 48),
        ("HIST-0019", 76),
        ("HIST-0020", 63),
        ("HIST-0021", 557),
        ("HIST-0022", 317),
        ("HIST-0023", 196),
        ("HIST-0024", 721),
        ("HIST-0025", 885),
        ("HIST-0026", 1148),
        ("HIST-0027", 107),
        ("HIST-0028", 17),
        ("HIST-0029", 143),
        ("HIST-0030", 556),
    ]
    reserve_rows = [
        ("HIST-R01", 64),
        ("HIST-R02", 268),
        ("HIST-R03", 138),
        ("HIST-R04", 341),
        ("HIST-R05", 137),
        ("HIST-R06", 150),
        ("HIST-R07", 236),
        ("HIST-R08", 544),
        ("HIST-R09", 230),
        ("HIST-R10", 273),
    ]

    by_row = {r["row_index"]: r for r in recs}
    manifest = {
        "schema": "tenderhack.history_pairs_manifest/v1",
        "source_file": "НН 2026/Выгрузка СТП за 2026.xlsx",
        "source_sha256": HISTORY_SHA,
        "taxonomy_file": "НН 2026/Темы_подтемы_обращений.xlsx",
        "taxonomy_sha256": TAXONOMY_SHA,
        "rows_total": n_rows,
        "exclude_training_examples_rows": sorted(TRN_ROWS),
        "notes": (
            "Пара — реальная строка выгрузки: Описание (вопрос) -> Решение (фактический ответ оператора). "
            "Решение не является trusted gold само по себе; оценка по рубрике D00/D01. "
            "Отбор: валидность (Описание>=25, Решение>=40 после очистки), дедуп точных и близких пар, "
            "стратификация по подтемам, исключены учебные примеры D00 (TRN rows)."
        ),
        "pairs": [],
    }
    for pair_id, row_idx in selected_rows + reserve_rows:
        r = by_row.get(row_idx)
        if r is None:
            raise SystemExit(f"row_index {row_idx} not found")
        manifest["pairs"].append(
            {
                "pair_id": pair_id,
                "row_index": row_idx,
                "content_hashes": {
                    "sha256_description": sha256_hex(r["q"].encode("utf-8")),
                    "sha256_resolution": sha256_hex(r["r"].encode("utf-8")),
                },
                "topic_raw": r["topic_raw"],
                "subtopic_raw": r["subtopic_raw"],
                "pair_status": "selected" if pair_id.startswith("HIST-") and not pair_id.startswith("HIST-R") else "reserve",
                "notes_null": [],
            }
        )

    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # deterministic report (no text, only stats/pool positions)
    report = {
        "rows_total": n_rows,
        "valid_rows": int(validity.sum()),
        "exact_dup_removed": n_rows - len(dedup),
        "near_dup_groups_kept": len(grouped),
        "groups_after_valid_clean_no_trn": len(candidates),
        "subtopic_counts_top": sub_counts.most_common(15),
        "selected_n": len(selected_rows),
        "reserve_n": len(reserve_rows),
        "selected_rows": [i for _, i in selected_rows],
        "reserve_rows": [i for _, i in reserve_rows],
        "selected_subtopics_distinct": len({by_row[i]["subtopic_raw"] for _, i in selected_rows}),
        "selected_subtopics": sorted(
            {by_row[i]["subtopic_raw"] or "NO_SUBTOPIC" for _, i in selected_rows}
        ),
    }
    OUT_PICK_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()