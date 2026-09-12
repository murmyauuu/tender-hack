# Contracts

Текущая версия: `2.1.0-a02`. Исходный frozen C0 остаётся тегом
`bootstrap-contracts-v2` с версией `2.0.0-c0`; совместимое расширение A02 описано в
`docs/integration/contract_changelog.md`.

`python/tenderhack_contracts` — единственный редактируемый канон DTO и Protocol. OpenAPI и EvaluationExport JSON Schema являются производными и перегенерируются командой:

~~~powershell
uv run python -m tools.generate_contracts
~~~

Fixtures в `fixtures` покрывают answer, clarify, handoff offered, ticket, operator reply, policy closure,
generic error, stale version, три стадии `RequestView` и `SourceRecord`. Это mock-контракт для B/C/D,
не доказательство качества модели или real E2E.

Публичные input-модели не содержат `author_id`; автор сообщения специалиста назначается backend после защищённого internal reply.
