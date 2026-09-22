#!/opt/optolink/venv/bin/python
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone

APP_DIR = "/opt/optolink"
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from c_settings_adapter import settings  # type: ignore
from homeassistant_publish import connect_mqtt  # type: ignore

STATE_DIR = "/var/lib/optolink-party"
STATE_FILE = os.path.join(STATE_DIR, "state.json")

ADDR_MODE = 0x2323
ADDR_NORMAL_SETPOINT = 0x2306
ADDR_PARTY_STATE = 0x2303
ADDR_PARTY_SETPOINT = 0x2308
ADDR_PARTY_LIMIT = 0x27F2

POLL_NATIVE_SECONDS = 3.0
POLL_EMULATION_SYNC_SECONDS = 3.0
REQUEST_TIMEOUT = 5.0


def log(message):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def utc_iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class PartyEmulator:
    def __init__(self):
        if not getattr(settings, "mqtt_broker", None):
            raise RuntimeError("MQTT is disabled in settings_ini.py")
        if not getattr(settings, "mqtt_listen", None):
            raise RuntimeError("mqtt_listen is disabled")
        if not getattr(settings, "mqtt_respond", None):
            raise RuntimeError("mqtt_respond is disabled")
        if not getattr(settings, "mqtt_topic", None):
            raise RuntimeError("mqtt_topic is not configured")

        self.base_topic = settings.mqtt_topic.rstrip("/")
        self.command_topic = f"{self.base_topic}/party_emulation/set"
        self.state_topic = f"{self.base_topic}/party_emulation/state"
        self.status_topic = f"{self.base_topic}/party_emulation/status"

        self.client = None
        self.actions = queue.Queue()
        self.response_cond = threading.Condition()
        self.response_seq = 0
        self.responses = []
        self.native_party = 0
        self.last_published_state = None
        self.stop_event = threading.Event()
        self.state = self.load_state()

    def load_state(self):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if data.get("version") != 1:
                raise ValueError("unsupported state version")
            return data
        except FileNotFoundError:
            return {"version": 1, "active": False}
        except Exception as exc:
            log(f"WARNING: cannot read {STATE_FILE}: {exc}")
            return {"version": 1, "active": False, "state_error": str(exc)}

    def save_state(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(self.state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, STATE_FILE)

    def clear_emulation_state(self):
        self.state = {"version": 1, "active": False}
        self.save_state()

    def on_message(self, client, userdata, message):
        payload = message.payload.decode(errors="replace").strip()
        if message.topic == settings.mqtt_respond:
            with self.response_cond:
                self.response_seq += 1
                self.responses.append((self.response_seq, payload))
                if len(self.responses) > 100:
                    self.responses = self.responses[-100:]
                self.response_cond.notify_all()
            return

        if message.topic == self.command_topic:
            value = payload.lower()
            if value in ("1", "on", "true", "ein"):
                self.actions.put(("set", 1))
            elif value in ("0", "off", "false", "aus"):
                self.actions.put(("set", 0))
            else:
                log(f"WARNING: ignoring invalid Party command payload: {payload!r}")

    def connect(self):
        self.client = connect_mqtt(retries=10, delay=3)
        if self.client is None:
            raise RuntimeError("MQTT connection failed")
        self.client.on_message = self.on_message
        self.client.subscribe(
            [
                (settings.mqtt_respond, 0),
                (self.command_topic, 0),
            ]
        )
        time.sleep(0.5)
        log(
            f"listening on {self.command_topic}; state={self.state_topic}; "
            f"Optolink commands={settings.mqtt_listen}"
        )

    @staticmethod
    def response_addr(response):
        parts = response.split(";")
        if len(parts) < 2:
            return None
        try:
            return int(parts[1], 0)
        except ValueError:
            return None

    def request(self, command, expected_addr, timeout=REQUEST_TIMEOUT):
        with self.response_cond:
            start_seq = self.response_seq

        log(f"TX {command}")
        self.client.publish(settings.mqtt_listen, command).wait_for_publish()
        deadline = time.monotonic() + timeout

        with self.response_cond:
            while True:
                for seq, response in self.responses:
                    if seq <= start_seq:
                        continue
                    if self.response_addr(response) == expected_addr:
                        log(f"RX {response}")
                        return response
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"timeout waiting for 0x{expected_addr:04X} after {command}"
                    )
                self.response_cond.wait(timeout=remaining)

    @staticmethod
    def response_value(response):
        parts = response.split(";")
        if len(parts) < 3:
            raise RuntimeError(f"malformed Optolink response: {response}")
        if parts[0] != "1":
            raise RuntimeError(f"Optolink request failed: {response}")
        try:
            return int(parts[2], 0)
        except ValueError:
            return int(parts[2])

    def read_int(self, addr, length=1):
        response = self.request(
            f"r;0x{addr:04X};{length};1;False",
            expected_addr=addr,
        )
        return self.response_value(response)

    def write_int(self, addr, length, value):
        response = self.request(
            f"w;0x{addr:04X};{length};{value}",
            expected_addr=addr,
        )
        self.response_value(response)

    def verified_write(self, addr, length, value):
        self.write_int(addr, length, value)
        last = None
        for delay in (0.35, 0.9, 1.8):
            time.sleep(delay)
            last = self.read_int(addr, length)
            if last == value:
                return
        raise RuntimeError(
            f"verification failed for 0x{addr:04X}: expected {value}, got {last}"
        )

    def publish_status(self):
        combined = 1 if self.state.get("active") or self.native_party == 1 else 0
        if combined != self.last_published_state:
            self.client.publish(self.state_topic, str(combined), retain=True)
            self.last_published_state = combined
            log(f"published Party state {combined}")

        status = {
            "active": bool(self.state.get("active")),
            "native_party": int(self.native_party),
            "combined_state": combined,
            "mode": "emulated"
            if self.state.get("active")
            else ("native" if self.native_party else "off"),
        }
        for key in (
            "previous_mode",
            "previous_normal_setpoint",
            "party_setpoint",
            "time_limit_hours",
            "started_at",
            "started_at_iso",
            "phase",
            "last_error",
        ):
            if key in self.state:
                status[key] = self.state[key]
        self.client.publish(
            self.status_topic, json.dumps(status, sort_keys=True), retain=True
        )

    def rollback_activation(self):
        errors = []
        try:
            if "previous_normal_setpoint" in self.state:
                self.verified_write(
                    ADDR_NORMAL_SETPOINT,
                    1,
                    int(self.state["previous_normal_setpoint"]),
                )
        except Exception as exc:
            errors.append(f"2306 restore: {exc}")
        try:
            if "previous_mode" in self.state:
                self.verified_write(ADDR_MODE, 1, int(self.state["previous_mode"]))
        except Exception as exc:
            errors.append(f"2323 restore: {exc}")
        if errors:
            raise RuntimeError("; ".join(errors))

    def activate(self):
        if self.state.get("active"):
            log("Party emulation already active")
            self.publish_status()
            return

        native = self.read_int(ADDR_PARTY_STATE)
        self.native_party = native
        if native == 1:
            log("native Party is already active; no emulation needed")
            self.publish_status()
            return

        previous_mode = self.read_int(ADDR_MODE)
        previous_normal = self.read_int(ADDR_NORMAL_SETPOINT)
        party_setpoint = self.read_int(ADDR_PARTY_SETPOINT)
        time_limit = self.read_int(ADDR_PARTY_LIMIT)
        started = time.time()

        self.state = {
            "version": 1,
            "active": True,
            "phase": "activating",
            "previous_mode": previous_mode,
            "previous_normal_setpoint": previous_normal,
            "party_setpoint": party_setpoint,
            "time_limit_hours": time_limit,
            "started_at": started,
            "started_at_iso": utc_iso(started),
        }
        self.save_state()

        try:
            if previous_normal != party_setpoint:
                self.verified_write(ADDR_NORMAL_SETPOINT, 1, party_setpoint)
            self.verified_write(ADDR_MODE, 1, 4)
            self.state["phase"] = "active"
            self.state.pop("last_error", None)
            self.save_state()
            log(
                "Party emulation active: "
                f"mode {previous_mode}->4, normal setpoint "
                f"{previous_normal}->{party_setpoint}, limit={time_limit}h"
            )
        except Exception as exc:
            self.state["phase"] = "error"
            self.state["last_error"] = str(exc)
            self.save_state()
            log(f"ERROR activating Party emulation: {exc}")
            try:
                self.rollback_activation()
                self.clear_emulation_state()
                log("activation rollback succeeded")
            except Exception as rollback_exc:
                self.state["last_error"] = (
                    f"activation failed: {exc}; rollback failed: {rollback_exc}"
                )
                self.save_state()
                log(f"ERROR rollback failed: {rollback_exc}")
            raise
        finally:
            self.publish_status()

    def restore_emulation(self):
        previous_normal = int(self.state["previous_normal_setpoint"])
        previous_mode = int(self.state["previous_mode"])
        self.state["phase"] = "restoring"
        self.save_state()

        self.verified_write(ADDR_NORMAL_SETPOINT, 1, previous_normal)
        self.verified_write(ADDR_MODE, 1, previous_mode)
        self.clear_emulation_state()
        log(
            "Party emulation restored: "
            f"normal setpoint={previous_normal}, mode={previous_mode}"
        )

    def deactivate(self, reason="user"):
        errors = []
        try:
            native = self.read_int(ADDR_PARTY_STATE)
            self.native_party = native
        except Exception as exc:
            errors.append(f"native state read: {exc}")

        if self.native_party == 1:
            try:
                self.verified_write(ADDR_PARTY_STATE, 1, 0)
                self.native_party = 0
                log("native Party switched off")
            except Exception as exc:
                errors.append(f"native Party off: {exc}")

        if self.state.get("active"):
            try:
                self.restore_emulation()
            except Exception as exc:
                self.state["phase"] = "error"
                self.state["last_error"] = f"restore failed ({reason}): {exc}"
                self.save_state()
                errors.append(f"emulation restore: {exc}")

        self.publish_status()
        if errors:
            raise RuntimeError("; ".join(errors))

    def recover_startup(self):
        if not self.state.get("active"):
            return

        log(f"recovering active Party emulation from {STATE_FILE}")
        limit = int(self.state.get("time_limit_hours", 0) or 0)
        started = float(self.state.get("started_at", 0) or 0)
        if (
            limit > 0
            and started > 0
            and time.time() >= started + limit * 3600
        ):
            log("stored Party emulation already exceeded its time limit; restoring")
            self.restore_emulation()
            return

        party_setpoint = self.read_int(ADDR_PARTY_SETPOINT)
        current_normal = self.read_int(ADDR_NORMAL_SETPOINT)
        current_mode = self.read_int(ADDR_MODE)
        if current_normal != party_setpoint:
            self.verified_write(ADDR_NORMAL_SETPOINT, 1, party_setpoint)
        if current_mode != 4:
            self.verified_write(ADDR_MODE, 1, 4)
        self.state["party_setpoint"] = party_setpoint
        self.state["phase"] = "active"
        self.state.pop("last_error", None)
        self.save_state()
        log("active Party emulation recovered")

    def sync_emulated_controls(self):
        if not self.state.get("active"):
            return

        target = self.read_int(ADDR_PARTY_SETPOINT)
        current_normal = self.read_int(ADDR_NORMAL_SETPOINT)
        current_mode = self.read_int(ADDR_MODE)

        old_party = int(self.state.get("party_setpoint", target))
        changed = False

        # If the normal setpoint is changed while synthetic Party is active,
        # remember the new value as the post-Party target, then immediately
        # re-apply the Party setpoint.  Do not mistake the old Party value for
        # a user normal-setpoint change when 0x2308 itself has just changed.
        if current_normal != target:
            if current_normal != old_party:
                old_normal = int(self.state["previous_normal_setpoint"])
                self.state["previous_normal_setpoint"] = current_normal
                changed = True
                log(
                    "normal setpoint changed during Party: "
                    f"restore target {old_normal}->{current_normal}"
                )
            self.verified_write(ADDR_NORMAL_SETPOINT, 1, target)

        if target != old_party:
            self.state["party_setpoint"] = target
            changed = True
            log(f"Party setpoint changed {old_party}->{target}; mirrored to 0x2306")

        # A mode change made while Party is active becomes the mode to restore
        # afterwards. Keep Dauernd Normal active until Party is switched off.
        if current_mode != 4:
            old_mode = int(self.state["previous_mode"])
            self.state["previous_mode"] = current_mode
            changed = True
            log(
                "operating mode changed during Party: "
                f"restore target {old_mode}->{current_mode}; re-applying mode 4"
            )
            self.verified_write(ADDR_MODE, 1, 4)

        if changed:
            self.save_state()

        # Keep the HA Party-temperature entity responsive even though the
        # splitter's complete poll cycle can take considerably longer.
        self.client.publish(
            f"{self.base_topic}/heizkreis_m1_raumsolltemperatur_party",
            str(target),
        )

    def check_timeout(self):
        if not self.state.get("active"):
            return
        limit = int(self.state.get("time_limit_hours", 0) or 0)
        started = float(self.state.get("started_at", 0) or 0)
        if (
            limit > 0
            and started > 0
            and time.time() >= started + limit * 3600
        ):
            log(f"Party emulation time limit reached ({limit}h)")
            self.deactivate(reason="timeout")

    def run(self):
        self.connect()
        try:
            self.recover_startup()
            try:
                self.native_party = self.read_int(ADDR_PARTY_STATE)
            except Exception as exc:
                log(f"WARNING: initial native Party read failed: {exc}")
            self.publish_status()

            next_native = 0.0
            next_setpoint = 0.0
            while not self.stop_event.is_set():
                try:
                    action, value = self.actions.get(timeout=0.25)
                    if action == "set":
                        try:
                            if value:
                                self.activate()
                            else:
                                self.deactivate()
                        except Exception as exc:
                            log(f"ERROR handling Party command {value}: {exc}")
                            self.publish_status()
                except queue.Empty:
                    pass

                now = time.monotonic()
                self.check_timeout()

                if now >= next_native:
                    try:
                        native = self.read_int(ADDR_PARTY_STATE)
                        if self.state.get("active") and native == 1:
                            # Synthetic Party leaves native 0x2303 off. If the
                            # physical Party button is pressed while emulation
                            # is active, 0x2303 becomes 1. Treat that single
                            # button press as an OFF request for the synthetic
                            # Party: clear the native request and restore the
                            # saved mode/setpoint.
                            log(
                                "native Party activation detected during "
                                "emulation; treating physical button as OFF"
                            )
                            self.native_party = 1
                            self.deactivate(reason="physical-button")
                            native = 0
                        if native != self.native_party:
                            log(
                                f"native Party state changed "
                                f"{self.native_party}->{native}"
                            )
                            self.native_party = native
                            self.publish_status()
                    except Exception as exc:
                        log(f"WARNING: native Party poll failed: {exc}")
                    next_native = now + POLL_NATIVE_SECONDS

                if self.state.get("active") and now >= next_setpoint:
                    try:
                        self.sync_emulated_controls()
                    except Exception as exc:
                        self.state["last_error"] = (
                            f"setpoint sync failed: {exc}"
                        )
                        self.save_state()
                        log(f"WARNING: Party setpoint sync failed: {exc}")
                        self.publish_status()
                    next_setpoint = now + POLL_EMULATION_SYNC_SECONDS
                elif not self.state.get("active"):
                    next_setpoint = now + POLL_EMULATION_SYNC_SECONDS
        finally:
            if self.client is not None:
                self.client.loop_stop()
                self.client.disconnect()


def main():
    emulator = PartyEmulator()
    emulator.run()


if __name__ == "__main__":
    main()
