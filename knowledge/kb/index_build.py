"""Валидация и приёмка dense-индекса, построенного на G, + штамповка manifest.

Только stdlib (`sqlite3`, `hashlib`, `json`, `os`) — файл лежит прямо в
`knowledge/kb/` и подпадает под сканирование `test_no_model_calls.py`.
Сам forward-pass модели (torch/transformers) сюда не входит: этот модуль
только ПРИНИМАЕТ уже посчитанный `embeddings.npy` + `index_ids.json` от
`knowledge/kb/gpu/embed_and_smoke.py` и проверяет их согласованность со
снимком C02, прежде чем разрешить `SqliteKnowledgeStore` их читать.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from knowledge.kb.dense.vectors import read_npy_f32

__all__ = ["expected_chunk_order", "validate_index_artifact", "stamp_manifest"]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def expected_chunk_order(snapshot_dir: str) -> list[str]:
    """Порядок source_id, в котором G обязан подавать чанки на embedding —
    тот же `ORDER BY ord, source_id`, что зафиксирован в C02-handoff.md."""
    db_path = os.path.join(snapshot_dir, "knowledge.sqlite")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT source_id FROM chunks ORDER BY ord, source_id").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def validate_index_artifact(
    snapshot_dir: str, vectors_path: str, ids_path: str, expected_dim: int
) -> None:
    """Бросить ValueError, если артефакт G не согласован со снимком C02.

    Проверяется: форма массива, размерность, порядок и состав id, конечность
    значений (нет NaN/inf), приблизительная L2-нормализация выхода.
    """
    with open(ids_path, encoding="utf-8") as fh:
        ids = json.load(fh)
    expected_ids = expected_chunk_order(snapshot_dir)
    if ids != expected_ids:
        missing = set(expected_ids) - set(ids)
        extra = set(ids) - set(expected_ids)
        raise ValueError(
            f"{ids_path}: порядок/состав id не совпадает со снимком "
            f"(missing={len(missing)}, extra={len(extra)}, order_matches={ids == expected_ids})"
        )

    npy = read_npy_f32(vectors_path)
    if len(npy.shape) != 2:
        raise ValueError(f"{vectors_path}: ожидается 2D массив, получено {npy.shape}")
    n_rows, dim = npy.shape
    if n_rows != len(ids):
        raise ValueError(f"{vectors_path}: {n_rows} строк против {len(ids)} id")
    if dim != expected_dim:
        raise ValueError(f"{vectors_path}: dim={dim}, ожидалось {expected_dim}")

    import math

    for i in range(n_rows):
        row = npy.data[i * dim : (i + 1) * dim]
        norm = math.sqrt(sum(x * x for x in row))
        if not math.isfinite(norm):
            raise ValueError(f"{vectors_path}: строка {i} ({ids[i]}) содержит NaN/inf")
        if not (0.9 <= norm <= 1.1):
            raise ValueError(
                f"{vectors_path}: строка {i} ({ids[i]}) не L2-нормализована (norm={norm:.4f})"
            )


def stamp_manifest(
    manifest_path: str,
    vectors_path: str,
    ids_path: str,
    embedding_model: str,
    embedding_revision: str,
    embedding_dim: int,
    adapter_version: str,
    index_type: str,
) -> dict:
    """Дописать embedding-поля в manifest.json снимка (поля были null у C02).

    Возвращает обновлённый manifest (тот же файл, что читает
    `SqliteKnowledgeStore`, — единый manifest, не второй параллельный).
    """
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    manifest["embedding_model"] = embedding_model
    manifest["embedding_revision"] = embedding_revision
    manifest["embedding_dim"] = embedding_dim
    manifest["adapter_version"] = adapter_version
    manifest["index_type"] = index_type

    existing_paths = {f["path"] for f in manifest.get("files", [])}
    for path in (vectors_path, ids_path):
        rel = os.path.relpath(path, os.path.dirname(manifest_path))
        if rel in existing_paths:
            continue
        manifest.setdefault("files", []).append(
            {"path": rel, "sha256": _sha256(path), "size_bytes": os.path.getsize(path)}
        )

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest
