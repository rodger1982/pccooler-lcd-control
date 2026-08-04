from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import struct
import time

START_END=0x5A

class CP3Error(RuntimeError):
    pass

@dataclass(slots=True)
class Reply:
    raw: bytes
    status: int|None
    ack_number: int|None
    content: dict|None

    @property
    def successful(self)->bool:
        return self.status==200

def checksum(length_bytes:bytes,payload:bytes)->int:
    return (sum(length_bytes)+sum(payload))&0xFF

def frame(payload:bytes)->bytes:
    total=len(payload)+5
    if total>0xFFFF:
        raise ValueError("CP3 control frame exceeds 65535 bytes")
    length=total.to_bytes(2,"big")
    return bytes([START_END])+length+payload+bytes([checksum(length,payload),START_END])

def make_request(method:str,sequence:int,date_ms:int,content:dict)->bytes:
    body=json.dumps(content,separators=(",",":"),ensure_ascii=True).encode("ascii")
    header=(
        f"{method} 1\r\n"
        f"SeqNumber={sequence}\r\n"
        f"Date={date_ms}\r\n"
        f"ContentType=json\r\n"
        f"ContentLength={len(body)}\r\n\r\n"
    ).encode("ascii")
    return frame(header+body)

def announce_frame(sequence:int,date_ms:int,file_name:str,file_size:int)->bytes:
    return make_request("POST transport",sequence,date_ms,{"type":"media","fileSize":file_size,"fileName":file_name})

def complete_frame(sequence:int,date_ms:int,file_name:str)->bytes:
    return make_request("POST transported",sequence,date_ms,{"md5":"todo","fileName":file_name})

def parse_png_dimensions(data:bytes)->tuple[int,int]:
    if len(data)<24 or data[:8]!=b"\x89PNG\r\n\x1a\n" or data[12:16]!=b"IHDR":
        raise ValueError("Input is not a valid PNG")
    return struct.unpack(">II",data[16:24])

def parse_reply(raw:bytes)->Reply:
    if len(raw)<5 or raw[0]!=START_END or raw[-1]!=START_END:
        return Reply(raw,None,None,None)
    total=int.from_bytes(raw[1:3],"big")
    if total!=len(raw):
        return Reply(raw,None,None,None)
    expected=checksum(raw[1:3],raw[3:-2])
    if expected!=raw[-2]:
        raise CP3Error(f"Bad reply checksum: expected {expected:02x}, got {raw[-2]:02x}")
    text=raw[3:-2].decode("utf-8","replace")
    head,_,body=text.partition("\r\n\r\n")
    lines=head.split("\r\n")
    status=None
    if lines:
        parts=lines[0].split()
        if len(parts)>=2 and parts[1].isdigit():
            status=int(parts[1])
    ack=None
    for line in lines[1:]:
        if line.startswith("AckNumber="):
            try: ack=int(line.split("=",1)[1])
            except ValueError: pass
    content=None
    if body:
        try: content=json.loads(body)
        except json.JSONDecodeError: pass
    return Reply(raw,status,ack,content)

def read_frame(serial_port,timeout:float=3.0)->bytes:
    deadline=time.monotonic()+timeout
    data=bytearray()
    expected=None
    while time.monotonic()<deadline:
        chunk=serial_port.read(4096)
        if not chunk:
            continue
        data.extend(chunk)
        while data and data[0]!=START_END:
            del data[0]
        if len(data)>=3 and expected is None:
            expected=int.from_bytes(data[1:3],"big")
        if expected is not None and len(data)>=expected:
            return bytes(data[:expected])
    return bytes(data)

def generated_filename(now:datetime|None=None)->str:
    now=now or datetime.now()
    return now.strftime("%Y-%m-%d_%H-%M-%S-")+f"{now.microsecond//1000:03d}.osd"


def request_preview(
    method: str,
    sequence: int,
    date_ms: int,
    content: dict,
) -> dict:
    packet = make_request(method, sequence, date_ms, content)
    return {
        "method": method,
        "sequence": sequence,
        "date_ms": date_ms,
        "content": content,
        "packet_length": len(packet),
        "packet_hex": packet.hex(),
    }


def describe_frame(raw: bytes) -> dict:
    description = {
        "length": len(raw),
        "hex": raw.hex(),
        "valid_start_end": bool(
            len(raw) >= 2
            and raw[0] == START_END
            and raw[-1] == START_END
        ),
    }
    if not description["valid_start_end"] or len(raw) < 5:
        return description

    declared = int.from_bytes(raw[1:3], "big")
    payload = raw[3:-2]
    description["declared_length"] = declared
    description["checksum"] = raw[-2]
    description["checksum_valid"] = (
        checksum(raw[1:3], payload) == raw[-2]
    )
    description["payload_text"] = payload.decode(
        "utf-8",
        "replace",
    )
    return description
