import json
from pathlib import Path

from pydantic import TypeAdapter
from tenderhack_contracts import CaseView, ErrorEnvelope, RequestView, SourceRecord

ROOT = Path(__file__).parents[1]
FIXTURES = {
    "answer.json": CaseView,
    "clarify.json": CaseView,
    "handoff_offered.json": CaseView,
    "ticket.json": CaseView,
    "operator.json": CaseView,
    "policy.json": CaseView,
    "error.json": ErrorEnvelope,
    "stale.json": ErrorEnvelope,
    "request_queued.json": RequestView,
    "request_retrieving.json": RequestView,
    "request_sources_found.json": RequestView,
    "source.json": SourceRecord,
}


def main() -> None:
    for name, model in FIXTURES.items():
        path = ROOT / "contracts" / "fixtures" / name
        TypeAdapter(model).validate_python(json.loads(path.read_text(encoding="utf-8")))
        print(f"valid: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
