from __future__ import annotations

import serial

from pccooler_lcd import transport


def test_open_with_retry_recovers(monkeypatch):
    connection = transport.CP3Connection(
        device="auto",
        reconnect_attempts=2,
        reconnect_base_delay=0,
        verbose=True,
    )
    attempts = {"count": 0}

    def fake_open():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise FileNotFoundError("temporarily missing")
        connection.path = "/dev/ttyACM0"
        connection.port = object()

    monkeypatch.setattr(connection, "open", fake_open)
    monkeypatch.setattr(connection, "close", lambda: None)
    monkeypatch.setattr(transport, "wait_for_device", lambda *a, **k: "/dev/ttyACM0")

    connection.open_with_retry()
    assert attempts["count"] == 2
    assert connection.path == "/dev/ttyACM0"


def test_open_with_retry_raises_transfer_error(monkeypatch):
    connection = transport.CP3Connection(
        device="auto",
        reconnect_attempts=1,
        reconnect_base_delay=0,
    )
    monkeypatch.setattr(
        connection,
        "open",
        lambda: (_ for _ in ()).throw(
            serial.SerialException("offline")
        ),
    )
    monkeypatch.setattr(connection, "close", lambda: None)
    monkeypatch.setattr(
        transport,
        "wait_for_device",
        lambda *a, **k: (_ for _ in ()).throw(
            FileNotFoundError("missing")
        ),
    )
    monkeypatch.setattr(transport.time, "sleep", lambda _delay: None)

    try:
        connection.open_with_retry()
    except transport.TransferError as error:
        assert "could not be restored" in str(error)
    else:
        raise AssertionError("TransferError was not raised")


def test_context_manager_uses_retry(monkeypatch):
    connection = transport.CP3Connection()
    called = {"open": 0, "close": 0}
    monkeypatch.setattr(
        connection,
        "open_with_retry",
        lambda: called.__setitem__("open", called["open"] + 1),
    )
    monkeypatch.setattr(
        connection,
        "close",
        lambda: called.__setitem__("close", called["close"] + 1),
    )

    with connection:
        pass

    assert called == {"open": 1, "close": 1}
