# CR-B01 — frozen fixtures для переходных и source/structured-answer состояний

- Status: proposed
- Owner: Стас / B01
- Contract owner: A
- Detected against: `dddb724f454c986a60c6b3243db41f22bfbfabea`, contracts `2.0.0-c0`

## Проблема

Frozen C0 содержит восемь файлов `CaseView`/`ErrorEnvelope`, но не содержит fixture `RequestView` для `queued`, `retrieving`, `sources_found`/candidate, fixture `SourceRecord` для `source-demo` и структурированных данных `summary/conditions/steps` в публичном `Message`. `answer.json` передаёт только строку `Message.content` и `source_ids`.

Из-за этого B01 может проверить terminal-состояния exact fixtures, но не может одновременно показать реальные fixture-значения progress/source drawer/conditions/steps. Frontend не должен придумывать неизвестные URL, дату, версию, условия или новый DTO.

## Предлагаемое изменение C0 владельцем A

Не добавляя endpoints, заморозить совместимые с текущим OpenAPI примеры:

1. `RequestView` для `queued`, `retrieving`, `sources_found` с `CandidateSource`;
2. `SourceRecord` для `source-demo`, включая честные nullable metadata;
3. закрепить публичное представление `summary/conditions/steps`: либо документированный формат `Message.content`, либо существующий C0 DTO, выбранный владельцем контракта.

## Потребители и тест

- B01/B02: progress, candidate, source drawer и answer sections.
- A02/A03: contract fixtures и API examples.
- Test: все новые fixtures валидируются текущими Pydantic-моделями; generated TS не меняется без изменения OpenAPI; UI fixture test показывает source → conditions → steps без синтетических фактов.

## Текущее безопасное поведение B01

Exact восемь общих fixtures импортируются напрямую. Переходные `RequestView` типизированы generated C0 types и явно относятся к mock; candidate использует только `source_id` из `answer.json`. Source drawer и conditions честно показывают отсутствие данных, URL/PDF/version не выдумываются.
