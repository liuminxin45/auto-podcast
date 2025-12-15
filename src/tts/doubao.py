from __future__ import annotations

import gzip
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests
import websocket


class DoubaoTTSException(RuntimeError):
    pass


@dataclass
class DoubaoTTSConfig:
    app_id: str
    access_key: str
    secret_key: str
    region: str


class DoubaoTTSClient:
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        self.cfg = DoubaoTTSConfig(
            app_id=os.environ.get("DOUBAO_APP_ID", "").strip(),
            access_key=os.environ.get("DOUBAO_ACCESS_KEY", "").strip(),
            secret_key=os.environ.get("DOUBAO_SECRET_KEY", "").strip(),
            region=os.environ.get("DOUBAO_REGION", "").strip() or "cn-north-1",
        )
        self._conns: Dict[str, websocket.WebSocket] = {}
        self._payloads: Dict[str, Dict[str, Any]] = {}

    def _ws_url(self) -> str:
        return "wss://openspeech.bytedance.com/api/v3/sami/podcasttts"

    def _ws_headers(self) -> Dict[str, str]:
        # From the doc: Podcast API websocket v3
        return {
            "X-Api-App-Id": self.cfg.app_id,
            "X-Api-Access-Key": self.cfg.access_key,
            "X-Api-Resource-Id": "volc.service_type.10050",
            "X-Api-App-Key": "aGjiRDfUWi",
            "X-Api-Request-Id": str(uuid.uuid4()),
        }

    @staticmethod
    def _strip_ssml(ssml: str) -> str:
        # Keep it simple: remove angle-bracket tags.
        out = []
        in_tag = False
        for ch in ssml:
            if ch == "<":
                in_tag = True
                continue
            if ch == ">":
                in_tag = False
                continue
            if not in_tag:
                out.append(ch)
        return "".join(out).strip()

    @staticmethod
    def _build_frame(message_type: int, flags: int, serialization: int, compression: int, payload: bytes) -> bytes:
        # Base header 4 bytes.
        # Byte0: version=1 (0b0001), header_size=1 (4 bytes)
        b0 = (0x1 << 4) | 0x1
        # Byte1: message type (4-bit) + flags (4-bit)
        b1 = ((message_type & 0xF) << 4) | (flags & 0xF)
        # Byte2: serialization (4-bit) + compression (4-bit)
        b2 = ((serialization & 0xF) << 4) | (compression & 0xF)
        b3 = 0

        # Payload size uses big-endian uint32.
        size = len(payload).to_bytes(4, byteorder="big", signed=False)
        return bytes([b0, b1, b2, b3]) + size + payload

    @staticmethod
    def _build_event_frame(
        message_type: int,
        flags: int,
        serialization: int,
        compression: int,
        event_code: int,
        session_id: Optional[str],
        payload: bytes,
    ) -> bytes:
        b0 = (0x1 << 4) | 0x1
        b1 = ((message_type & 0xF) << 4) | (flags & 0xF)
        b2 = ((serialization & 0xF) << 4) | (compression & 0xF)
        b3 = 0

        out = bytearray()
        out += bytes([b0, b1, b2, b3])
        out += int(event_code).to_bytes(4, byteorder="big", signed=False)

        if session_id is not None:
            sid_b = session_id.encode("utf-8")
            out += len(sid_b).to_bytes(4, byteorder="big", signed=False)
            out += sid_b

        out += len(payload).to_bytes(4, byteorder="big", signed=False)
        out += payload
        return bytes(out)

    @staticmethod
    def _parse_frame(raw: bytes) -> Tuple[int, int, int, int, Optional[int], bytes]:
        if len(raw) < 8:
            raise DoubaoTTSException("invalid websocket frame")

        b0, b1, b2, _b3 = raw[0], raw[1], raw[2], raw[3]
        _version = (b0 >> 4) & 0xF
        header_size_x4 = b0 & 0xF
        header_size_bytes = header_size_x4 * 4
        msg_type = (b1 >> 4) & 0xF
        flags = b1 & 0xF
        serialization = (b2 >> 4) & 0xF
        compression = b2 & 0xF

        if len(raw) < header_size_bytes + 4:
            raise DoubaoTTSException("invalid frame: header too short")

        idx = header_size_bytes
        event_code: Optional[int] = None

        # Error frame: doc says byte1 is 0b11110000, and [4~7] is Error code.
        if msg_type == 0xF:
            if len(raw) < idx + 4:
                raise DoubaoTTSException("invalid error frame: missing error code")
            event_code = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
            idx += 4

        if msg_type == 0xF:
            if len(raw) < idx + 4:
                raise DoubaoTTSException("invalid frame: missing payload size")
            payload_size = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
            idx += 4
            payload = raw[idx : idx + payload_size]
            return msg_type, flags, serialization, compression, event_code, payload

        if flags & 0x4:
            if len(raw) < idx + 4:
                raise DoubaoTTSException("invalid frame: missing event code")
            event_code = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
            idx += 4

            session_payload = b""
            if len(raw) >= idx + 4:
                sid_len = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
                if 0 < sid_len <= 512 and len(raw) >= idx + 4 + sid_len + 4:
                    idx += 4 + sid_len
                    session_payload = raw[idx:]

            if session_payload:
                if len(session_payload) < 4:
                    raise DoubaoTTSException("invalid frame: missing payload size")
                payload_size = int.from_bytes(session_payload[0:4], byteorder="big", signed=False)
                payload = session_payload[4 : 4 + payload_size]
                return msg_type, flags, serialization, compression, event_code, payload

            if len(raw) < idx + 4:
                raise DoubaoTTSException("invalid frame: missing payload size")
            payload_size = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
            idx += 4
            payload = raw[idx : idx + payload_size]
            return msg_type, flags, serialization, compression, event_code, payload

        if len(raw) < idx + 4:
            raise DoubaoTTSException("invalid frame: missing payload size")
        payload_size = int.from_bytes(raw[idx : idx + 4], byteorder="big", signed=False)
        idx += 4
        payload = raw[idx : idx + payload_size]
        return msg_type, flags, serialization, compression, event_code, payload

    @staticmethod
    def _maybe_decompress(payload: bytes, compression: int) -> bytes:
        if not payload:
            return payload
        # 0b0000: none, 0b0001: gzip
        if compression == 0x1:
            try:
                return gzip.decompress(payload)
            except Exception as e:  # noqa: BLE001
                raise DoubaoTTSException("gzip decompress failed") from e
        return payload

    def submit(self, ssml: str, voice: str) -> str:
        # Doc uses Access Token (X-Api-Access-Key). secret_key is not required for this websocket API,
        # but we keep it for compatibility with other Volcengine auth styles.
        if not (self.cfg.app_id and self.cfg.access_key):
            raise DoubaoTTSException(
                "Doubao TTS not configured: set DOUBAO_APP_ID and DOUBAO_ACCESS_KEY (access token)"
            )

        task_id = str(uuid.uuid4())
        text = self._strip_ssml(ssml)
        if not text:
            raise DoubaoTTSException("empty ssml/text")

        req: Dict[str, Any] = {
            "input_id": task_id,
            "action": 0,
            "input_text": text,
            "use_head_music": False,
            "use_tail_music": False,
            "aigc_watermark": False,
            "audio_config": {"format": "mp3", "sample_rate": 24000, "speech_rate": 0},
            "audio_params": {"format": "mp3", "sample_rate": 24000, "speech_rate": 0},
            "input_info": {"return_audio_url": True},
        }

        if voice and "," in voice:
            parts = [p.strip() for p in voice.split(",") if p.strip()]
            if len(parts) == 2:
                req["speaker_info"] = {"random_order": True, "speakers": parts}

        headers = self._ws_headers()
        header_list = [f"{k}: {v}" for k, v in headers.items()]

        try:
            ws = websocket.create_connection(self._ws_url(), header=header_list, timeout=self.timeout_seconds)
            ws.settimeout(self.timeout_seconds)
        except Exception as e:  # noqa: BLE001
            raise DoubaoTTSException("Doubao websocket connect failed") from e

        payload_bytes = json.dumps(req, ensure_ascii=False).encode("utf-8")
        ws.send(
            self._build_event_frame(
                message_type=0x9,
                flags=0x4,
                serialization=0x1,
                compression=0x0,
                event_code=1,
                session_id=task_id,
                payload=payload_bytes,
            ),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )

        self._conns[task_id] = ws
        self._payloads[task_id] = req
        return task_id

    def poll(self, task_id: str, max_wait_seconds: int = 600, interval_seconds: int = 3) -> bytes:
        if not task_id:
            raise DoubaoTTSException("task_id is empty")

        ws = self._conns.get(task_id)
        if ws is None:
            raise DoubaoTTSException("unknown task_id in current process; submit() and poll() must run together")

        deadline = time.time() + max_wait_seconds
        audio_chunks: list[bytes] = []
        last_json: Optional[Dict[str, Any]] = None

        try:
            while time.time() < deadline:
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    time.sleep(interval_seconds)
                    continue

                if raw is None:
                    break
                if isinstance(raw, str):
                    raw = raw.encode("utf-8")

                msg_type, flags, serialization, _compression, event, payload = self._parse_frame(raw)

                if msg_type == 0xF:
                    err_code = event
                    payload2 = self._maybe_decompress(payload, _compression)
                    msg = payload2.decode("utf-8", errors="ignore") if payload2 else ""
                    raise DoubaoTTSException(f"Doubao error frame code={err_code} msg={msg}")

                if event == 361 and payload:
                    audio_chunks.append(payload)
                    continue

                if serialization == 0x0 and payload:
                    audio_chunks.append(payload)
                    continue

                if serialization == 0x1 and payload:
                    payload2 = self._maybe_decompress(payload, _compression)
                    try:
                        obj = json.loads(payload2.decode("utf-8"))
                    except Exception:
                        obj = {"raw": payload2.decode("utf-8", errors="ignore")}
                    last_json = obj if isinstance(obj, dict) else {"data": obj}

                    # PodcastEnd may contain meta_info.audio_url
                    if event == 363:
                        meta = (last_json.get("meta_info") or {}) if isinstance(last_json, dict) else {}
                        audio_url = (meta.get("audio_url") or "").strip() if isinstance(meta, dict) else ""
                        if audio_url:
                            a = requests.get(audio_url, timeout=self.timeout_seconds)
                            a.raise_for_status()
                            return a.content

                    continue

            if audio_chunks:
                return b"".join(audio_chunks)

            raise DoubaoTTSException(f"Doubao poll ended without audio (last={last_json})")
        finally:
            try:
                try:
                    ws.send(
                        self._build_event_frame(
                            message_type=0x9,
                            flags=0x4,
                            serialization=0x1,
                            compression=0x0,
                            event_code=2,
                            session_id=None,
                            payload=b"{}",
                        ),
                        opcode=websocket.ABNF.OPCODE_BINARY,
                    )
                except Exception:
                    pass

                try:
                    # Best-effort wait for ConnectionFinished (event=52)
                    end_deadline = time.time() + 2
                    while time.time() < end_deadline:
                        try:
                            raw2 = ws.recv()
                        except websocket.WebSocketTimeoutException:
                            break
                        if raw2 is None:
                            break
                        if isinstance(raw2, str):
                            raw2 = raw2.encode("utf-8")
                        try:
                            _mt, _fl, _ser, _cmp, ev2, _pl = self._parse_frame(raw2)
                        except Exception:
                            continue
                        if ev2 == 52:
                            break
                except Exception:
                    pass

                ws.close()
            except Exception:
                pass
            self._conns.pop(task_id, None)
            self._payloads.pop(task_id, None)
