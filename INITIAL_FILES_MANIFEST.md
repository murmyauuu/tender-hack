# Какие файлы должны быть на старте

## Уже входят в starter pack

| Файл | Назначение |
|---|---|
| AGENTS.md | Правила для всех coding-агентов и границы файлов |
| TenderHack_UNIFIED_SPEC_v2.md | Единая архитектура, порядок и 34 промпта |
| START_HERE.md | Как создать Git-репозиторий, получить BASE_SHA и открыть первые чаты |
| INITIAL_FILES_MANIFEST.md | Этот реестр |
| docs/integration/input_inventory.md | Проверка реальных входных данных |
| docs/integration/machine_map.md | Связь людей с четырьмя ноутбуками |
| docs/integration/gpu_slots.md | Расписание тяжёлых запусков |
| docs/integration/decisions.md | Журнал решений интегратора |
| docs/templates/HANDOFF_TEMPLATE.md | Шаблон результата каждого нового чата |
| docs/templates/CR_TEMPLATE.md | Шаблон запроса на изменение общего контракта |
| data/raw/README.md | Правила размещения исходных данных |
| .gitignore | Исключает секреты, веса, БД и сборки |

## Предоставляет команда или организаторы

| Материал | Где взять | Если отсутствует |
|---|---|---|
| Регламент/официальные требования | Файлы организаторов | Не заявлять непроверенное соответствие |
| KB export | Полученный набор задания/предыдущая рабочая папка | C02/C03 real blocked |
| PDF и приложения | Пакет задания | Точные PDF citations ограничены |
| История обращений | Пакет задания | 30 real historical pairs blocked |
| Taxonomy и маршруты | Справочник задания | C04 оставляет unknown |
| Lab-code/Qdrant adapter | Предыдущая разработка команды | A00 выбирает NumPy |
| Веса моделей | Заранее загруженные официальные артефакты | A01/A03 blocked до подготовки |
| Разрешение WSL2 | Ответ организатора/ментора | WSL2 не закрывает Linux gate |
| Существующий код | Рабочая папка команды | Начать новый Git repository |

## Создаются задачами и не нужны до старта

| Артефакт | Кто создаёт | Начиная с какой задачи нужен |
|---|---|---|
| contracts, OpenAPI, JSON Schema и fixtures | A00 | B01, C01, D01 и далее |
| backend skeleton и test fakes | A00 | A01/A02 и далее |
| A00-handoff и SHA C0 | A00 | Все задачи после bootstrap |
| PolicyPort implementation | C01 | A02/A03 |
| knowledge.sqlite и source manifest | C02 | C03 и далее |
| Embedding index | C03 | A03 и далее |
| Dev/final/history suites | D01 | C03/D02 и далее |
| Evaluation runner/report | D02 | D07/D09 |
| Operator reply/CLI | A04 | B03 и demo |
| Reviewed cards | C06 | A05/A06 |
| RC manifest | A06 | D07 |
| Release package | A07 | Сдача |

Task handoff-файл появляется только после соответствующего Task ID. Новый чат получает handoff только тех зависимостей, которые уже выполнены.
