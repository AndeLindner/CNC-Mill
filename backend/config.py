import os
from pathlib import Path


class Config:
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    gcode_dir = data_dir / "gcode"
    db_path = data_dir / "tools.db"

    simulation = os.getenv("SIMULATION", "0").lower() in {"1", "true", "yes", "on"}
    serial_port = os.getenv("GRBL_PORT", "/dev/ttyUSB0")
    serial_baud = int(os.getenv("GRBL_BAUD", "115200"))

    gpio_forward = int(os.getenv("GPIO_FORWARD", "17"))
    gpio_reverse = int(os.getenv("GPIO_REVERSE", "27"))
    gpio_vacuum = int(os.getenv("GPIO_VACUUM", "22"))
    i2c_bus = int(os.getenv("I2C_BUS", "1"))

    dac_address = int(os.getenv("DAC_ADDRESS", "0x60"), 16)
    dac_vref = float(os.getenv("DAC_VREF", "5.0"))

    spindle_max_rpm = float(os.getenv("SPINDLE_MAX_RPM", "24000"))
    spindle_min_rpm = float(os.getenv("SPINDLE_MIN_RPM", "0"))

    # Pi pin map (for easy re-mapping)
    pi_pins = {
        "vfd_forward_gpio": gpio_forward,
        "vfd_reverse_gpio": gpio_reverse,
        "vacuum_gpio": gpio_vacuum,
        "i2c_bus": i2c_bus,
        "dac_address": dac_address,
    }

    # Arduino GRBL pin map (for custom cpu_map, informational here)
    arduino_pins = {
        "limits": {"y1": "D13", "y2": "D12", "x": "D3", "z": "D2"},
        "step": {"y1": "D10", "y2": "D8", "x": "D6", "z": "D4"},
        "dir": {"y1": "D11", "y2": "D9", "x": "D7", "z": "D5"},
    }

    websocket_path = "/ws"


def ensure_directories() -> None:
    Config.data_dir.mkdir(parents=True, exist_ok=True)
    Config.gcode_dir.mkdir(parents=True, exist_ok=True)
