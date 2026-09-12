"""Сборка канонического справочника taxonomy (тема/подтема) из реального
входа `НН 2026/Темы_подтемы_обращений.xlsx` (C04, §10 «Routing»: «Taxonomy
из реального справочника, 9/86 не выдумываются»).

Файл — Office Open XML (zip + XML), читается через stdlib `zipfile` и
`xml.etree.ElementTree`, без openpyxl/pandas — та же линия, что и остальной
`knowledge/kb/**` (только stdlib, файл лежит в `knowledge/kb/` и подпадает
под сканирование `test_no_model_calls.py`).

Тема указана только в первой строке своего блока (визуально объединённые
ячейки в исходном файле) — вперёд-заполнение (`current_theme`) обязательно,
иначе часть строк потеряет тему.

`theme_id`/`subtopic_id` — не из внешнего справочника (справочника линий/
адресатов не существует, BL-C00-2), а стабильная нумерация самого этого
файла: `theme_id` — порядковый номер темы по первому появлению (TH1..TH9),
`subtopic_id` — колонка «№» источника (ST01..ST86), т.е. буквально номер
строки исходной таблицы, не изобретённое значение.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

__all__ = ["TaxonomyRow", "build_taxonomy", "load_taxonomy", "TAXONOMY_JSON_PATH"]

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_XLSX = _REPO_ROOT / "НН 2026" / "Темы_подтемы_обращений.xlsx"
TAXONOMY_JSON_PATH = _REPO_ROOT / "config" / "knowledge" / "taxonomy.json"


@dataclass(frozen=True)
class TaxonomyRow:
    row_no: int
    theme_id: str
    theme: str
    subtopic_id: str
    subtopic: str


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in tree.findall("m:si", _NS):
        out.append("".join(t.text or "" for t in si.findall(".//m:t", _NS)))
    return out


def _cell_value(cell: ET.Element, shared: list[str]) -> str | None:
    v = cell.find("m:v", _NS)
    if v is None or v.text is None:
        return None
    if cell.get("t") == "s":
        return shared[int(v.text)]
    return v.text


def build_taxonomy(source_xlsx: Path = _SOURCE_XLSX) -> list[TaxonomyRow]:
    """Разобрать реальный xlsx. Ничего не выдумывает: строки без подтемы или
    без действующей темы пропускаются, названия берутся дословно (после
    strip пробелов по краям — в исходнике встречаются ведущие пробелы,
    например ` Регистрация`)."""
    z = zipfile.ZipFile(source_xlsx)
    shared = _shared_strings(z)
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows_xml = sheet.findall(".//m:sheetData/m:row", _NS)

    theme_ids: dict[str, str] = {}
    result: list[TaxonomyRow] = []
    current_theme: str | None = None

    for row in rows_xml:
        cells = {c.get("r")[0]: _cell_value(c, shared) for c in row.findall("m:c", _NS) if c.get("r")}
        num_raw = cells.get("A")
        theme_raw = cells.get("B")
        subtopic_raw = cells.get("C")
        if num_raw is None and theme_raw is None and subtopic_raw is None:
            continue
        if theme_raw and theme_raw.strip():
            current_theme = theme_raw.strip()
        if subtopic_raw is None or not subtopic_raw.strip():
            continue
        if current_theme is None:
            continue
        try:
            row_no = int(num_raw)
        except (TypeError, ValueError):
            continue
        if current_theme not in theme_ids:
            theme_ids[current_theme] = f"TH{len(theme_ids) + 1}"
        result.append(
            TaxonomyRow(
                row_no=row_no,
                theme_id=theme_ids[current_theme],
                theme=current_theme,
                subtopic_id=f"ST{row_no:02d}",
                subtopic=subtopic_raw.strip(),
            )
        )
    return result


def write_taxonomy_json(rows: list[TaxonomyRow], source_xlsx: Path = _SOURCE_XLSX,
                         out_path: Path = TAXONOMY_JSON_PATH) -> dict:
    sha256 = hashlib.sha256(source_xlsx.read_bytes()).hexdigest()
    themes = sorted({r.theme for r in rows})
    subtopics = sorted({r.subtopic for r in rows})
    doc = {
        "source_file": "НН 2026/Темы_подтемы_обращений.xlsx",
        "source_sha256": sha256,
        "themes_count": len(themes),
        "subtopic_rows_count": len(rows),
        "subtopics_distinct_count": len(subtopics),
        "rows": [
            {
                "row_no": r.row_no,
                "theme_id": r.theme_id,
                "theme": r.theme,
                "subtopic_id": r.subtopic_id,
                "subtopic": r.subtopic,
            }
            for r in rows
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return doc


def load_taxonomy(path: Path = TAXONOMY_JSON_PATH) -> list[TaxonomyRow]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [
        TaxonomyRow(
            row_no=r["row_no"],
            theme_id=r["theme_id"],
            theme=r["theme"],
            subtopic_id=r["subtopic_id"],
            subtopic=r["subtopic"],
        )
        for r in doc["rows"]
    ]


if __name__ == "__main__":
    rows = build_taxonomy()
    doc = write_taxonomy_json(rows)
    print(
        f"themes={doc['themes_count']} subtopic_rows={doc['subtopic_rows_count']} "
        f"subtopics_distinct={doc['subtopics_distinct_count']} -> {TAXONOMY_JSON_PATH}"
    )
