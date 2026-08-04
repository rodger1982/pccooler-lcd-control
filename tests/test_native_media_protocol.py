import json

from pccooler_lcd.protocol_cp3 import (
    describe_frame,
    make_request,
    request_preview,
)


def test_request_preview_matches_packet():
    preview = request_preview(
        "GET media",
        123,
        456,
        {"example": True},
    )
    packet = make_request(
        "GET media",
        123,
        456,
        {"example": True},
    )
    assert preview["packet_hex"] == packet.hex()
    assert preview["packet_length"] == len(packet)


def test_describe_frame_recognizes_request():
    packet = make_request(
        "POST transport",
        12,
        34,
        {"fileName": "test.mp4"},
    )
    description = describe_frame(packet)
    assert description["valid_start_end"] is True
    assert description["checksum_valid"] is True
    assert "POST transport" in description["payload_text"]
