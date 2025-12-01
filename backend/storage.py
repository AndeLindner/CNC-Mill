import os
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from .config import Config, ensure_directories
from .models import FileInfo, Tool, ToolCreate, ToolUpdate


class ToolStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_directories()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    diameter_mm REAL NOT NULL,
                    length_mm REAL NOT NULL,
                    rpm INTEGER NOT NULL,
                    feed_mm_min REAL NOT NULL,
                    direction TEXT NOT NULL,
                    climb INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def list_tools(self) -> List[Tool]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, diameter_mm, length_mm, rpm, feed_mm_min, direction, climb FROM tools ORDER BY id"
            ).fetchall()
        return [
            Tool(
                id=row[0],
                name=row[1],
                diameter_mm=row[2],
                length_mm=row[3],
                rpm=row[4],
                feed_mm_min=row[5],
                direction=row[6],
                climb=bool(row[7]),
            )
            for row in rows
        ]

    def add_tool(self, tool: ToolCreate) -> Tool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO tools (name, diameter_mm, length_mm, rpm, feed_mm_min, direction, climb)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool.name,
                    tool.diameter_mm,
                    tool.length_mm,
                    tool.rpm,
                    tool.feed_mm_min,
                    tool.direction.value if hasattr(tool.direction, "value") else tool.direction,
                    int(tool.climb),
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
        return Tool(id=new_id, **tool.dict())

    def update_tool(self, tool_id: int, update: ToolUpdate) -> Optional[Tool]:
        current = self.get_tool(tool_id)
        if not current:
            return None
        data = current.dict()
        for field, value in update.dict(exclude_none=True).items():
            data[field] = value if field != "direction" else value.value if hasattr(value, "value") else value
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE tools SET name=?, diameter_mm=?, length_mm=?, rpm=?, feed_mm_min=?, direction=?, climb=?
                WHERE id=?
                """,
                (
                    data["name"],
                    data["diameter_mm"],
                    data["length_mm"],
                    data["rpm"],
                    data["feed_mm_min"],
                    data["direction"],
                    int(data["climb"]),
                    tool_id,
                ),
            )
            conn.commit()
        return self.get_tool(tool_id)

    def delete_tool(self, tool_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM tools WHERE id=?", (tool_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_tool(self, tool_id: int) -> Optional[Tool]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, name, diameter_mm, length_mm, rpm, feed_mm_min, direction, climb FROM tools WHERE id=?",
                (tool_id,),
            ).fetchone()
        if not row:
            return None
        return Tool(
            id=row[0],
            name=row[1],
            diameter_mm=row[2],
            length_mm=row[3],
            rpm=row[4],
            feed_mm_min=row[5],
            direction=row[6],
            climb=bool(row[7]),
        )


class FileStore:
    def __init__(self, root: Path):
        self.root = root
        ensure_directories()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> List[FileInfo]:
        files: List[FileInfo] = []
        for entry in self.root.glob("*.gcode"):
            stat = entry.stat()
            files.append(FileInfo(name=entry.name, size=stat.st_size, mtime=stat.st_mtime))
        for entry in self.root.glob("*.nc"):
            stat = entry.stat()
            files.append(FileInfo(name=entry.name, size=stat.st_size, mtime=stat.st_mtime))
        return sorted(files, key=lambda f: f.name)

    def save_file(self, filename: str, data: bytes) -> Path:
        safe_name = os.path.basename(filename)
        target = self.root / safe_name
        with open(target, "wb") as f:
            f.write(data)
        return target

    def read_text(self, filename: str) -> str:
        path = self.root / filename
        if not path.exists():
            raise FileNotFoundError(filename)
        return path.read_text()

    def delete(self, filename: str) -> bool:
        path = self.root / filename
        if path.exists():
            path.unlink()
            return True
        return False

    def path_for(self, filename: str) -> Path:
        return self.root / filename

    def line_count(self, filename: str) -> int:
        path = self.path_for(filename)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
