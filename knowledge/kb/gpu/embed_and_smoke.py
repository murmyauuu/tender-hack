#!/usr/bin/env python3
"""C03 — реальный embedding build + retrieval smoke. ТОЛЬКО профиль G.

Запускать на машине с GPU и уже локально скачанной моделью
`Qwen/Qwen3-Embedding-0.6B` (ревизия закреплена в
`knowledge/kb/dense/encoder.py`, буквально по A01). На M (MacBook Air M2,
без GPU) этот скрипт не запускается и не был запущен — CPU-логика C03
проверена отдельно на mock encoder + честном FTS fallback (см. тесты и
C03-handoff.md).

Что делает, по порядку:

1. Проверяет наличие снимка C02 (`var/knowledge/knowledge.sqlite`) и
   опционально хеш локального `model.safetensors`.
2. Грузит модель, кодирует все чанки снимка (`ORDER BY ord, source_id`) —
   БЕЗ query-инструкции (документы её не получают, §10 «Поиск»).
3. Пишет `index.npy` + `index_ids.json`, валидирует их
   (`knowledge.kb.index_build.validate_index_artifact`) и штампует
   embedding-поля в `manifest.json` снимка.
4. Кодирует 20 dev-запросов (D01, `evaluation/ai_test/dev/ai_test_dev.jsonl`
   — на момент написания лежит на неслитой ветке `origin/task/d01-dataset`,
   см. команду ниже) С query-инструкцией и прогоняет ПОЛНЫЙ пайплайн C03
   (`knowledge.kb.retrieval.run_pipeline`) — тот же код, что и на M, только
   теперь с реальными векторами и реальным encoder.
5. Пишет JSON-лог реальных решений gate по всем 20 dev-кейсам.

Пример полных команд — см. `knowledge/kb/gpu/README.md`.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tenderhack_contracts.models import QueryContext  # noqa: E402

from knowledge.kb.dense.encoder import (  # noqa: E402
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_REVISION,
    EMBEDDING_SAFETENSORS_SHA256,
)
from knowledge.kb.dense.vectors import DenseIndex, write_npy_f32  # noqa: E402
from knowledge.kb.gpu.real_encoder import ADAPTER_VERSION, RealQwen3Encoder  # noqa: E402
from knowledge.kb.index_build import stamp_manifest, validate_index_artifact  # noqa: E402
from knowledge.kb.retrieval import run_pipeline  # noqa: E402

INDEX_TYPE = "numpy_exact_cosine"


def _read_chunks_in_order(snapshot_dir: str) -> tuple[list[str], list[str]]:
    """(source_ids, document_texts) в порядке ORDER BY ord, source_id.

    document_texts = title + "\\n" + text — заголовок входит в embedding
    (§10 «Поиск»), text_norm из FTS сюда НЕ подаётся (это лексический ключ,
    не для dense) — берём именно `title`/`text`, не `raw_title`/`text_norm`
    (см. C02-handoff.md, раздел «Точка интеграции для C03»).
    """
    db_path = os.path.join(snapshot_dir, "knowledge.sqlite")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT source_id, title, text FROM chunks ORDER BY ord, source_id"
        ).fetchall()
    finally:
        conn.close()
    ids = [r["source_id"] for r in rows]
    texts = [f"{r['title']}\n{r['text']}" for r in rows]
    return ids, texts


def _find_local_safetensors(model_id: str, revision: str) -> str | None:
    """Best-effort поиск локального кеша HF без сетевого вызова."""
    cache_root = os.environ.get(
        "HF_HOME", os.path.expanduser("~/.cache/huggingface")
    )
    hub_dir = os.path.join(cache_root, "hub")
    if not os.path.isdir(hub_dir):
        return None
    slug = "models--" + model_id.replace("/", "--")
    candidate_dir = os.path.join(hub_dir, slug)
    if not os.path.isdir(candidate_dir):
        return None
    for root, _dirs, files in os.walk(candidate_dir):
        for name in files:
            if name == "model.safetensors":
                return os.path.join(root, name)
    return None


def _sha256_file(path: str) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _map_gold_to_source_ids(conn: sqlite3.Connection) -> dict[str, list[str]]:
    rows = conn.execute("SELECT source_id, original_ids FROM chunks").fetchall()
    mapping: dict[str, list[str]] = {}
    for source_id, original_ids_json in rows:
        for oid in json.loads(original_ids_json or "[]"):
            mapping.setdefault(oid, []).append(source_id)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", default=os.path.join(REPO_ROOT, "var", "knowledge"))
    parser.add_argument(
        "--dev-jsonl",
        default=os.path.join(REPO_ROOT, "evaluation", "ai_test", "dev", "ai_test_dev.jsonl"),
        help=(
            "20 dev-кейсов D01. Если файла нет локально (ветка task/d01-dataset "
            "ещё не слита): git show origin/task/d01-dataset:evaluation/ai_test/dev/"
            "ai_test_dev.jsonl > /tmp/ai_test_dev.jsonl и передать --dev-jsonl /tmp/..."
        ),
    )
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--skip-safetensors-check", action="store_true")
    parser.add_argument(
        "--retrieval-log",
        default=None,
        help="Путь для лога dev-retrieval (по умолчанию <snapshot-dir>/retrieval_log_dev20.json)",
    )
    args = parser.parse_args()

    snapshot_dir = args.snapshot_dir
    vectors_path = os.path.join(snapshot_dir, "index.npy")
    ids_path = os.path.join(snapshot_dir, "index_ids.json")
    manifest_path = os.path.join(snapshot_dir, "manifest.json")
    retrieval_log_path = args.retrieval_log or os.path.join(
        snapshot_dir, "retrieval_log_dev20.json"
    )

    if not os.path.exists(os.path.join(snapshot_dir, "knowledge.sqlite")):
        print(f"FATAL: {snapshot_dir}/knowledge.sqlite не найден. Собрать: "
              f"python3 -m knowledge.kb.ingest --out {snapshot_dir}", file=sys.stderr)
        return 2

    if not args.skip_safetensors_check:
        local = _find_local_safetensors(EMBEDDING_MODEL, EMBEDDING_REVISION)
        if local is None:
            print(
                "WARNING: model.safetensors не найден локально автоматически "
                f"(искали в HF_HOME/hub для {EMBEDDING_MODEL}). Если офлайн — "
                "модель должна быть уже скачана (A01). Продолжаю (--skip-safetensors-check "
                "чтобы убрать это предупреждение).",
                file=sys.stderr,
            )
        else:
            actual = _sha256_file(local)
            print(f"model.safetensors: {local}\n  sha256 actual   = {actual}\n"
                  f"  sha256 expected = {EMBEDDING_SAFETENSORS_SHA256}")
            if actual != EMBEDDING_SAFETENSORS_SHA256:
                print("FATAL: safetensors sha256 mismatch — не тот вес/ревизия.", file=sys.stderr)
                return 3

    print(f"== 1/4: чтение чанков снимка {snapshot_dir} ==")
    ids, texts = _read_chunks_in_order(snapshot_dir)
    print(f"chunks: {len(ids)}")

    print(f"== 2/4: загрузка модели {EMBEDDING_MODEL}@{EMBEDDING_REVISION} на {args.device} ==")
    t0 = time.perf_counter()
    encoder = RealQwen3Encoder(device=args.device)
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"load_ms={load_ms:.1f}")

    print(f"== 3/4: батч-инференс {len(texts)} документов (batch_size={args.batch_size}) ==")
    t0 = time.perf_counter()
    vectors = encoder.encode_documents(texts, batch_size=args.batch_size)
    encode_ms = (time.perf_counter() - t0) * 1000
    print(f"encode_ms={encode_ms:.1f} ({encode_ms / max(1, len(texts)):.2f} ms/chunk)")

    write_npy_f32(vectors_path, vectors)
    with open(ids_path, "w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    print(f"written: {vectors_path} ({os.path.getsize(vectors_path)} bytes)")
    print(f"written: {ids_path} ({os.path.getsize(ids_path)} bytes)")

    validate_index_artifact(snapshot_dir, vectors_path, ids_path, EMBEDDING_DIM)
    print("validate_index_artifact: OK (форма/порядок/L2-норма согласованы со снимком)")

    manifest = stamp_manifest(
        manifest_path,
        vectors_path,
        ids_path,
        embedding_model=EMBEDDING_MODEL,
        embedding_revision=EMBEDDING_REVISION,
        embedding_dim=EMBEDDING_DIM,
        adapter_version=ADAPTER_VERSION,
        index_type=INDEX_TYPE,
    )
    print(f"manifest stamped: {manifest_path}")
    print(f"  vectors sha256: {_sha256_file(vectors_path)}")
    print(f"  ids sha256:     {_sha256_file(ids_path)}")

    print(f"== 4/4: dev retrieval smoke ({args.dev_jsonl}) ==")
    if not os.path.exists(args.dev_jsonl):
        print(
            f"WARNING: {args.dev_jsonl} не найден. D01 на неслитой ветке — получить: "
            "git show origin/task/d01-dataset:evaluation/ai_test/dev/ai_test_dev.jsonl "
            "> /tmp/ai_test_dev.jsonl (и передать --dev-jsonl /tmp/ai_test_dev.jsonl). "
            "Индекс уже построен и сохранён — smoke можно повторить отдельно.",
            file=sys.stderr,
        )
        return 0

    dense_index = DenseIndex.load(vectors_path, ids_path)
    db_path = os.path.join(snapshot_dir, "knowledge.sqlite")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    gold_map = _map_gold_to_source_ids(conn)

    dev_cases = []
    with open(args.dev_jsonl, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                dev_cases.append(json.loads(line))

    log_entries = []
    for case in dev_cases:
        question = case["messages"][-1]["text"]
        role = case.get("role")
        query = QueryContext(
            text=question,
            confirmed_facts={"role": role} if role else {},
            recent_user_messages=[m["text"] for m in case["messages"][:-1]],
            clarification_count=0,
            trace_id=f"dev-smoke:{case['test_id']}",
        )
        result = run_pipeline(conn, None, query, dense_index, encoder)
        gold_ids = case.get("gold_source_ids", [])
        gold_source_ids_mapped = sorted(
            {sid for g in gold_ids for sid in gold_map.get(g, [])}
        )
        selected_source_ids = {
            c.source_id for c in result.candidates if c.evidence_id in result.selected_evidence_ids
        }
        candidate_source_ids = {c.source_id for c in result.candidates}
        log_entries.append(
            {
                "test_id": case["test_id"],
                "question": question,
                "role": role,
                "gold_source_ids_raw": gold_ids,
                "gold_source_ids_mapped": gold_source_ids_mapped,
                "decision": result.decision,
                "reason_codes": result.reason_codes,
                "candidate_source_ids": sorted(candidate_source_ids),
                "selected_source_ids": sorted(selected_source_ids),
                "gold_in_candidates": bool(set(gold_source_ids_mapped) & candidate_source_ids),
                "gold_in_selected": bool(set(gold_source_ids_mapped) & selected_source_ids),
            }
        )

    conn.close()

    with open(retrieval_log_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_by": "knowledge/kb/gpu/embed_and_smoke.py",
                "embedding_model": EMBEDDING_MODEL,
                "embedding_revision": EMBEDDING_REVISION,
                "n_dev_cases": len(log_entries),
                "n_gold_in_candidates": sum(e["gold_in_candidates"] for e in log_entries),
                "n_gold_in_selected": sum(e["gold_in_selected"] for e in log_entries),
                "n_answer_allowed": sum(e["decision"] == "ANSWER_ALLOWED" for e in log_entries),
                "cases": log_entries,
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )
    print(f"written: {retrieval_log_path}")
    print(
        f"dev20 summary: gold_in_candidates={sum(e['gold_in_candidates'] for e in log_entries)}/20, "
        f"gold_in_selected={sum(e['gold_in_selected'] for e in log_entries)}/20, "
        f"ANSWER_ALLOWED={sum(e['decision'] == 'ANSWER_ALLOWED' for e in log_entries)}/20"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
