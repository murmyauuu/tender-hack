# TenderHack frontend

React/TypeScript/Vite клиент с двумя явно разделёнными режимами транспорта:

- `VITE_API_MODE=mock` — frozen C0 fixtures и controlled B03 interaction fixtures, сеть не используется;
- `VITE_API_MODE=real` — sessions/chat/requests/cases/sources/feedback/handoff через generated OpenAPI client.

Без явного `real` приложение запускается в mock-режиме. В real-режиме cookie отправляются с
`credentials: include`; браузер не читает HttpOnly cookie, SQLite или Ollama напрямую.

## Локальный запуск с A02

Запустите backend на `127.0.0.1:8000`, затем:

```powershell
cd frontend
Copy-Item .env.example .env.local
# В .env.local установить VITE_API_MODE=real
npm ci
npm run dev
```

Открывайте `http://127.0.0.1:5173`. Vite проксирует `/api` на
`VITE_API_PROXY_TARGET` (по умолчанию `http://127.0.0.1:8000`), поэтому session cookie остаётся
same-origin. Для production `VITE_API_BASE_URL` можно оставить пустым при размещении UI и API на
одном origin либо задать адрес разрешённого reverse proxy.

Текущий `case_id` сохраняется в localStorage только как указатель для восстановления истории;
авторизация всегда определяется серверной HttpOnly cookie. Polling Request идёт каждые 800 мс в
активной вкладке и каждые 3 секунды в фоне. После terminal Request клиент перечитывает Case,
дедуплицирует сообщения по `message_id` и игнорирует поздние ответы предыдущего `case_id`.
Во время `handed_off` текущий Case перечитывается каждые 1,2 секунды в активной вкладке и каждые
4 секунды в фоне, чтобы настоящий ответ специалиста появился без ручного обновления.

При отклонении chat с 409/429/503 или сетевой ошибке текст остаётся в поле. Автоматического слепого
повтора mutation нет.

Handoff требует отдельного подтверждения и отправляет `expected_case_version` из последнего Case.
Статусы Ticket описывают локальную очередь специалистов нашего сервиса. Operator key и internal reply
endpoint в browser-клиент не подключаются. Повтор failed Request отправляется как `retry_of` с `text=null`,
а ответ пользователя после operator reply остаётся в том же Case и использует его свежую версию.

До публикации A04 состояния clarify/handoff/Ticket/operator/policy и их переходы проверяются только на
явно помеченных frozen/controlled fixtures. Это не real operator/handoff PASS.

## Проверки

```powershell
npm run generate:api
npm run check:generated
npm run typecheck
npm test
npm run build
```

Полный B03 operator/handoff E2E ожидает опубликованный A04 runtime. Fixture или controlled-transport
результат нельзя считать финальным real B03 PASS.
