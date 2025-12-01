from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SpindleDirection(str, Enum):
    cw = "CW"
    ccw = "CCW"
    off = "OFF"


class MachineStatus(str, Enum):
    idle = "Idle"
    running = "Running"
    paused = "Paused"
    homing = "Homing"
    alarm = "Alarm"
    stopped = "Stopped"
    complete = "Complete"


class ToolBase(BaseModel):
    name: str
    diameter_mm: float = Field(gt=0)
    length_mm: float = Field(gt=0)
    rpm: int = Field(gt=0)
    feed_mm_min: float = Field(gt=0)
    direction: SpindleDirection
    climb: bool = False


class Tool(ToolBase):
    id: int


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseModel):
    name: Optional[str] = None
    diameter_mm: Optional[float] = Field(default=None, gt=0)
    length_mm: Optional[float] = Field(default=None, gt=0)
    rpm: Optional[int] = Field(default=None, gt=0)
    feed_mm_min: Optional[float] = Field(default=None, gt=0)
    direction: Optional[SpindleDirection] = None
    climb: Optional[bool] = None


class FileInfo(BaseModel):
    name: str
    size: int
    mtime: float


class PathSegment(BaseModel):
    start: List[float]
    end: List[float]
    rapid: bool


class Preview(BaseModel):
    segments: List[PathSegment]
    bbox_min: List[float]
    bbox_max: List[float]


class JobRequest(BaseModel):
    filename: str
    tool_id: Optional[int] = None


class JogRequest(BaseModel):
    axis: str
    delta: float
    feed: float = Field(default=500, gt=0)


class WorkOffset(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


class MachineState(BaseModel):
    status: MachineStatus
    machine_pos: List[float] = [0, 0, 0]
    work_offset: WorkOffset = WorkOffset()
    feed_rate: float = 0
    spindle_rpm: float = 0
    spindle_dir: SpindleDirection = SpindleDirection.off
    tool: Optional[Tool] = None
    current_line: int = 0
    total_lines: int = 0
    job_file: Optional[str] = None
