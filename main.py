"""
URM37 の距離を読み出し、成功時に LED を点灯するエントリーポイント。
"""

import time

from led import LED
from main_urm37 import create_sensor, read_distance_and_temperature


def main() -> None:
    # 各色LEDの GPIO を指定。配線に合わせて変更してください。
    leds = {
        "white": LED(gpio_no=11),
        "red": LED(gpio_no=12),
        "blue": LED(gpio_no=15),
        "green": LED(gpio_no=13),
        "yellow": LED(gpio_no=14),
    }
    for led in leds.values():
        led.ledinit()

    # UART1 デフォルト配線 (TX=GP4, RX=GP5) を想定。必要に応じて変更してください。
    sensor = create_sensor(port=1, tx=4, rx=5)

    # 距離しきい値 [cm]。近→遠の順で評価する。
    # 10cm以内: 白 / 60cm以内: 赤 / 1m以内: 黄 / 1.5m以内: 緑 / 2m以内: 青
    bands = [
        (10, "white"),
        (60, "red"),
        (100, "yellow"),
        (150, "green"),
        (200, "blue"),
    ]
    # 2mより遠い場合は消灯
    default_color = None

    # センサの応答を素早く反映させるため、ポーリング間隔を短くする
    poll_interval_s = 0.1

    def set_color(color: str | None) -> None:
        """指定色のみ点灯させる。color=None で全消灯。"""
        for name, led in leds.items():
            if color is not None and name == color:
                led.ledon()
            else:
                led.ledoff()

    try:
        while True:
            dist, temp = read_distance_and_temperature(sensor)

            if dist is None:
                # センサ応答が無いときは全消灯
                set_color(color="none")
            else:
                for threshold, color in bands:
                    if dist <= threshold:
                        set_color(color)
                        break
                else:
                    set_color(default_color)

            print("distance:", dist, "cm", "| temp:", temp, "C")
            time.sleep(poll_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        for led in leds.values():
            led.cleanup()


if __name__ == "__main__":
    main()
