"""Фиксация входов и хешей: манифест должен совпадать с фактическими файлами."""

from __future__ import annotations

import hashlib
import os
import subprocess

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

KB_JSONL = "TenderHack_KnowledgeBase/knowledge_base_FINAL.jsonl"
# Фактический SHA-256 рабочего дерева, он же хеш git blob (проверено в C02).
# В манифесте A00 стоит другое значение — хеш CRLF-версии, см. handoff.
KB_JSONL_SHA = "71bf714a9e205a35f5d8ec0fd2d0f9bbd4ad3a8409968b754eb8de7b349d79ae"
A00_MANIFEST_SHA = "439e7041b233498a894a9eab41917e07e79109408e1f09b7cbb96668c1b8df2c"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def test_manifest_hashes_match_actual_files(manifest):
    assert manifest["input_files"], "манифест обязан перечислять входы"
    for item in manifest["input_files"]:
        path = os.path.join(REPO_ROOT, item["name"])
        assert os.path.exists(path), f"вход отсутствует: {item['name']}"
        assert item["sha256"] == _sha256(path), f"хеш разошёлся: {item['name']}"


def test_kb_snapshot_hash_is_the_measured_one(manifest):
    entry = next(i for i in manifest["input_files"] if i["name"] == KB_JSONL)
    assert entry["sha256"] == KB_JSONL_SHA
    assert entry["sha256"] != A00_MANIFEST_SHA, "нельзя брать хеш из манифеста A00"


def test_kb_snapshot_hash_equals_git_blob():
    """Фактический хеш рабочего дерева совпадает с содержимым git blob."""
    blob = subprocess.run(
        ["git", "show", f"HEAD:{KB_JSONL}"],
        cwd=REPO_ROOT, capture_output=True, check=True,
    ).stdout
    assert hashlib.sha256(blob).hexdigest() == KB_JSONL_SHA


def test_a00_manifest_hash_is_reproduced_by_crlf_conversion():
    """Причина расхождения с A00 — перевод строк, а не другое содержимое."""
    data = open(os.path.join(REPO_ROOT, KB_JSONL), "rb").read()
    assert b"\r\n" not in data, "в рабочем дереве перевод строк LF"
    crlf = data.replace(b"\n", b"\r\n")
    assert hashlib.sha256(crlf).hexdigest() == A00_MANIFEST_SHA


def test_raw_count_is_the_measured_1468(manifest, raw_rows):
    """Counts берутся из файла, а не из api_report.json (530/483/944)."""
    assert len(raw_rows) == 1468
    assert manifest["counts"]["raw"] == 1468


def test_counts_agree_with_c00(manifest, raw_rows):
    pdf = sum(1 for r in raw_rows if r["source_type"] == "organizer_pdf")
    portal = sum(1 for r in raw_rows if r["source_type"] == "portal_knowledge_base_api")
    assert (pdf, portal) == (941, 527)
    assert manifest["counts"]["articles"] == 480, "480 уникальных article_id (C00)"
    assert manifest["counts"]["by_source_type"]["portal_kb"] == 527


def test_embedding_fields_are_explicit_null(manifest):
    """C02 embeddings не строит: поля null ЯВНО, а не выдуманы."""
    for key in (
        "embedding_model", "embedding_revision", "embedding_dim",
        "adapter_version", "index_type",
    ):
        assert key in manifest, f"поле {key} обязано присутствовать в манифесте"
        assert manifest[key] is None, f"{key} должно быть null"
    assert "пересборк" in manifest["embedding_note"].lower()


def test_manifest_files_carry_path_and_sha(manifest, snapshot_dir):
    assert manifest["files"], "манифест обязан перечислять артефакты"
    entry = manifest["files"][0]
    assert entry["path"].endswith("knowledge.sqlite")
    assert len(entry["sha256"]) == 64
    assert entry["size_bytes"] > 0
