from dataclasses import dataclass
from typing import Optional

from .config import Config
from .models import SpindleDirection


def _gpio():
    try:
        import RPi.GPIO as GPIO
    except Exception:
        return None
    return GPIO


def _i2c():
    try:
        import smbus
    except Exception:
        return None
    return smbus


@dataclass
class VFDController:
    gpio_forward: int = Config.gpio_forward
    gpio_reverse: int = Config.gpio_reverse
    dac_address: int = Config.dac_address
    vref: float = Config.dac_vref
    _bus: Optional[object] = None
    _gpio: Optional[object] = None

    def __post_init__(self):
        self._gpio = _gpio()
        self._bus = _i2c().SMBus(Config.i2c_bus) if _i2c() else None
        if self._gpio:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setup(self.gpio_forward, self._gpio.OUT, initial=self._gpio.LOW)
            self._gpio.setup(self.gpio_reverse, self._gpio.OUT, initial=self._gpio.LOW)

    def set_direction(self, direction: SpindleDirection) -> None:
        if not self._gpio:
            return
        if direction == SpindleDirection.cw:
            self._gpio.output(self.gpio_forward, self._gpio.HIGH)
            self._gpio.output(self.gpio_reverse, self._gpio.LOW)
        elif direction == SpindleDirection.ccw:
            self._gpio.output(self.gpio_forward, self._gpio.LOW)
            self._gpio.output(self.gpio_reverse, self._gpio.HIGH)
        else:
            self._gpio.output(self.gpio_forward, self._gpio.LOW)
            self._gpio.output(self.gpio_reverse, self._gpio.LOW)

    def set_voltage(self, volts: float) -> None:
        if not self._bus:
            return
        volts = max(0.0, min(self.vref, volts))
        value = int((volts / self.vref) * 4095)
        data = [value >> 8, value & 0xFF]
        try:
            self._bus.write_i2c_block_data(self.dac_address, 0x00, data)
        except Exception:
            pass


@dataclass
class VacuumController:
    gpio_pin: int = Config.gpio_vacuum
    _gpio: Optional[object] = None

    def __post_init__(self):
        self._gpio = _gpio()
        if self._gpio:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setup(self.gpio_pin, self._gpio.OUT, initial=self._gpio.LOW)

    def set_state(self, on: bool) -> None:
        if not self._gpio:
            return
        self._gpio.output(self.gpio_pin, self._gpio.HIGH if on else self._gpio.LOW)
