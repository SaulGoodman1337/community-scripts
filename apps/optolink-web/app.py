from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from paho.mqtt import client as mqtt
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "datapoints.json"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    optolink_host = os.getenv("OPTOLINK_HOST", "192.168.1.10")
    optolink_port = int(os.getenv("OPTOLINK_PORT", "65234"))
    tcp_timeout = float(os.getenv("OPTOLINK_TCP_TIMEOUT", "3.0"))
    mqtt_host = os.getenv("MQTT_HOST", "").strip()
    mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    mqtt_user = os.getenv("MQTT_USER", "").strip()
    mqtt_password = os.getenv("MQTT_PASSWORD", "")
    mqtt_topic = os.getenv("MQTT_TOPIC", "openv").strip().strip("/") or "openv"
    allow_writes = env_bool("ALLOW_WRITES", False)


settings = Settings()


def load_datapoints() -> list[dict[str, Any]]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


DATAPOINTS = load_datapoints()
DP_BY_NAME = {item["name"]: item for item in DATAPOINTS}


class TcpClient:
    """Small request/response client for Optolink-Splitter TCP.

    It deliberately does not depend on a newline terminator. Older ViessData-compatible
    splitter setups may send replies without LF; newer upstream builds may append LF.
    """

    def request(self, command: str) -> str:
        deadline = time.monotonic() + settings.tcp_timeout
        chunks: list[bytes] = []
        with socket.create_connection(
            (settings.optolink_host, settings.optolink_port), timeout=settings.tcp_timeout
        ) as sock:
            sock.settimeout(0.20)
            sock.sendall((command.strip() + "\n").encode("utf-8"))
            last_data = time.monotonic()
            while time.monotonic() < deadline:
                try:
                    data = sock.recv(4096)
                    if not data:
                        break
                    chunks.append(data)
                    last_data = time.monotonic()
                    if b"\n" in data:
                        break
                except socket.timeout:
                    if chunks and time.monotonic() - last_data >= 0.15:
                        break
                    continue
        if not chunks:
            raise TimeoutError("No response from Optolink-Splitter")
        return b"".join(chunks).decode("utf-8", errors="replace").strip("\x00\r\n ")

    def read(self, address: int, length: int, scale: Any = None, signed: bool = False) -> dict[str, Any]:
        parts = ["read", f"0x{address:04x}", str(length)]
        if scale is not None:
            parts.extend([str(scale), str(bool(signed))])
        response = self.request(";".join(parts))
        fields = response.split(";", 2)
        if len(fields) != 3:
            raise ValueError(f"Unexpected splitter response: {response}")
        retcode, returned_address, value = fields
        return {
            "ok": retcode in {"1", "01"},
            "retcode": retcode,
            "address": returned_address,
            "value": value,
            "raw_response": response,
        }


tcp_client = TcpClient()


class MqttState:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.connected = False
        self.last_error: str | None = None
        self.client: mqtt.Client | None = None

    def start(self) -> None:
        if not settings.mqtt_host:
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="optolink-web")
        if settings.mqtt_user:
            client.username_pw_set(settings.mqtt_user, settings.mqtt_password)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        self.client = client
        try:
            client.connect_async(settings.mqtt_host, settings.mqtt_port, 30)
            client.loop_start()
        except Exception as exc:
            self.last_error = str(exc)

    def stop(self) -> None:
        if self.client:
            self.client.loop_stop()
            try:
                self.client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if int(reason_code) == 0:
            self.connected = True
            self.last_error = None
            client.subscribe(f"{settings.mqtt_topic}/#")
        else:
            self.connected = False
            self.last_error = f"MQTT connect reason: {reason_code}"

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any) -> None:
        self.connected = False

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        prefix = f"{settings.mqtt_topic}/"
        name = message.topic[len(prefix):] if message.topic.startswith(prefix) else message.topic
        if name.endswith("/set"):
            return
        payload = message.payload.decode("utf-8", errors="replace")
        with self.lock:
            self.values[name] = {"value": payload, "updated": time.time()}

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self.lock:
            return dict(self.values)

    def publish_set(self, name: str, value: str) -> None:
        if not self.client or not self.connected:
            raise RuntimeError("MQTT is not connected")
        info = self.client.publish(f"{settings.mqtt_topic}/{name}/set", value)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with rc={info.rc}")


mqtt_state = MqttState()


class WriteRequest(BaseModel):
    value: float | int | str


class RawReadRequest(BaseModel):
    address: str = Field(pattern=r"^(0x)?[0-9A-Fa-f]{1,4}$")
    length: int = Field(ge=1, le=64)
    scale: str | None = None
    signed: bool = False


app = FastAPI(title="Optolink Web", version="0.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def startup() -> None:
    mqtt_state.start()


@app.on_event("shutdown")
def shutdown() -> None:
    mqtt_state.stop()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"version": app.version},
    )


@app.get("/api/config")
def config() -> dict[str, Any]:
    return {
        "optolink_host": settings.optolink_host,
        "optolink_port": settings.optolink_port,
        "mqtt_enabled": bool(settings.mqtt_host),
        "mqtt_host": settings.mqtt_host or None,
        "mqtt_port": settings.mqtt_port if settings.mqtt_host else None,
        "mqtt_topic": settings.mqtt_topic,
        "allow_writes": settings.allow_writes,
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    tcp_ok = False
    tcp_error = None
    device = None
    try:
        result = await asyncio.to_thread(tcp_client.read, 0x00F8, 8, None, False)
        tcp_ok = result["ok"]
        device = result["value"] if result["ok"] else None
    except Exception as exc:
        tcp_error = str(exc)
    snapshot = mqtt_state.snapshot()
    latest = max((item["updated"] for item in snapshot.values()), default=None)
    return {
        "tcp": {"ok": tcp_ok, "error": tcp_error},
        "device_ident": device,
        "mqtt": {
            "configured": bool(settings.mqtt_host),
            "connected": mqtt_state.connected,
            "last_error": mqtt_state.last_error,
            "topic_count": len(snapshot),
            "last_message": latest,
        },
    }


@app.get("/api/datapoints")
def datapoints() -> dict[str, Any]:
    snapshot = mqtt_state.snapshot()
    items = []
    for definition in DATAPOINTS:
        item = dict(definition)
        state = snapshot.get(definition["name"])
        item["value"] = state["value"] if state else None
        item["updated"] = state["updated"] if state else None
        item["write_available"] = bool(
            settings.allow_writes and definition.get("writable") and settings.mqtt_host
        )
        items.append(item)
    return {"items": items, "extra_topics": sorted(set(snapshot) - set(DP_BY_NAME))}


@app.post("/api/datapoints/{name}/read")
async def read_datapoint(name: str) -> dict[str, Any]:
    definition = DP_BY_NAME.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail="Unknown datapoint")
    if definition.get("tcp_read") is False:
        raise HTTPException(status_code=400, detail="Direct TCP read is disabled for this derived datapoint")
    try:
        result = await asyncio.to_thread(
            tcp_client.read,
            int(definition["address"], 16),
            int(definition["length"]),
            definition.get("scale"),
            bool(definition.get("signed", False)),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result)
    return result


@app.post("/api/datapoints/{name}/write")
def write_datapoint(name: str, request: WriteRequest) -> dict[str, Any]:
    definition = DP_BY_NAME.get(name)
    if not definition:
        raise HTTPException(status_code=404, detail="Unknown datapoint")
    if not settings.allow_writes:
        raise HTTPException(status_code=403, detail="Writes are disabled by ALLOW_WRITES")
    if not definition.get("writable"):
        raise HTTPException(status_code=403, detail="Datapoint is not write-enabled")
    try:
        numeric = float(request.value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="This datapoint expects a numeric value") from exc
    minimum = definition.get("min")
    maximum = definition.get("max")
    if minimum is not None and numeric < float(minimum):
        raise HTTPException(status_code=400, detail=f"Value below minimum {minimum}")
    if maximum is not None and numeric > float(maximum):
        raise HTTPException(status_code=400, detail=f"Value above maximum {maximum}")
    try:
        mqtt_state.publish_set(name, str(request.value))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "topic": f"{settings.mqtt_topic}/{name}/set", "value": request.value}


@app.post("/api/raw/read")
async def raw_read(request: RawReadRequest) -> dict[str, Any]:
    address = int(request.address, 16)
    scale: Any = request.scale
    if scale is not None:
        try:
            scale = float(scale)
        except ValueError:
            pass
    try:
        return await asyncio.to_thread(tcp_client.read, address, request.length, scale, request.signed)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
