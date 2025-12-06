"""
URM37 を UART1 経由で読み取ってターミナルに出力するサンプル。

配線例（Raspberry Pi Pico）:
  - Pico UART1 TX (GP4) -> URM37 RXD
  - Pico UART1 RX (GP5) -> URM37 TXD
  - 5V / GND はセンサ仕様に従って接続すること
"""

import time

from uart import UARTPort
import sys

# ensure lib directory is importable when running from project root on desktop
if "lib" not in sys.path:
    sys.path.append("lib")

from urm37 import URM37


def create_sensor(
    port: int = 1,
    tx: int = 4,
    rx: int = 5,
    baudrate: int = 9600,
    timeout_ms: int = 200,
    measurement_timeout_ms: int = 120,
) -> URM37:
    """UART1 + URM37 のデフォルト構成でセンサインスタンスを生成する。"""
    uart = UARTPort(port=port, baudrate=baudrate, tx=tx, rx=rx, timeout_ms=timeout_ms)
    return URM37(uart, measurement_timeout_ms=measurement_timeout_ms)


def read_distance_and_temperature(sensor: URM37):
    """URM37 から距離(cm)と温度(°C)を1回読み出す。"""
    dist = sensor.measure_distance_cm()
    temp = sensor.read_temperature_c()
    return dist, temp


def main() -> None:
    # UART1 を使用。配線に合わせて tx/rx ピン番号を変更してください。
    sensor = create_sensor(port=1, tx=4, rx=5)

    while True:
        dist, temp = read_distance_and_temperature(sensor)
        print("distance:", dist, "cm", "| temp:", temp, "C")
        time.sleep(1)


if __name__ == "__main__":
    main()
