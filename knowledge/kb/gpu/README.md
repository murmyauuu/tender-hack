# C03 — реальный embedding build + dev retrieval smoke (профиль G)

Этот каталог — единственная часть C03, которая требует GPU/torch/transformers.
Всё остальное (`knowledge/kb/retrieval.py`, `knowledge/kb/dense/`,
`knowledge/kb/lexical.py`, `knowledge/kb/store.py`) написано и протестировано
на M (mock encoder + честный FTS fallback). Этот README и скрипт
предназначены для того, у кого физический доступ к машине G (Артём, либо
пользователь лично на G) — агент C03 (эта сессия, M, без GPU) сам его не
выполнял. Статус: **blocked-on-G**, см. `docs/coordination/eduard/C03-handoff.md`.

## Предпосылки

1. Занятый GPU-слот в `docs/integration/gpu_slots.md` (владелец A планирует
   слоты; в момент написания C03 в таблице стоит как `planned`).
2. Локально уже присутствует `Qwen/Qwen3-Embedding-0.6B` ревизии
   `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` (A01 её скачал и проверил на
   Windows CUDA venv — см. `docs/coordination/artem/A01-handoff.md` на ветке
   `task/a01`). `model.safetensors` sha256 должен быть
   `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
3. `torch` + `transformers` установлены в среде, где будет запускаться
   Python (та же среда, что A01 использовал для embedding-смока, либо новая
   на Linux/WSL2 — на момент A01 такой Linux-среды для embedding ещё не
   было, это отдельный блокер A01, не C03).
4. Собранный снимок C02: `var/knowledge/knowledge.sqlite` +
   `var/knowledge/manifest.json`. Если их нет:
   ```bash
   python3 -m knowledge.kb.ingest --out var/knowledge
   ```
   Ожидаемый `snapshot_id`: `kb-4918a97f0874d1e8` (1528 chunks, 636 parents).
   Если получилось другое — снимок не тот, останавливаться и разбираться,
   не продолжать со сборкой embeddings.
5. 20 dev-кейсов D01 (`evaluation/ai_test/dev/ai_test_dev.jsonl`). На момент
   написания C03 они лежат на **неслитой** ветке `origin/task/d01-dataset`:
   ```bash
   git fetch origin task/d01-dataset
   git show origin/task/d01-dataset:evaluation/ai_test/dev/ai_test_dev.jsonl \
     > /tmp/ai_test_dev.jsonl
   ```
   (Если к моменту запуска D01 уже влит интегратором в `main`, можно
   использовать путь из рабочего дерева напрямую и опустить `--dev-jsonl`.)

## Команда

Из корня репозитория, веткой `task/c03` (или её результатом после приёмки):

```bash
python3 -m knowledge.kb.gpu.embed_and_smoke \
  --snapshot-dir var/knowledge \
  --dev-jsonl /tmp/ai_test_dev.jsonl \
  --device cuda \
  --batch-size 16
```

На CPU-only машине без реального GPU скрипт тоже технически запустится с
`--device cpu`, но тогда инференс по 1528 чанкам будет медленным — это не
теряет корректность, но обесценивает смысл выполнять его не на G.

## Что скрипт делает и что проверяет сам

1. Сверяет `model.safetensors` (best-effort поиск в `HF_HOME/hub`) с пином
   A01; при несовпадении — `FATAL`, останавливается (не продолжает с чужой
   моделью). `--skip-safetensors-check`, если пин не находится автоматически
   (нестандартный `HF_HOME`) — тогда сверить хеш вручную и сверить с
   выводом.
2. Кодирует все чанки снимка (порядок `ORDER BY ord, source_id`) —
   конкатенация `title` + `\n` + `text`, БЕЗ query-инструкции (документы
   инструкцию не получают, §10 «Поиск»).
3. Пишет `var/knowledge/index.npy` (`.npy` float32, читается без пакета
   numpy — `knowledge/kb/dense/vectors.py`) и `var/knowledge/index_ids.json`
   (список `source_id` в том же порядке).
4. Валидирует артефакт (`knowledge.kb.index_build.validate_index_artifact`):
   форма, совпадение id/порядка со снимком, L2-норма каждой строки в
   диапазоне [0.9, 1.1], отсутствие NaN/inf. Останавливается с `ValueError`,
   если что-то не так — не пишет манифест с плохим индексом.
5. Штампует `embedding_model`/`embedding_revision`/`embedding_dim`/
   `adapter_version`/`index_type` в СУЩЕСТВУЮЩИЙ `var/knowledge/manifest.json`
   (эти поля у C02 были `null` — это тот же единый manifest, не второй
   параллельный файл) и дописывает `index.npy`/`index_ids.json` в
   `files[]` с их sha256.
6. Кодирует 20 dev-запросов С query-инструкцией A01 и прогоняет **тот же**
   `knowledge.kb.retrieval.run_pipeline`, что используется на M — теперь с
   реальным `DenseIndex` и реальным `RealQwen3Encoder` вместо mock. Никакого
   отдельного «G-only» пайплайна нет — код retrieval не меняется между M и G,
   меняется только encoder/индекс.
7. Пишет `var/knowledge/retrieval_log_dev20.json`: по каждому из 20 кейсов —
   вопрос, gold_source_ids (сырые и смапленные на внутренние `source_id`
   через `original_ids`), решение gate, reason_codes, найденные кандидаты,
   выбранные evidence, флаги `gold_in_candidates`/`gold_in_selected`.

## Ожидаемый вывод (форма, не придуманные числа)

```
== 1/4: чтение чанков снимка var/knowledge ==
chunks: 1528
== 2/4: загрузка модели Qwen/Qwen3-Embedding-0.6B@97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 на cuda ==
load_ms=<реальное>
== 3/4: батч-инференс 1528 документов (batch_size=16) ==
encode_ms=<реальное> (<реальное> ms/chunk)
written: var/knowledge/index.npy (<реальный размер> bytes)
written: var/knowledge/index_ids.json (<реальный размер> bytes)
validate_index_artifact: OK (форма/порядок/L2-норма согласованы со снимком)
manifest stamped: var/knowledge/manifest.json
  vectors sha256: <реальный>
  ids sha256:     <реальный>
== 4/4: dev retrieval smoke (/tmp/ai_test_dev.jsonl) ==
written: var/knowledge/retrieval_log_dev20.json
dev20 summary: gold_in_candidates=<N>/20, gold_in_selected=<N>/20, ANSWER_ALLOWED=<N>/20
```

Никакие числа выше не подставлены заранее — они реальны только после
фактического запуска на G. Не публиковать `<N>` как «результат C03», пока
скрипт не выполнен физически.

## Что вернуть агенту C03/интегратору после запуска

Три файла из `var/knowledge/` (вне Git, передаются как артефакт с хешами —
`AGENTS.md`):

- `index.npy`
- `index_ids.json`
- `manifest.json` (обновлённый, с реальными embedding-полями)
- `retrieval_log_dev20.json`

Плюс полный stdout запуска (для `C03-handoff.md`/`C07`). Если что-то из
`FATAL`/`ValueError` сработало — вернуть именно это сообщение, а не
"должно быть ок".

## Ограничения этого скрипта, зафиксированные заранее

- Один индекс, один тип (`numpy_exact_cosine`, DEC-001) — скрипт не создаёт
  альтернативный ANN/faiss/qdrant индекс.
- Пороги gate (`knowledge/kb/retrieval.py`) не подбираются по результату
  этого прогона — retrieval_log — это диагностика, а не тюнинг под final.
- Дообучение/дозагрузка второй копии модели не предусмотрены — один
  экземпляр `RealQwen3Encoder` на весь прогон (документы + 20 запросов),
  как и требует «один последовательный тяжёлый GPU-участок» (AGENTS.md).
