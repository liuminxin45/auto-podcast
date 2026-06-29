"""Local Python 3.13 LLM gateway for Electron and workflow callers."""

import argparse
import json
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from protocol.llm_client import DEFAULT_TEMPERATURE, DEFAULT_TIMEOUT, LLMClient, LLMError

GATEWAY_VERSION = "1"
SERVER_NAME = "PodFlowLLMGateway"
PROJECT_ERROR_STATUS = {
    "AUTH": HTTPStatus.UNAUTHORIZED,
    "RATE_LIMIT": HTTPStatus.TOO_MANY_REQUESTS,
    "TIMEOUT": HTTPStatus.GATEWAY_TIMEOUT,
    "NETWORK": HTTPStatus.BAD_GATEWAY,
    "PARSE": HTTPStatus.BAD_GATEWAY,
    "CONFIG": HTTPStatus.BAD_REQUEST,
    "PROVIDER": HTTPStatus.BAD_GATEWAY,
    "UNKNOWN": HTTPStatus.INTERNAL_SERVER_ERROR,
}


def _first(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _json_error(error: LLMError) -> dict[str, Any]:
    return {
        "error": {
            "message": str(error),
            "code": error.code,
            "details": error.details,
        }
    }


def _coerce_timeout(value: Any) -> int:
    if value is None:
        return DEFAULT_TIMEOUT
    try:
        return max(1, int(value))
    except (TypeError, ValueError) as error:
        raise LLMError("Invalid timeout", "CONFIG", details={"timeout": value}) from error


def _coerce_max_tokens(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(1, int(value))
    except (TypeError, ValueError) as error:
        raise LLMError("Invalid max_tokens", "CONFIG", details={"max_tokens": value}) from error


def _build_client(
    payload: dict[str, Any],
) -> tuple[LLMClient, int, int | None, list[dict[str, str]]]:
    api_base = _first(payload, "api_base", "apiBase", default="")
    api_key = _first(payload, "api_key", "apiKey", default="")
    model = _first(payload, "model", default="")
    messages = _first(payload, "messages", default=[])
    temperature = _first(payload, "temperature", default=DEFAULT_TEMPERATURE)
    timeout = _coerce_timeout(_first(payload, "timeout", default=DEFAULT_TIMEOUT))
    max_tokens = _coerce_max_tokens(_first(payload, "max_tokens", "maxTokens"))
    debug_mode = bool(_first(payload, "debug_mode", "debugMode", default=False))

    if not model:
        raise LLMError("Missing model", "CONFIG")
    if not isinstance(messages, list):
        raise LLMError(
            "messages must be a list", "CONFIG", details={"messages": type(messages).__name__}
        )

    client = LLMClient(
        api_base=api_base,
        api_key=api_key,
        model=model,
        temperature=float(temperature),
        debug_mode=debug_mode,
    )
    return client, timeout, max_tokens, messages


class LLMGatewayHandler(BaseHTTPRequestHandler):
    server_version = SERVER_NAME
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[LLMGateway] {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(
                {
                    "ok": True,
                    "service": SERVER_NAME,
                    "version": GATEWAY_VERSION,
                    "time": time.time(),
                }
            )
            return
        self._send_json(
            {"error": {"message": "Not found", "code": "UNKNOWN"}}, HTTPStatus.NOT_FOUND
        )

    def do_POST(self) -> None:
        route = self.path.split("?", 1)[0]
        try:
            payload = self._read_json()
            if route == "/models":
                self._handle_models(payload)
                return
            if route == "/chat/completions":
                self._handle_chat(payload)
                return
            self._send_json(
                {"error": {"message": "Not found", "code": "UNKNOWN"}}, HTTPStatus.NOT_FOUND
            )
        except LLMError as error:
            self._send_project_error(error)
        except Exception as error:
            self._send_project_error(LLMError(str(error), "UNKNOWN"))

    def _handle_models(self, payload: dict[str, Any]) -> None:
        api_base = _first(payload, "api_base", "apiBase", default="")
        api_key = _first(payload, "api_key", "apiKey", default="")
        timeout = _coerce_timeout(_first(payload, "timeout", default=DEFAULT_TIMEOUT))
        client = LLMClient(api_base=api_base, api_key=api_key, model="__models__")
        try:
            self._send_json(client.fetch_models(timeout=timeout))
        finally:
            client.__exit__(None, None, None)

    def _handle_chat(self, payload: dict[str, Any]) -> None:
        stream = bool(_first(payload, "stream", default=False))
        client, timeout, max_tokens, messages = _build_client(payload)
        try:
            if stream:
                self._send_stream(client, messages, timeout, max_tokens)
            else:
                response = client.call(messages, timeout=timeout, max_tokens=max_tokens)
                self._send_json(response)
        finally:
            client.__exit__(None, None, None)

    def _send_stream(
        self,
        client: LLMClient,
        messages: list[dict[str, str]],
        timeout: int,
        max_tokens: int | None,
    ) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            for chunk in client.stream(messages, timeout=timeout, max_tokens=max_tokens):
                self._write_sse(chunk)
            self._write_raw(b"data: [DONE]\n\n")
        except LLMError as error:
            self._write_sse(_json_error(error), event="error")
        finally:
            self.wfile.flush()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as error:
            raise LLMError(f"Invalid JSON body: {error}", "PARSE", details=raw[:200]) from error
        if not isinstance(data, dict):
            raise LLMError("JSON body must be an object", "CONFIG")
        return data

    def _send_project_error(self, error: LLMError) -> None:
        status = PROJECT_ERROR_STATUS.get(error.code, HTTPStatus.INTERNAL_SERVER_ERROR)
        self._send_json(_json_error(error), status)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write_raw(data)

    def _write_sse(self, payload: dict[str, Any], event: str | None = None) -> None:
        if event:
            self._write_raw(f"event: {event}\n".encode())
        data = json.dumps(payload, ensure_ascii=False)
        self._write_raw(f"data: {data}\n\n".encode())

    def _write_raw(self, data: bytes) -> None:
        self.wfile.write(data)
        self.wfile.flush()


def run(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), LLMGatewayHandler)
    actual_host, actual_port = server.server_address
    ready = {
        "host": actual_host,
        "port": actual_port,
        "baseUrl": f"http://{actual_host}:{actual_port}",
        "version": GATEWAY_VERSION,
    }
    print(f"LLM_GATEWAY_READY {json.dumps(ready, ensure_ascii=False)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PodFlow local LLM gateway.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
