"""Приёмка dense-индекса от G: валидация формы/порядка/нормализации + manifest.

Векторы здесь СИНТЕТИЧЕСКИЕ (случайные детерминированные, не реальный
forward-pass) — тест проверяет только код валидации/штамповки, а не
семантическое качество. Реальный embeddings.npy ещё не доставлен (см.
C03-handoff.md, blocked-on-G); этот тест не выдаёт синтетику за него и не
трогает настоящий var/knowledge/manifest.json.
"""

from __future__ import annotations

import json
import math
import shutil

import pytest

from knowledge.kb.dense.vectors import write_npy_f32
from knowledge.kb.index_build import (
    expected_chunk_order,
    stamp_manifest,
    validate_index_artifact,
)


def _fake_unit_vector(seed: int, dim: int) -> list[float]:
    vec = [((seed * 2654435761 + i * 40503) % 1000) / 1000.0 - 0.5 for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


@pytest.fixture
def fake_index(tmp_path, snapshot_dir):
    """Копия реального снимка + синтетический, но структурно валидный индекс."""
    work_dir = tmp_path / "work"
    shutil.copytree(snapshot_dir, work_dir)
    ids = expected_chunk_order(str(work_dir))
    dim = 8  # маленькая размерность для скорости теста; проверка dim делается отдельно
    rows = [_fake_unit_vector(i, dim) for i in range(len(ids))]
    vectors_path = str(work_dir / "index.npy")
    ids_path = str(work_dir / "index_ids.json")
    write_npy_f32(vectors_path, rows)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    return {"dir": str(work_dir), "vectors": vectors_path, "ids": ids_path, "dim": dim, "ids_list": ids}


def test_expected_chunk_order_matches_manifest_count(snapshot_dir, manifest):
    ids = expected_chunk_order(snapshot_dir)
    assert len(ids) == manifest["counts"]["included"]
    assert len(ids) == len(set(ids)), "source_id обязаны быть уникальны"


def test_validate_index_artifact_accepts_well_formed_index(fake_index):
    validate_index_artifact(fake_index["dir"], fake_index["vectors"], fake_index["ids"], fake_index["dim"])


def test_validate_index_artifact_rejects_wrong_dim(fake_index):
    with pytest.raises(ValueError, match="dim"):
        validate_index_artifact(fake_index["dir"], fake_index["vectors"], fake_index["ids"], fake_index["dim"] + 1)


def test_validate_index_artifact_rejects_id_order_mismatch(fake_index):
    shuffled = list(reversed(fake_index["ids_list"]))
    with open(fake_index["ids"], "w", encoding="utf-8") as fh:
        json.dump(shuffled, fh, ensure_ascii=False)
    with pytest.raises(ValueError, match="id"):
        validate_index_artifact(fake_index["dir"], fake_index["vectors"], fake_index["ids"], fake_index["dim"])


def test_validate_index_artifact_rejects_non_normalized_rows(tmp_path, snapshot_dir):
    work_dir = tmp_path / "work2"
    shutil.copytree(snapshot_dir, work_dir)
    ids = expected_chunk_order(str(work_dir))
    dim = 4
    rows = [[10.0, 0.0, 0.0, 0.0] for _ in ids]  # намеренно не L2-нормализовано
    vectors_path = str(work_dir / "index.npy")
    ids_path = str(work_dir / "index_ids.json")
    write_npy_f32(vectors_path, rows)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    with pytest.raises(ValueError, match="нормализ"):
        validate_index_artifact(str(work_dir), vectors_path, ids_path, dim)


def test_stamp_manifest_fills_embedding_fields_without_touching_real_snapshot(fake_index):
    manifest_path = fake_index["dir"] + "/manifest.json"
    updated = stamp_manifest(
        manifest_path,
        fake_index["vectors"],
        fake_index["ids"],
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        embedding_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        embedding_dim=fake_index["dim"],
        adapter_version="c03-qwen3-embedding-last-token-l2-1.0.0",
        index_type="numpy_exact_cosine",
    )
    assert updated["embedding_model"] == "Qwen/Qwen3-Embedding-0.6B"
    assert updated["embedding_dim"] == fake_index["dim"]
    paths = {f["path"] for f in updated["files"]}
    assert "index.npy" in paths and "index_ids.json" in paths

    with open(manifest_path, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk["embedding_model"] == "Qwen/Qwen3-Embedding-0.6B"
