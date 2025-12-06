"""
Lightweight UART helper that works on both MicroPython and desktop Python.

On MicroPython it wraps `machine.UART`. On desktop it falls back to a mock
implementation so the rest of the code can be exercised without hardware.
"""

import time

try:
    from typing import Optional  # type: ignore
except ImportError:  # MicroPython など typing が無い環境
    Optional = None  # type: ignore

try:
    from machine import UART as MachineUART, Pin as MachinePin
except ImportError:
    MachineUART = None  # Desktop Pythonなど、machineが存在しない環境用
    MachinePin = None


def _ticks_ms() -> int:
    """Return current time in milliseconds (MicroPython or CPython)."""
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()  # type: ignore[attr-defined]
    return int(time.time() * 1000)


def _ticks_diff(a: int, b: int) -> int:
    """Return the signed difference between two millisecond ticks."""
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(a, b)  # type: ignore[attr-defined]
    return a - b


def _sleep_ms(ms: int) -> None:
    """Sleep in milliseconds (MicroPython or CPython)."""
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)  # type: ignore[attr-defined]
    else:
        time.sleep(ms / 1000.0)


class UARTPort:
    """
    UART wrapper.

    Parameters
    ----------
    port : int
        UARTポート番号（Picoでは0または1）
    baudrate : int
        ボーレート。URM37は9600bpsがデフォルト
    tx, rx : optional
        ピン番号。MicroPythonのUART初期化に渡される
    timeout_ms : int
        読み取りタイムアウト（ミリ秒）
    """

    def __init__(
        self,
        port: int = 0,
        baudrate: int = 9600,
        tx=None,
        rx=None,
        timeout_ms: int = 200,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.tx = tx
        self.rx = rx
        self.timeout_ms = timeout_ms

        self._use_mock = MachineUART is None
        self._uart = None

    def open(self) -> None:
        """Open the UART port if it is not already open."""
        if self._uart is not None:
            return

        if self._use_mock:
            # モック：接続の有無は気にしない
            print(f"[mock] open UART{self.port} baud={self.baudrate} tx={self.tx} rx={self.rx}")
            self._uart = True  # sentinel for "opened"
            return

        kwargs = {"baudrate": self.baudrate}
        if self.tx is not None:
            if MachinePin is not None and isinstance(self.tx, int):
                kwargs["tx"] = MachinePin(self.tx)
            else:
                kwargs["tx"] = self.tx
        if self.rx is not None:
            if MachinePin is not None and isinstance(self.rx, int):
                kwargs["rx"] = MachinePin(self.rx)
            else:
                kwargs["rx"] = self.rx

        self._uart = MachineUART(self.port, **kwargs)

    def write(self, data: bytes) -> int:
        """Write bytes to UART."""
        if self._uart is None:
            self.open()

        if self._use_mock:
            print(f"[mock] UART write: {data.hex()}")
            return len(data)

        return self._uart.write(data)

    def read(self, size: int = 1, timeout_ms=None) -> bytes:
        """
        Read up to `size` bytes.

        Polls until `size` bytes are received or the timeout elapses.
        """
        if self._uart is None:
            self.open()

        if self._use_mock:
            # Return empty to simulate "no hardware response"
            print(f"[mock] UART read request: {size} bytes (timeout {timeout_ms or self.timeout_ms} ms)")
            return b""

        effective_timeout = timeout_ms if timeout_ms is not None else self.timeout_ms
        deadline = _ticks_ms() + effective_timeout
        chunks = bytearray()

        while len(chunks) < size and _ticks_diff(deadline, _ticks_ms()) > 0:
            remaining = size - len(chunks)
            incoming = self._uart.read(remaining)
            if incoming:
                chunks.extend(incoming)
                continue
            _sleep_ms(2)

        return bytes(chunks)

    def close(self) -> None:
        """Close the UART port (if supported)."""
        if self._uart is None:
            return

        if self._use_mock:
            print(f"[mock] close UART{self.port}")
            self._uart = None
            return

        if hasattr(self._uart, "deinit"):
            self._uart.deinit()
        self._uart = None

    def __enter__(self) -> "UARTPort":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()


# Backward compatibility for code importing `uart` in lowercase
uart = UARTPort
