"""
Simple LED control helper.

For Raspberry Pi Pico / MicroPython, this class wraps `machine.Pin`.
If `machine` is not available (e.g. when running on desktop CPython),
it falls back to printing actions so the rest of the code can still run.
"""

try:
    from machine import Pin
except ImportError:
    Pin = None  # Desktop Pythonなど、machineが存在しない環境用

import time


class LED:
    def __init__(self, gpio_no: int):
        self.gpio_no = gpio_no
        self._initialized = False
        self._use_mock = Pin is None
        self._pin = None

    def ledinit(self) -> None:
        """初期化：MicroPythonではPinを生成、デスクトップではモック表示のみ。"""
        if self._initialized:
            return

        if self._use_mock:
            print(f"[mock] init LED on GPIO{self.gpio_no}")
        else:
            # Raspberry Pi Pico / MicroPython 用
            self._pin = Pin(self.gpio_no, Pin.OUT)

        self._initialized = True

    def ledon(self) -> None:
        """LED を点灯させる。"""
        if not self._initialized:
            self.ledinit()

        if self._use_mock:
            print(f"[mock] LED on (GPIO{self.gpio_no})")
            return

        self._pin.value(1)

    def ledoff(self) -> None:
        """LED を消灯させる。"""
        if not self._initialized:
            self.ledinit()

        if self._use_mock:
            print(f"[mock] LED off (GPIO{self.gpio_no})")
            return

        self._pin.value(0)

    def cleanup(self) -> None:
        """
        後処理用フック。

        MicroPython には RPi.GPIO のような `cleanup()` は不要なので、
        ここでは安全のため LED を消灯するだけにしている。
        """
        if self._use_mock:
            print(f"[mock] cleanup LED on GPIO{self.gpio_no}")
            return

        if self._pin is not None:
            self._pin.value(0)


# Backward compatibility for code importing `led` in lowercase
led = LED
