import asyncio
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, ensure_directories
from .gcode_parser import GCodeParser
from .grbl_client import SpindleShim
from .machine import MachineController
from .models import (
    FileInfo,
    JobRequest,
    JogRequest,
    MachineState,
    Preview,
    Tool,
    ToolCreate,
    ToolUpdate,
    WorkOffset,
)
from .storage import FileStore, ToolStore

ensure_directories()

files = FileStore(Config.gcode_dir)
tools = ToolStore(Config.db_path)
parser = GCodeParser()
controller = MachineController(files=files, tools=tools, parser=parser, vfd=None, vacuum=None)  # type: ignore

try:
    from .io import VFDController, VacuumController
except Exception:
    VFDController = None  # type: ignore
    VacuumController = None  # type: ignore

if VFDController:
    controller.vfd = VFDController()
    controller.spindle = SpindleShim(controller.vfd)
if VacuumController:
    controller.vacuum = VacuumController()

router = APIRouter(prefix="/api")


def get_controller() -> MachineController:
    return controller


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/files", response_model=list[FileInfo])
def list_files(store: FileStore = Depends(lambda: files)):
    return store.list_files()


@router.post("/files", response_model=FileInfo)
async def upload_file(upload: UploadFile = File(...), store: FileStore = Depends(lambda: files)):
    data = await upload.read()
    path = store.save_file(upload.filename, data)
    stat = path.stat()
    return FileInfo(name=path.name, size=stat.st_size, mtime=stat.st_mtime)


@router.delete("/files/{filename}")
def delete_file(filename: str, store: FileStore = Depends(lambda: files)):
    deleted = store.delete(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"deleted": filename}


@router.get("/files/{filename}/preview", response_model=Preview)
def preview_file(filename: str, store: FileStore = Depends(lambda: files)):
    path = store.path_for(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return parser.parse_file(path)


@router.get("/files/{filename}/raw")
def download_file(filename: str, store: FileStore = Depends(lambda: files)):
    path = store.path_for(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@router.get("/tools", response_model=list[Tool])
def list_tools(store: ToolStore = Depends(lambda: tools)):
    return store.list_tools()


@router.post("/tools", response_model=Tool)
def create_tool(payload: ToolCreate, store: ToolStore = Depends(lambda: tools)):
    return store.add_tool(payload)


@router.put("/tools/{tool_id}", response_model=Tool)
def update_tool(tool_id: int, payload: ToolUpdate, store: ToolStore = Depends(lambda: tools)):
    tool = store.update_tool(tool_id, payload)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, store: ToolStore = Depends(lambda: tools)):
    ok = store.delete_tool(tool_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"deleted": tool_id}


@router.post("/job/start")
def start_job(request: JobRequest, mc: MachineController = Depends(get_controller)):
    try:
        mc.start_job(request)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except RuntimeError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return {"started": request.filename}


@router.post("/job/pause")
def pause_job(mc: MachineController = Depends(get_controller)):
    mc.pause()
    return {"status": mc.snapshot().status}


@router.post("/job/resume")
def resume_job(mc: MachineController = Depends(get_controller)):
    mc.resume()
    return {"status": mc.snapshot().status}


@router.post("/job/stop")
def stop_job(mc: MachineController = Depends(get_controller)):
    mc.stop()
    return {"status": mc.snapshot().status}


@router.post("/job/home")
def home(mc: MachineController = Depends(get_controller)):
    mc.home()
    return {"status": mc.snapshot().status}


@router.post("/workoffset")
def set_work_offset(offset: WorkOffset, mc: MachineController = Depends(get_controller)):
    mc.set_work_offset(offset)
    return mc.snapshot().work_offset


@router.post("/jog")
def jog(payload: JogRequest, mc: MachineController = Depends(get_controller)):
    try:
        mc.jog(payload.axis, payload.delta, payload.feed)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return mc.snapshot()


@router.get("/state", response_model=MachineState)
def state(mc: MachineController = Depends(get_controller)):
    return mc.snapshot()


app = FastAPI(title="CNC Controller")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
async def startup():
    if not Config.simulation:
        controller.connect()


@app.websocket(Config.websocket_path)
async def websocket_endpoint(ws: WebSocket, mc: MachineController = Depends(get_controller)):
    await ws.accept()
    try:
        while True:
            await ws.send_json({"state": mc.snapshot().dict()})
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return


dist_dir = Config.base_dir / "web" / "dist"
ui_dir = dist_dir if dist_dir.exists() else Config.base_dir / "web"
if ui_dir.exists():
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
