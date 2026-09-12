# Contracts C0

Версия: `2.0.0-c0`.

`python/tenderhack_contracts` — единственный редактируемый канон DTO и Protocol. OpenAPI и EvaluationExport JSON Schema являются производными и перегенерируются командой:

~~~powershell
uv run python -m tools.generate_contracts
~~~

Fixtures в `fixtures` покрывают answer, clarify, handoff offered, ticket, operator reply, policy closure, generic error и stale version. Это mock-контракт для B/C/D, не доказательство качества модели или real E2E.

Публичные input-модели не содержат `author_id`; автор сообщения специалиста назначается backend после защищённого internal reply.
