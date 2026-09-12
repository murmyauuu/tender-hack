import json
from pathlib import Path
from urllib.request import Request
from uuid import uuid4

from tools.operator_reply import send_operator_reply


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps({"message_id": str(uuid4())}).encode()


def test_operator_cli_reads_text_file_and_key_from_environment(
    tmp_path: Path,
) -> None:
    text_file = tmp_path / "reply.txt"
    text_file.write_text("Ответ специалиста\n", encoding="utf-8")
    captured: list[Request] = []

    def opener(request: Request, timeout: float):
        assert timeout == 30
        captured.append(request)
        return FakeResponse()

    result = send_operator_reply(
        base_url="http://127.0.0.1:8000",
        ticket_id=uuid4(),
        expected_case_version=4,
        text_file=text_file,
        next_status="waiting_user",
        environ={"TENDERHACK_OPERATOR_REPLY_KEY": "test-secret"},
        opener=opener,
    )

    request = captured[0]
    payload = json.loads(request.data)
    assert request.get_header("Authorization") == "Bearer test-secret"
    assert payload["text"] == "Ответ специалиста"
    assert payload["expected_case_version"] == 4
    assert payload["next_status"] == "waiting_user"
    assert "test-secret" not in json.dumps(result)
