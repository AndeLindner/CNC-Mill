# CNC-Mill
3-axis wood CNC with Raspberry Pi 4 as host/UI and Arduino Uno (GRBL) as realtime motion controller. Four Nema 23 steppers with TB6600 drivers, four inductive sensors, VFD spindle control, and vacuum relay.

## Hardware map
- Mechanics: Y has 2×1500 mm ball screws (5 mm pitch) with two motors and sensors front; X 1500 mm (5 mm) with sensor right; Z 250 mm (10 mm) with sensor top.
- Arduino Uno I/O:
  - D13 Y1 limit, D12 Y2 limit, D3 X limit, D2 Z limit
  - D11 Y1 dir, D10 Y1 step, D9 Y2 dir, D8 Y2 step
  - D7 X dir, D6 X step, D5 Z dir, D4 Z step
- Raspberry Pi 4 I/O:
  - USB -> Arduino
  - I2C SDA/SCL -> DAC (0–5 V spindle reference)
  - GPIO17 forward to VFD, GPIO27 reverse to VFD, GPIO22 relay for vacuum

## Firmware
- Use GRBL 1.1h on the Uno with a custom `cpu_map` for the pinout above. Keep planner/jerk/feed conservative for wood.
- Dual Y on Uno: share Y1/Y2 step/dir and series-wire both Y limits to the single Y limit input for homing. For independent squaring, move to grblHAL on a roomier MCU.
- Endstop levels: match inductive sensors (NPN/PNP) to 5 V logic with proper pull-ups/downs; shield long runs.
- Spindle commands (M3/M4/M5/S) are driven from the Pi to the VFD; GRBL spindle outputs can stay unused in the custom map.

## Software (implemented)
- Backend (`backend/app.py`): FastAPI + WebSocket. Handles G-code upload/list/download, tool database (SQLite), GRBL serial bridge, job control (start/pause/resume/stop/home), work offset setter, and state reporting. Streams state over `/ws` for the UI.
- Machine control (`backend/machine.py`): job streamer with GRBL realtime commands, spindle shim mapping S/M3/M4/M5 to VFD (DAC + GPIO), vacuum relay control, and simulated motion if no GRBL is connected.
- G-code preview (`backend/gcode_parser.py`): parses G0/G1 moves into segments for 3D visualization.
- Frontend (`web/`): static Three.js UI with file manager/upload, tool selector, start/pause/resume/stop, homing, work-offset setter, live status, and 3D path viewer with live position marker and cutter diameter overlay.

## Layout
- `backend/` Python backend
  - `app.py` FastAPI entrypoint
  - `machine.py` job control, spindle/vacuum hooks
  - `grbl_client.py` serial bridge + status parser
  - `gcode_parser.py` preview segments
  - `storage.py` tool DB (SQLite) and G-code file store
  - `io.py` VFD (GPIO/I2C DAC) and vacuum relay drivers
  - `config.py` paths, pins, defaults
  - `requirements.txt` backend dependencies
- `web/` static UI (Three.js viewer, controls)
- `data/` runtime assets (created on first run): `gcode/` files, `tools.db` SQLite

## Configuration (pins/interfaces)
- Raspberry Pi pins: set via env vars or edit `backend/config.py`
  - `GPIO_FORWARD` (default 17), `GPIO_REVERSE` (27), `GPIO_VACUUM` (22)
  - `I2C_BUS` (default 1), `DAC_ADDRESS` (default 0x60), `DAC_VREF` (default 5.0 V)
- Spindle RPM scaling: `SPINDLE_MAX_RPM` (default 24000), `SPINDLE_MIN_RPM` (default 0)
- GRBL serial: `GRBL_PORT` (default `/dev/ttyUSB0`), `GRBL_BAUD` (default 115200)
- Arduino pin map (for your custom GRBL `cpu_map`, informational in `backend/config.py`):
  - Limits: Y1 D13, Y2 D12, X D3, Z D2
  - Step: Y1 D10, Y2 D8, X D6, Z D4
  - Dir: Y1 D11, Y2 D9, X D7, Z D5

## Backend setup (Pi or dev machine)
Prereqs: Python 3.11+, pip, virtualenv.
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r backend/requirements.txt

# optional: export GRBL_PORT=/dev/ttyUSB0 GRBL_BAUD=115200 GPIO_FORWARD=17 ...
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
Runtime folders `data/`, `data/gcode/`, and `data/tools.db` are created automatically.  
UI options:
- Dev: run Vite as below (`npm run dev`) and open `http://localhost:5173`.
- Serve from backend: build once with `npm run build` (see below), then open `http://localhost:8000`.

## Frontend dev (local)
Prereqs: Node 18+ and npm.
```bash
cd web
npm install
npm run dev   # Vite dev server on http://localhost:5173 with proxy to backend:8000
```
During dev, the UI proxies `/api` and `/ws` to the backend. Start the backend first. Live reload is enabled by Vite.

### Frontend build for serving via backend
```bash
cd web
npm run build   # outputs web/dist
# then start backend normally; it will serve web/dist if present
```

## Using the UI
- Upload/select a G-code file, select a tool, and Start. Preview renders the path; live position updates via WebSocket.
- Pause/Resume/Stop and Home map to GRBL realtime commands when connected.
- Work offset form sends `G10 L20 P1` when GRBL is present; otherwise it updates the simulated state.
- Tool form stores tooling (name, diameter, length, rpm, feed, direction, climb) in SQLite and updates the cutter overlay.

## Flash GRBL with the custom map
- Clone GRBL 1.1h, add a `cpu_map` matching the Arduino pins listed above, and build/flash to the Uno.
- Set steps/mm for 5 mm (X/Y) and 10 mm (Z) pitch with your microstepping (e.g., `$100/$101/$102`).
- Enable homing `$22=1`, set homing dir/seek/feed, set soft limits `$20=1` after verifying travel.

## Safety and wiring
- Hardware E-Stop is required; cut driver/VFD enables in hardware.
- Common ground between Pi/Arduino/DAC/VFD analog reference; consider optocouplers for GPIO to VFD and relay.
- RC filter on the DAC output for a stable 0–5 V reference; verify VFD input impedance and scaling.
- EMI: shield motor/endstop lines, separate power and signal routing, add ferrites near the controllers.

## Next steps
- Add the custom GRBL `cpu_map` file into this repo for repeatable builds.
- Implement feed/spindle overrides, probing macros, and optional remote/video.
- If dual-Y squaring is required, migrate to grblHAL-capable hardware.
