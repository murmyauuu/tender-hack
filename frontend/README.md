# TenderHack frontend

React/TypeScript/Vite клиент с двумя явно разделёнными режимами транспорта:

- `VITE_API_MODE=mock` — frozen C0 fixtures, сеть не используется;
- `VITE_API_MODE=real` — sessions/chat/requests/cases/sources/feedback через A02 OpenAPI client.

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

При отклонении chat с 409/429/503 или сетевой ошибке текст остаётся в поле. Автоматического слепого
повтора mutation нет.

## Проверки

```powershell
npm run generate:api
npm run check:generated
npm run typecheck
npm test
npm run build
```

Полный browser RAG E2E не относится к текущему smoke: он ожидает опубликованный A03 runtime и
реальный C03 dense index. Mock/lexical-only результат нельзя считать финальным real RAG E2E.
