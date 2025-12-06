"""
URM37 V3.2 超音波センサ（シリアルモード）用ドライバ。

本ドライバは UART 通信で距離・温度を取得する最小限の機能を提供する。
MicroPython では `machine.UART` を、デスクトップ Python では `uart.UARTPort`
のモック実装を介して動作する。
"""

# MicroPython には typing が無いので ImportError を無視する
try:
    from typing import Optional  # type: ignore
except ImportError:
    Optional = None  # type: ignore

from uart import UARTPort


class URM37Error(Exception):
    """URM37 通信に関する例外。"""


class URM37:
    """
    URM37 センサを UART 経由で制御するラッパー。

    Parameters
    ----------
    uart : UARTPort
        事前に初期化済みの UARTPort インスタンス
    measurement_timeout_ms : int
        距離計測レスポンス待ち時間（ミリ秒）
    """

    CMD_DISTANCE = 0x22
    CMD_TEMPERATURE = 0x11
    FRAME_LENGTH = 4

    def __init__(self, uart: UARTPort, measurement_timeout_ms: int = 120) -> None:
        self.uart = uart
        self.measurement_timeout_ms = measurement_timeout_ms

    def measure_distance_cm(self):
        """
        距離をセンチメートル単位で取得。

        Returns
        -------
        int | None
            距離 [cm]。応答が無い場合は None。
        """
        self._send_command(self.CMD_DISTANCE)
        raw = self.uart.read(self.FRAME_LENGTH, timeout_ms=self.measurement_timeout_ms)
        if len(raw) != self.FRAME_LENGTH:
            return None

        value = self._parse_frame(raw, expected_cmd=self.CMD_DISTANCE)
        return value

    def read_temperature_c(self):
        """
        内蔵温度センサ値を摂氏で取得。

        Returns
        -------
        float | None
            温度 [°C]。応答が無い場合は None。
        """
        self._send_command(self.CMD_TEMPERATURE)
        raw = self.uart.read(self.FRAME_LENGTH, timeout_ms=self.measurement_timeout_ms)
        if len(raw) != self.FRAME_LENGTH:
            return None

        value = self._parse_frame(raw, expected_cmd=self.CMD_TEMPERATURE)
        if value is None:
            return None
        return value / 10.0

    def _send_command(self, command: int) -> None:
        """URM37 へ 4 バイトのコマンドフレームを送信。"""
        checksum = (command + 0x00 + 0x00) & 0xFF
        frame = bytes([command, 0x00, 0x00, checksum])
        self.uart.write(frame)

    @staticmethod
    def _parse_frame(frame: bytes, expected_cmd: int):
        """
        受信フレームを解析し、値を返す。

        Returns
        -------
        int | None
            パース成功時は値、コマンド不一致やチェックサム不正時は None。
        """
        if len(frame) != URM37.FRAME_LENGTH:
            return None

        cmd, high, low, checksum = frame
        if cmd != expected_cmd:
            return None

        if ((cmd + high + low) & 0xFF) != checksum:
            return None

        return (high << 8) | low


# Backward compatibility for code importing `urm37` in lowercase
urm37 = URM37
