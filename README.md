# TenderHack

Локальный сервис поддержки по требованиям `TenderHack_UNIFIED_SPEC_v2.1_prefilled.md`.

## A02 backend core

- Contracts version: `2.1.0-a02` (frozen C0 remains tagged as `2.0.0-c0`).
- Канон DTO и Protocol: `contracts/python/tenderhack_contracts`.
- Производные артефакты: `contracts/openapi/openapi.json` и `contracts/schemas/evaluation-export.schema.json`.
- Fixtures в `contracts/fixtures` являются mock-данными для независимой разработки, а не real E2E.
- Зафиксированный тип индекса: NumPy exact cosine; реальный embedding build относится к C03.
- A02 сохраняет session/Case/Message/Request/Feedback в `var/app.sqlite`, выполняет не более одного
  generation через последовательную очередь и публикует результат только после version guard.
- C01 policy подключён в production wiring. До A03 `KnowledgePort.retrieve()` остаётся dependency-injected;
  C02 production adapter предоставляет source lookup/health, а C03 подключит настоящий retrieval.
- Handoff и internal operator reply намеренно остаются за A04.

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

После запуска health доступен по `http://127.0.0.1:8000/api/v1/health`. На A02 статус `degraded` ожидаем до
подключения C03 retrieval и отдельной live-проверки локального GeneratorPort; это не включает test fakes в production wiring.

Создать/восстановить HttpOnly session cookie можно через `POST /api/v1/sessions`. Для browser mutation
значение `Origin` должно совпадать с `TENDERHACK_ALLOWED_ORIGIN`. Production wiring никогда не включает
test fakes; controlled dependencies передаются только через `create_app(..., service=...)` в тестах.

Единый export из согласованного SQLite read snapshot:

~~~powershell
uv run python -m tools.export_data --db var/app.sqlite --output var/evaluation-export.json
~~~

Параметры A01-модели (`qwen3:8b-q4_K_M`, manifest digest, thinking off) закреплены в
`config/runtime/a02.json`. Настройки локального запуска перечислены в `.env.example`.

Начальная процедура Git и порядок задач описаны в `START_HERE.md`.
