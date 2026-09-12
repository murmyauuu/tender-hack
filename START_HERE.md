# С чего начать TenderHack

## REPO_PATH и BASE_SHA

REPO_PATH — полный путь к общей папке Git-проекта на конкретном ноутбуке.

Примеры:

- Windows: C:\Projects\tenderhack
- macOS/Linux/WSL: /home/user/tenderhack

MACHINE_PROFILE — буква G, M, N или W из раздела 3 спецификации; укажите фактический ноутбук. TASK_ID — код задачи, например A00.

BASE_SHA — точный идентификатор Git-коммита, от которого агент начинает задачу. Это не файл и его не скачивают. Получить его:

~~~bash
git rev-parse HEAD
~~~

Полученную длинную строку вставляют вместо <BASE_SHA>.

Первый BASE_SHA появляется после стартового коммита. После A00 главным ориентиром станет SHA коммита/tag bootstrap-contracts-v2. Каждая следующая задача получает SHA принятого состояния, где уже есть её зависимости.

## Если рабочий Git-репозиторий уже есть

1. Сделайте резервную копию.
2. Скопируйте содержимое starter pack в корень репозитория, не заменяя более новые одноимённые файлы без проверки.
3. Положите TenderHack_UNIFIED_SPEC_v2.md в корень.
4. Заполните docs/integration/machine_map.md и input_inventory.md.
5. Выполните:

~~~bash
git status --short
git add AGENTS.md TenderHack_UNIFIED_SPEC_v2.md START_HERE.md docs data/raw/README.md .gitignore
git commit -m "chore: add TenderHack starter pack"
git rev-parse HEAD
~~~

Последняя строка — первый BASE_SHA.

## Если репозитория ещё нет

Создайте папку проекта, распакуйте starter pack и выполните:

~~~bash
git init
git add .
git commit -m "chore: initialize TenderHack workspace"
git rev-parse HEAD
~~~

Если Git просит имя/email, настройте свои настоящие или командные значения:

~~~bash
git config user.name "Имя"
git config user.email "email"
~~~

Примерные значения не копируйте буквально.

## Первые четыре чата

После стартового commit откройте четыре отдельных чата:

- Артём — A00;
- Стас — B00;
- Эдуард — C00;
- Егор — D00.

В каждый передайте карточку задачи из спецификации, REPO_PATH, полученный BASE_SHA, профиль машины, AGENTS.md, спецификацию и только реально доступные входы.

B00/C00/D00 не требуют contracts/fixtures: их ещё нет. Их создаёт A00. После принятия A00 интегратор сообщает новый SHA C0. Затем запускаются новые чаты B01/C01/D01 и другие зависимые задачи.

## Ветка и worktree

Простой вариант:

~~~bash
git switch -c task/a00-bootstrap <BASE_SHA>
~~~

При нескольких задачах на одной машине:

~~~bash
git worktree add ../tenderhack-a00 -b task/a00-bootstrap <BASE_SHA>
~~~

Угловые скобки замените реальным значением.

## Что появляется только после задач

Эти файлы не должны существовать изначально:

- contracts, OpenAPI, JSON Schema, API/export fixtures — A00;
- backend skeleton и test fakes — A00;
- knowledge.sqlite, KB manifest, source snapshot — C02;
- embeddings/index — C03;
- dev/final suites — D01;
- runner/report — D02;
- task handoff — после соответствующей задачи;
- RC/release manifest — A06/A07.

Если зависимый чат не видит такой результат, он не создаёт его заново: выполняет автономную часть и фиксирует отсутствующий commit/handoff.

## Что должна предоставить команда

Отметьте в docs/integration/input_inventory.md:

- текущий репозиторий или решение начать с пустого;
- официальный регламент/правила хакатона;
- локальную выгрузку KB;
- PDF-инструкции и приложения;
- историю обращений;
- справочник тем/подтем, линий и адресатов;
- существующий lab-код/Qdrant adapter;
- локальные веса моделей либо согласованный этап загрузки;
- ответ организатора о допустимости WSL2;
- фактически оставшееся время.

Starter pack не может создать официальные материалы. Их берут у организаторов или из прежней папки команды. Отсутствие фиксируется как blocker и ограничивает зависимые результаты.
