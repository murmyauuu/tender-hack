# GPU-слоты профиля G

Планирует A. Один слот — один SHA и одна тяжёлая цель.

| Дата/время UTC | Task | Owner | Commit SHA | Команда/цель | Статус | Артефакт/результат |
|---|---|---|---|---|---|---|
| 2026-09-12 12:29:28–13:35:14 | A01 | A | `dddb724f454c986a60c6b3243db41f22bfbfabea` | WSL2 Ollama `qwen3:8b-q4_K_M` short/long/warm/restart + offline `Qwen3-Embedding-0.6B`, sequential only | completed; WSL2 admission open | `docs/coordination/artem/A01-handoff.md`; 8B fit, 4B fallback not used |
| | C03 | C | | Embedding build/retrieval smoke | planned | |
| | A03 | A | | Первый real E2E | planned | |
| | C07 | C | | Dev retrieval run | planned | |
| 2026-09-12 22:17–22:32 UTC | A05 | A | `461c1145983490f6440b47b4b3bb936db39b0b4a`+ (task/a05) | Concurrency/restart/outage/retry/offline resilience harness, **no GPU used** — session ran on machine M (MacBook Air M2, no CUDA/Ollama), not machine G; see `docs/coordination/artem/A05-handoff.md` §0 | completed, no GPU slot occupied | `docs/coordination/artem/A05-handoff.md` |
| | D07 | D | | Sealed final | planned | |
| | A07/D08 | A/D | | Rehearsal/release | planned | |
