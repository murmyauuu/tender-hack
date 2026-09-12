"""Чистый stdlib .npy reader/writer и cosine top-k (без пакета numpy)."""

from __future__ import annotations

import json
import math
import os

import pytest

from knowledge.kb.dense.vectors import (
    DenseIndex,
    cosine_similarity,
    index_files_exist,
    l2_normalize,
    read_npy_f32,
    write_npy_f32,
)


def test_write_then_read_roundtrip(tmp_path):
    rows = [[1.0, 2.0, 3.0, 4.0], [0.5, -0.5, 0.25, -0.25], [0.0, 0.0, 0.0, 0.0]]
    path = str(tmp_path / "vecs.npy")
    write_npy_f32(path, rows)
    arr = read_npy_f32(path)
    assert arr.shape == (3, 4)
    flat = arr.data.tolist()
    for i, row in enumerate(rows):
        got = flat[i * 4 : (i + 1) * 4]
        for a, b in zip(got, row):
            assert a == pytest.approx(b, abs=1e-6)


def test_read_npy_rejects_bad_magic(tmp_path):
    path = tmp_path / "bad.npy"
    path.write_bytes(b"NOTNUMPY" + b"\x00" * 20)
    with pytest.raises(ValueError):
        read_npy_f32(str(path))


def test_l2_normalize_produces_unit_vector():
    v = l2_normalize([3.0, 4.0])
    assert math.sqrt(sum(x * x for x in v)) == pytest.approx(1.0)
    assert v[0] == pytest.approx(0.6)
    assert v[1] == pytest.approx(0.8)


def test_l2_normalize_handles_zero_vector():
    assert l2_normalize([0.0, 0.0]) == [0.0, 0.0]


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_is_minus_one():
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_dense_index_load_and_top_k(tmp_path):
    rows = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.0, 0.0, 1.0],
    ]
    ids = ["a", "b", "c", "d"]
    vectors_path = str(tmp_path / "index.npy")
    ids_path = str(tmp_path / "index_ids.json")
    write_npy_f32(vectors_path, rows)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh)

    idx = DenseIndex.load(vectors_path, ids_path)
    assert len(idx) == 4
    assert idx.dim == 3

    top = idx.top_k([1.0, 0.0, 0.0], k=2)
    assert [t[0] for t in top] == ["a", "c"], "ближайший к [1,0,0] -> a, затем c"
    assert top[0][1] > top[1][1]


def test_dense_index_top_k_is_exact_not_approximate(tmp_path):
    """Точный (brute force) поиск: маленький corpus, ожидаемый порядок предсказуем."""
    rows = [[float(i), 0.0] for i in range(1, 6)]  # все коллинеарны -> cos == 1 для всех
    ids = [f"id{i}" for i in range(5)]
    vectors_path = str(tmp_path / "index.npy")
    ids_path = str(tmp_path / "index_ids.json")
    write_npy_f32(vectors_path, rows)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh)
    idx = DenseIndex.load(vectors_path, ids_path)
    top = idx.top_k([1.0, 0.0], k=5)
    assert len(top) == 5
    for _, score in top:
        assert score == pytest.approx(1.0, abs=1e-5)


def test_index_files_exist(tmp_path):
    v = str(tmp_path / "index.npy")
    i = str(tmp_path / "index_ids.json")
    assert index_files_exist(v, i) is False
    open(v, "w").close()
    assert index_files_exist(v, i) is False
    open(i, "w").close()
    assert index_files_exist(v, i) is True


def test_dense_index_rejects_shape_mismatch(tmp_path):
    rows = [[1.0, 2.0], [3.0, 4.0]]
    vectors_path = str(tmp_path / "index.npy")
    ids_path = str(tmp_path / "index_ids.json")
    write_npy_f32(vectors_path, rows)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(["only-one-id"], fh)  # 1 id против 2 строк
    with pytest.raises(ValueError):
        DenseIndex.load(vectors_path, ids_path)
