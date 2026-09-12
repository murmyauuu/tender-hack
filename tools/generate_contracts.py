import json
from pathlib import Path

from tenderhack_backend.app import app
from tenderhack_contracts import EvaluationExport


ROOT = Path(__file__).parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    write_json(ROOT / "contracts" / "openapi" / "openapi.json", app.openapi())
    write_json(
        ROOT / "contracts" / "schemas" / "evaluation-export.schema.json",
        EvaluationExport.model_json_schema(),
    )


if __name__ == "__main__":
    main()

