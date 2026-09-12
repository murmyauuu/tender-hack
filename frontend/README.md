# TenderHack frontend (B01)

React + TypeScript + Vite client for the frozen C0 contracts. B01 is an explicit mock-only build: it imports the eight shared fixtures from `../contracts/fixtures` and does not call a backend.

```powershell
npm install
npm run generate:api
npm run typecheck
npm test
npm run build
npm run dev
```

`src/generated/**` is generated from `../contracts/openapi/openapi.json` by `@hey-api/openapi-ts`; do not edit it manually. Run `npm run check:generated` after generated files have been committed to verify reproducibility.

The scenario panel renders all eight frozen fixtures plus typed transitional `RequestView` mock states. The limitations caused by missing transition/source/structured-answer fixtures are documented in `docs/coordination/stas/CR-B01.md` and shown honestly in the UI.
