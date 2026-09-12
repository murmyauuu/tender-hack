# CR-EDUARD-001 — Сделать `knowledge` импортируемым пакетом и включить его тесты в общий прогон

- **Инициатор / task:** Эдуард / агент C / C01 (Детерминированный policy-модуль)
- **Base SHA / contracts version:** `27d45b1675cc884350e6b06aba431d5d867fb76c` (tag `bootstrap-contracts-v2`) / `2.0.0-c0`
- **Проблема:**
  1. `pyproject.toml` объявляет `[tool.setuptools.packages.find] where = ["contracts/python", "backend"]`. Пакет `knowledge` не входит ни в один из этих корней, поэтому `from knowledge.policy import build_policy` работает только когда текущий каталог — корень репозитория. Фактическая проверка (см. C01-handoff, раздел «Commands and actual outputs»): из другого cwd `import knowledge.policy` даёт `ModuleNotFoundError: No module named 'knowledge'`. При запуске backend как установленного пакета (`uvicorn tenderhack_backend.app:app`) из произвольного каталога A02 не сможет подставить реальную policy вместо `FakePolicy`.
  2. `[tool.pytest.ini_options] testpaths = ["tests"]`. Тесты C01 лежат в зоне C (`knowledge/policy/tests/`) и общим прогоном `uv run pytest` **не подхватываются** — фактически собирается 28 тестов A00, 221 тест policy остаётся за кадром. Регрессии policy не увидит общий CI.
- **Текущий контракт:** изменение НЕ затрагивает `contracts/**`. `PolicyPort`/`PolicyResult` остаются как есть; C01 реализован строго по действующему контракту (синхронный `check(text) -> PolicyResult`).
- **Точное предлагаемое изменение** (файл `pyproject.toml`, зона A):
  ```toml
  [tool.setuptools.packages.find]
  where = ["contracts/python", "backend", "."]
  include = ["tenderhack_contracts*", "tenderhack_backend*", "knowledge*"]

  [tool.pytest.ini_options]
  testpaths = ["tests", "knowledge/policy/tests"]
  ```
  Достаточно любого варианта, дающего два эффекта: `knowledge` импортируется из установленного окружения, и `knowledge/policy/tests` входит в `testpaths`. Точную форму выбирает A как владелец файла.
- **Затронутые потребители:** A02 (внедрение policy вместо `FakePolicy`), общий прогон тестов, D02 runner. Для C02/C03 та же проблема возникнет с `knowledge.kb` — изменение стоит сделать один раз для всего пакета `knowledge`.
- **Обратная совместимость:** полная. Новых зависимостей нет, существующие пакеты и пути не переименовываются, `tests/**` продолжает собираться. `knowledge` — чистый Python/stdlib, вес нулевой.
- **Предлагаемый тест:** после изменения `uv run pytest` собирает 28 + 221 = 249 тестов и проходит; `cd /tmp && uv run --project <repo> python -c "from knowledge.policy import build_policy; build_policy().check('тест')"` завершается без ошибки.
- **Можно ли продолжить независимую часть:** да, C01 завершён и сдан. Обходной путь на сегодня: запускать backend из корня репозитория (cwd попадает в `sys.path`) и прогонять тесты C01 явным путём `uv run pytest knowledge/policy/tests -q`. `pyproject.toml` в C01 не редактировался.
- **Решение A:** accepted — `knowledge` включён в package discovery, а общий прогон включает
  `knowledge/policy/tests` и `knowledge/kb/tests`; C02 использует публичный пакет
  `tenderhack_contracts` вне cwd репозитория.
- **Decision SHA / новая версия contracts:** `dc277e52b536aec62468d77dc2e7cc8a4b0d2dd2` /
  contracts остаётся `2.0.0-c0`.
