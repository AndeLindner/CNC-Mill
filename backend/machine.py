import asyncio
import threading
import time
from pathlib import Path
from typing import List, Optional

from .gcode_parser import GCodeParser
from .grbl_client import GrblClient, SpindleShim
from .io import VacuumController, VFDController
from .models import (
    JobRequest,
    MachineState,
    MachineStatus,
    SpindleDirection,
    Tool,
    WorkOffset,
)
from .storage import FileStore, ToolStore


class NoopVFD:
    def set_direction(self, *_):
        pass

    def set_voltage(self, *_):
        pass


class NoopVacuum:
    def set_state(self, *_):
        pass


class SimpleMoveTracker:
    def __init__(self):
        self.position = [0.0, 0.0, 0.0]
        self.absolute = True

    def consume(self, line: str) -> List[float]:
        code = line.upper()
        if "G90" in code:
            self.absolute = True
        if "G91" in code:
            self.absolute = False
        if code.startswith("G0") or code.startswith("G1"):
            target = list(self.position)
            tokens = code.split()
            for tok in tokens:
                if tok.startswith("X"):
                    target[0] = float(tok[1:]) if self.absolute else self.position[0] + float(tok[1:])
                if tok.startswith("Y"):
                    target[1] = float(tok[1:]) if self.absolute else self.position[1] + float(tok[1:])
                if tok.startswith("Z"):
                    target[2] = float(tok[1:]) if self.absolute else self.position[2] + float(tok[1:])
            self.position = target
        return self.position


class MachineController:
    def __init__(
        self,
        files: FileStore,
        tools: ToolStore,
        parser: GCodeParser,
        vfd: Optional[VFDController],
        vacuum: Optional[VacuumController],
    ):
        self.files = files
        self.tools = tools
        self.parser = parser
        self.vfd = vfd or NoopVFD()
        self.vacuum = vacuum or NoopVacuum()
        self.grbl = GrblClient(on_status=self._ingest_status)
        self.spindle = SpindleShim(self.vfd)
        self.state = MachineState(status=MachineStatus.idle)
        self._lock = threading.Lock()
        self._job_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._move_tracker = SimpleMoveTracker()

    def connect(self) -> None:
        self.grbl.connect()

    def _ingest_status(self, payload: dict) -> None:
        with self._lock:
            if "status" in payload:
                self.state.status = MachineStatus(payload["status"])
            if "machine_pos" in payload:
                self.state.machine_pos = payload["machine_pos"]
            if "feed_rate" in payload:
                self.state.feed_rate = payload["feed_rate"]
            if "spindle_rpm" in payload:
                self.state.spindle_rpm = payload["spindle_rpm"]
            if "work_offset" in payload:
                w = payload["work_offset"]
                self.state.work_offset = WorkOffset(x=w[0], y=w[1], z=w[2])

    def snapshot(self) -> MachineState:
        with self._lock:
            return MachineState(**self.state.dict())

    def set_tool(self, tool_id: Optional[int]) -> Optional[Tool]:
        tool = self.tools.get_tool(tool_id) if tool_id else None
        with self._lock:
            self.state.tool = tool
        return tool

    def start_job(self, request: JobRequest) -> None:
        path = self.files.path_for(request.filename)
        if not path.exists():
            raise FileNotFoundError(request.filename)
        with self._lock:
            if self.state.status in {MachineStatus.running, MachineStatus.paused}:
                raise RuntimeError("Job already running")
            self.state.status = MachineStatus.running
            self.state.job_file = request.filename
            self.state.current_line = 0
            self.state.total_lines = self.files.line_count(request.filename)
        tool = self.set_tool(request.tool_id)
        if tool:
            with self._lock:
                self.state.spindle_rpm = tool.rpm
                self.state.spindle_dir = tool.direction
            self.spindle.apply(tool.rpm, tool.direction)
        self.vacuum.set_state(True)
        self._stop_flag.clear()
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        self._move_tracker = SimpleMoveTracker()
        self._job_thread = threading.Thread(target=self._run_job, args=(lines,), daemon=True)
        self._job_thread.start()

    def _run_job(self, lines: List[str]) -> None:
        for idx, raw in enumerate(lines, start=1):
            if self._stop_flag.is_set():
                break
            while True:
                with self._lock:
                    if self._stop_flag.is_set():
                        break
                    paused = self.state.status == MachineStatus.paused
                if not paused:
                    break
                time.sleep(0.05)
            if self._stop_flag.is_set():
                break
            line = raw.strip()
            if not line:
                continue
            self._handle_spindle_tokens(line)
            if self.grbl.connected:
                self.grbl.send_line(line)
            else:
                new_pos = self._move_tracker.consume(line)
                with self._lock:
                    self.state.machine_pos = new_pos
                    self.state.current_line = idx
                    continue
            with self._lock:
                self.state.current_line = idx
            time.sleep(0.002)
        with self._lock:
            if self._stop_flag.is_set():
                self.state.status = MachineStatus.stopped
            else:
                self.state.status = MachineStatus.complete
        time.sleep(0.5)
        self.vacuum.set_state(False)

    def pause(self) -> None:
        if self.grbl.connected:
            self.grbl.realtime_command("!")
        with self._lock:
            if self.state.status == MachineStatus.running:
                self.state.status = MachineStatus.paused

    def resume(self) -> None:
        if self.grbl.connected:
            self.grbl.realtime_command("~")
        with self._lock:
            if self.state.status == MachineStatus.paused:
                self.state.status = MachineStatus.running

    def stop(self) -> None:
        self._stop_flag.set()
        if self.grbl.connected:
            self.grbl.realtime_command("\x18")
        with self._lock:
            self.state.status = MachineStatus.stopped

    def home(self) -> None:
        if self.grbl.connected:
            self.grbl.send_line("$H")
        with self._lock:
            self.state.status = MachineStatus.homing

    def set_work_offset(self, offset: WorkOffset) -> None:
        with self._lock:
            self.state.work_offset = offset
        if self.grbl.connected:
            cmd = f"G10 L20 P1 X{offset.x} Y{offset.y} Z{offset.z}"
            self.grbl.send_line(cmd)

    def jog(self, axis: str, delta: float, feed: float = 500.0) -> None:
        axis_norm = axis.upper()
        if axis_norm not in {"X", "Y", "Z"}:
            raise ValueError("Invalid axis")
        if self.grbl.connected:
            cmd = f"$J=G91 {axis_norm}{delta:.3f} F{feed:.1f}"
            self.grbl.send_line(cmd)
            return
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis_norm]
        with self._lock:
            pos = list(self.state.machine_pos)
            pos[axis_idx] += delta
            self.state.machine_pos = pos

    def _handle_spindle_tokens(self, line: str) -> None:
        code = line.upper()
        direction = None
        if "M3" in code:
            direction = SpindleDirection.cw
        elif "M4" in code:
            direction = SpindleDirection.ccw
        elif "M5" in code:
            direction = SpindleDirection.off
        rpm = None
        if "S" in code:
            try:
                token = [t for t in code.split() if t.startswith("S")][0]
                rpm = float(token[1:])
            except Exception:
                rpm = None
        with self._lock:
            if rpm is not None:
                self.state.spindle_rpm = rpm
            if direction:
                self.state.spindle_dir = direction
        self.spindle.apply(self.state.spindle_rpm, self.state.spindle_dir)
