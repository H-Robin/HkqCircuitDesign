"""
URM37 の距離を読み出し、成功時に LED を点灯するエントリーポイント。
"""

import time

from led import LED
from main_urm37 import create_sensor, read_distance_and_temperature


def main() -> None:
    status_led = LED(gpio_no=15)
    status_led.ledinit()

    # UART1 デフォルト配線 (TX=GP4, RX=GP5) を想定。必要に応じて変更してください。
    sensor = create_sensor(port=1, tx=4, rx=5)

    try:
        while True:
            dist, temp = read_distance_and_temperature(sensor)

            if dist is not None:
                status_led.ledon()
            else:
                status_led.ledoff()

            print("distance:", dist, "cm", "| temp:", temp, "C")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        status_led.cleanup()


if __name__ == "__main__":
    main()
