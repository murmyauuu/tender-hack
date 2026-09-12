# TenderHack

Локальный сервис поддержки по требованиям `TenderHack_UNIFIED_SPEC_v2.1_prefilled.md`.

## C0 bootstrap

- Contracts version: `2.0.0-c0`.
- Канон DTO и Protocol: `contracts/python/tenderhack_contracts`.
- Производные артефакты: `contracts/openapi/openapi.json` и `contracts/schemas/evaluation-export.schema.json`.
- Fixtures в `contracts/fixtures` являются mock-данными для независимой разработки, а не real E2E.
- Зафиксированный тип индекса: NumPy exact cosine; реальный embedding build относится к C03.
- A00 предоставляет только contract/backend skeleton и health. Состояние, очередь, retrieval, generation и handoff реализуются последующими задачами.

## Установка и проверки

~~~powershell
uv sync
uv run python -m tools.generate_contracts
uv run python -m tools.validate_fixtures
uv run pytest
~~~

Генерация должна оставлять Git-tree без diff. Локальный минимальный запуск:

~~~powershell
uv run uvicorn tenderhack_backend.app:app --host 127.0.0.1 --port 8000
~~~

После запуска health доступен по `http://127.0.0.1:8000/api/v1/health`. Статус `degraded` на C0 ожидаем: реальные KnowledgePort и GeneratorPort ещё не подключены.

Начальная процедура Git и порядок задач описаны в `START_HERE.md`.
