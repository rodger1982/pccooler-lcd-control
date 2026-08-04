import json

from pccooler_lcd.protocol_cp3 import (
    decode_packet_text,
    make_request,
)
from pccooler_lcd.protocol_lab import (
    ProtocolRecorder,
    protocol_catalog,
)


def test_recorder_writes_json(tmp_path):
    path = tmp_path / "trace.json"
    recorder = ProtocolRecorder(path)
    recorder.record("TX", "example", b"abc", answer=42)
    data = json.loads(path.read_text())
    assert data[0]["raw_hex"] == "616263"
    assert data[0]["metadata"]["answer"] == 42


def test_decode_request_packet():
    packet = make_request(
        "GET status",
        1,
        2,
        {"example": True},
    )
    decoded = decode_packet_text(packet)
    assert decoded["first_line"] == "GET status 1"
    assert decoded["headers"]["SeqNumber"] == "1"
    assert decoded["body_json"]["example"] is True


def test_catalog_marks_transport_confirmed():
    catalog = protocol_catalog()
    assert catalog["confirmed"]["POST transport"]["status"] == "confirmed"
