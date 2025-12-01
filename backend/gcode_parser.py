from pathlib import Path
from typing import List, Tuple

from .models import PathSegment, Preview


class GCodeParser:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.position = [0.0, 0.0, 0.0]
        self.absolute = True

    def parse_file(self, path: Path) -> Preview:
        self.reset()
        segments: List[PathSegment] = []
        bbox_min = [float("inf"), float("inf"), float("inf")]
        bbox_max = [float("-inf"), float("-inf"), float("-inf")]

        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.split(";")[0].split("(")[0].strip()
            if not line:
                continue
            code = line.upper()
            if "G90" in code:
                self.absolute = True
            if "G91" in code:
                self.absolute = False
            if code.startswith("G0") or code.startswith("G1"):
                rapid = code.startswith("G0")
                delta, new_pos = self._extract_move(code)
                start = list(self.position)
                end = new_pos
                self.position = new_pos
                for i in range(3):
                    bbox_min[i] = min(bbox_min[i], start[i], end[i])
                    bbox_max[i] = max(bbox_max[i], start[i], end[i])
                segments.append(PathSegment(start=start, end=end, rapid=rapid))
        if bbox_min[0] == float("inf"):
            bbox_min = [0.0, 0.0, 0.0]
            bbox_max = [0.0, 0.0, 0.0]
        return Preview(segments=segments, bbox_min=bbox_min, bbox_max=bbox_max)

    def _extract_move(self, line: str) -> Tuple[List[float], List[float]]:
        target = list(self.position)
        tokens = line.split()
        for tok in tokens:
            if tok.startswith("X"):
                target[0] = float(tok[1:]) if self.absolute else self.position[0] + float(tok[1:])
            if tok.startswith("Y"):
                target[1] = float(tok[1:]) if self.absolute else self.position[1] + float(tok[1:])
            if tok.startswith("Z"):
                target[2] = float(tok[1:]) if self.absolute else self.position[2] + float(tok[1:])
        return list(self.position), target
