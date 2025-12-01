import threading
import time
from queue import Queue, Empty
from typing import Callable, Optional

from .config import Config
from .models import MachineStatus, SpindleDirection

try:
    import serial
except Exception:
    serial = None


class GrblClient:
    def __init__(self, on_status: Optional[Callable[[dict], None]] = None):
        self.port = Config.serial_port
        self.baud = Config.serial_baud
        self.ser = None
        self.connected = False
        self._rx_thread = None
        self._tx_thread = None
        self._tx_queue: Queue[str] = Queue()
        self._running = False
        self._on_status = on_status

    def connect(self) -> None:
        if Config.simulation:
            return
        if not serial:
            return
        if self.connected:
            return
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
        self.connected = True
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        self._rx_thread.start()
        self._tx_thread.start()
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\n")
        self.ser.flush()

    def close(self) -> None:
        self._running = False
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.connected = False

    def send_line(self, line: str) -> None:
        if not self.connected or not self.ser:
            return
        self._tx_queue.put(line.strip() + "\n")

    def realtime_command(self, code: str) -> None:
        if not self.connected or not self.ser:
            return
        try:
            self.ser.write(code.encode())
            self.ser.flush()
        except Exception:
            self.close()

    def request_status(self) -> None:
        self.realtime_command("?")

    def _rx_loop(self) -> None:
        while self._running and self.ser:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
            except Exception:
                self.close()
                break
            if not line:
                continue
            if line.startswith("<") and self._on_status:
                parsed = self._parse_status(line)
                self._on_status(parsed)

    def _tx_loop(self) -> None:
        while self._running and self.ser:
            try:
                line = self._tx_queue.get(timeout=0.1)
            except Empty:
                continue
            try:
                self.ser.write(line.encode())
                self.ser.flush()
            except Exception:
                self.close()
                break

    def _parse_status(self, status_line: str) -> dict:
        # Example: <Idle|MPos:0.000,0.000,0.000|FS:0,0|WCO:0.000,0.000,0.000>
        raw = status_line.strip("<>").split("|")
        payload = {"status": MachineStatus.idle.value}
        for token in raw:
            if token in ("Idle", "Run", "Hold", "Alarm", "Home"):
                payload["status"] = {
                    "Idle": MachineStatus.idle.value,
                    "Run": MachineStatus.running.value,
                    "Hold": MachineStatus.paused.value,
                    "Home": MachineStatus.homing.value,
                    "Alarm": MachineStatus.alarm.value,
                }.get(token, MachineStatus.idle.value)
            if token.startswith("MPos:"):
                coords = token.split(":")[1].split(",")
                payload["machine_pos"] = [float(c) for c in coords]
            if token.startswith("WCO:"):
                coords = token.split(":")[1].split(",")
                payload["work_offset"] = [float(c) for c in coords]
            if token.startswith("FS:"):
                vals = token.split(":")[1].split(",")
                payload["feed_rate"] = float(vals[0])
                payload["spindle_rpm"] = float(vals[1])
            if token.startswith("Ov:"):
                pass
        return payload


class SpindleShim:
    def __init__(self, vfd):
        self.vfd = vfd

    def apply(self, rpm: float, direction: SpindleDirection, max_rpm: float = 24000.0):
        max_rpm = Config.spindle_max_rpm
        min_rpm = Config.spindle_min_rpm
        rpm_clamped = min(max(rpm, min_rpm), max_rpm)
        volts = rpm_clamped / max_rpm * Config.dac_vref
        self.vfd.set_direction(direction)
        self.vfd.set_voltage(volts)
