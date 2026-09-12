"""Чтение/запись `.npy` и cosine top-k без пакета numpy (только stdlib).

Индекс `numpy_exact_cosine` (DEC-001, config/runtime/c0.json) назван по типу
формата и алгоритма — точный (brute-force) cosine по полному корпусу, без
приближённого поиска (ANN) и без второго индекса. Пакет numpy не входит в
зависимости репозитория (pyproject.toml — файл A, не в зоне C), поэтому
формат `.npy`, который реально пишет `numpy.save()` на машине G, здесь
разбирается вручную через `struct`/`array`. Это тот же самый точный cosine,
только без стороннего пакета — упрощённый второй индекс не создаётся.
"""

from __future__ import annotations

import array
import json
import math
import operator
import os
import re
import struct
from dataclasses import dataclass

__all__ = [
    "NpyArray",
    "read_npy_f32",
    "write_npy_f32",
    "DenseIndex",
    "cosine_similarity",
    "l2_normalize",
]

_MAGIC = b"\x93NUMPY"
_HEADER_RE = re.compile(
    r"'descr'\s*:\s*'([^']+)'.*'fortran_order'\s*:\s*(True|False).*"
    r"'shape'\s*:\s*\(([^)]*)\)",
    re.DOTALL,
)

_SUPPORTED_DESCR = {
    "<f4": ("f", 4),
    "|f4": ("f", 4),
    "=f4": ("f", 4),
    "<f8": ("d", 8),
    "=f8": ("d", 8),
}


@dataclass(frozen=True)
class NpyArray:
    """Плоский результат разбора `.npy`: данные + форма (N, dim)."""

    shape: tuple[int, ...]
    data: array.array  # typecode 'f' (float32) или 'd' (float64), C-order, плоско


def read_npy_f32(path: str) -> NpyArray:
    """Разобрать `.npy`, записанный `numpy.save()` для 2D float32/float64 массива.

    Поддерживаются версии заголовка 1.0 и 2.0, только C-order
    (`fortran_order=False`) — именно так `numpy.save` пишет обычный
    `np.asarray(list_of_vectors, dtype=np.float32)`.
    """
    with open(path, "rb") as fh:
        magic = fh.read(6)
        if magic != _MAGIC:
            raise ValueError(f"{path}: не .npy файл (magic={magic!r})")
        major, minor = fh.read(1)[0], fh.read(1)[0]
        if major == 1:
            (header_len,) = struct.unpack("<H", fh.read(2))
        elif major in (2, 3):
            (header_len,) = struct.unpack("<I", fh.read(4))
        else:
            raise ValueError(f"{path}: неподдерживаемая версия .npy {major}.{minor}")
        header = fh.read(header_len).decode("latin1")
        match = _HEADER_RE.search(header)
        if not match:
            raise ValueError(f"{path}: не удалось разобрать заголовок .npy: {header!r}")
        descr, fortran_order, shape_str = match.groups()
        if fortran_order == "True":
            raise ValueError(f"{path}: fortran_order=True не поддерживается")
        if descr not in _SUPPORTED_DESCR:
            raise ValueError(f"{path}: неподдерживаемый dtype {descr!r} (нужен float32/float64)")
        typecode, itemsize = _SUPPORTED_DESCR[descr]
        shape = tuple(int(x) for x in shape_str.split(",") if x.strip())
        count = 1
        for dim in shape:
            count *= dim
        raw = fh.read(count * itemsize)
        if len(raw) != count * itemsize:
            raise ValueError(f"{path}: файл короче объявленной формы {shape}")
        data = array.array(typecode)
        data.frombytes(raw)
        return NpyArray(shape=shape, data=data)


def write_npy_f32(path: str, rows: list[list[float]]) -> None:
    """Записать 2D float32 массив в формате `.npy` v1.0 (для тестов/синтетики).

    Совместим с тем, что прочитает `read_npy_f32` и что пишет `numpy.save`
    для `np.asarray(rows, dtype=np.float32)`.
    """
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    header = (
        "{'descr': '<f4', 'fortran_order': False, 'shape': (%d, %d), }" % (n_rows, n_cols)
    )
    # Заголовок дополняется пробелами так, чтобы magic+version+len(header)+header
    # было кратно 64 байтам (соглашение формата, не обязательное для чтения,
    # но воспроизводит поведение numpy.save).
    prefix_len = len(_MAGIC) + 2 + 2  # magic + version(2) + header_len(2, v1.0)
    total = prefix_len + len(header) + 1  # +1 на завершающий '\n'
    pad = (-total) % 64
    header = header + " " * pad + "\n"
    with open(path, "wb") as fh:
        fh.write(_MAGIC)
        fh.write(bytes([1, 0]))
        fh.write(struct.pack("<H", len(header)))
        fh.write(header.encode("latin1"))
        flat = array.array("f")
        for row in rows:
            flat.extend(float(x) for x in row)
        fh.write(flat.tobytes())


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return list(vec)
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine между двумя векторами; всегда нормализует заново для честности,
    даже если входы уже L2-нормализованы адаптером (§10 «Поиск»)."""
    na = l2_normalize(a)
    nb = l2_normalize(b)
    return float(sum(map(operator.mul, na, nb)))


@dataclass
class DenseIndex:
    """Корпус dense-векторов + их source_id, в порядке `chunks.ord`."""

    ids: list[str]
    dim: int
    _rows: list[array.array]

    @classmethod
    def load(cls, vectors_path: str, ids_path: str) -> "DenseIndex":
        npy = read_npy_f32(vectors_path)
        if len(npy.shape) != 2:
            raise ValueError(f"{vectors_path}: ожидается 2D массив, получено {npy.shape}")
        n_rows, dim = npy.shape
        with open(ids_path, encoding="utf-8") as fh:
            ids = json.load(fh)
        if not isinstance(ids, list) or len(ids) != n_rows:
            raise ValueError(
                f"{ids_path}: {len(ids) if isinstance(ids, list) else type(ids)} id "
                f"против {n_rows} строк в {vectors_path}"
            )
        rows: list[array.array] = []
        flat = npy.data
        for i in range(n_rows):
            row = array.array("f", flat[i * dim : (i + 1) * dim])
            rows.append(row)
        return cls(ids=list(ids), dim=dim, _rows=rows)

    def __len__(self) -> int:
        return len(self.ids)

    def top_k(self, query_vector: list[float], k: int = 10) -> list[tuple[str, float]]:
        """Точный (не приближённый) top-k по cosine — brute force по всему корпусу."""
        query = l2_normalize(query_vector)
        scored: list[tuple[str, float]] = []
        for source_id, row in zip(self.ids, self._rows):
            row_list = row.tolist()
            norm_row = l2_normalize(row_list)
            score = float(sum(map(operator.mul, query, norm_row)))
            scored.append((source_id, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]


def index_files_exist(vectors_path: str, ids_path: str) -> bool:
    return os.path.exists(vectors_path) and os.path.exists(ids_path)
