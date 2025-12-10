"""
PC 側でシリアル経由のセンサー値を表示する簡易ビューア。

- マイコンがターミナルに出力している「distance: ... | temp: ...」の行を
  シリアルポート経由で受信し、ウィンドウで見やすく表示します。
- ポート指定が無い場合は stdin から読み取るので、既存ツールの出力を
  パイプで繋いで流し込むこともできます。
"""

import argparse
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

try:
    import serial  # type: ignore
except ImportError:  # pyserial が無い場合は後でエラーを表示
    serial = None  # type: ignore

# カラーパレット（少しネオン寄り）
BG_MAIN = "#0b1021"
CARD_BG = "#11182f"
ACCENT = "#00e5ff"
ACCENT_SOFT = "#6be6ff"
TEXT_MUTED = "#9fb3c8"
TEXT_RAW = "#7b89a6"
ERROR = "#ff6b6b"


def _parse_measurement(text: str):
    """
    1 行のテキストから distance / temp を抜き出す。

    Returns
    -------
    (dist, temp) or None
    """
    dist_match = re.search(r"distance:\s*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    temp_match = re.search(r"temp:\s*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not dist_match and not temp_match:
        return None

    def _to_number(m):
        if not m:
            return None
        try:
            val = float(m.group(1))
            if val.is_integer():
                return int(val)
            return val
        except ValueError:
            return None

    return _to_number(dist_match), _to_number(temp_match)


def _reader_from_serial(port: str, baudrate: int, out_queue: queue.Queue, stop_event: threading.Event):
    """シリアルポートから行単位で読み取ってキューへ流す。"""
    if serial is None:
        out_queue.put(("error", "pyserial がインストールされていません。`pip install pyserial` を実行してください。"))
        return

    try:
        ser = serial.Serial(port, baudrate=baudrate, timeout=1)
    except Exception as exc:  # pragma: no cover - 実機依存
        out_queue.put(("error", f"シリアルポートを開けませんでした: {exc}"))
        return

    with ser:
        out_queue.put(("status", f"接続中: {port} ({baudrate}bps)"))
        while not stop_event.is_set():  # pragma: no cover - 実機依存
            try:
                line = ser.readline()
            except Exception as exc:
                out_queue.put(("error", f"受信エラー: {exc}"))
                break

            if not line:
                continue

            out_queue.put(("data", line.decode(errors="replace").strip()))


def _reader_from_stdin(out_queue: queue.Queue, stop_event: threading.Event):
    """stdin から行単位で読み取り（パイプ入力用）。"""
    out_queue.put(("status", "stdin から受信中"))
    for line in sys.stdin:
        if stop_event.is_set():
            break
        out_queue.put(("data", line.strip()))


def _choose_font(available, candidates, size: int, weight: str = "normal"):
    """候補にある最初のフォントを返す。無ければ等幅系にフォールバック。"""
    for name in candidates:
        if name in available:
            return tkfont.Font(family=name, size=size, weight=weight)
    return tkfont.Font(family="Courier New", size=size, weight=weight)


def build_ui(root: tk.Tk):
    """ラベル類を生成して参照を返す。"""
    root.title("URM37 Monitor")
    root.geometry("1200x720")
    root.configure(padx=18, pady=18, bg=BG_MAIN)

    available = set(tkfont.families())
    title_font = _choose_font(
        available, ["SF Pro Display", "Avenir Next", "Avenir", "Futura", "Helvetica Neue"], 64, "bold"
    )
    value_font = _choose_font(
        available, ["JetBrains Mono", "Fira Code", "SF Mono", "Menlo", "Consolas", "Inconsolata"], 136, "bold"
    )
    caption_font = _choose_font(
        available, ["SF Pro Text", "Avenir Next", "Avenir", "Futura", "Helvetica Neue"], 48, "normal"
    )

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG_MAIN)
    style.configure("Card.TFrame", background=CARD_BG, relief="flat")
    style.configure("Value.TLabel", background=CARD_BG, foreground=ACCENT, font=value_font)
    style.configure("Caption.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=caption_font)
    style.configure("Status.TLabel", background=BG_MAIN, foreground=ACCENT_SOFT, font=caption_font)
    style.configure("Raw.TLabel", background=BG_MAIN, foreground=TEXT_RAW, font=caption_font)

    header = ttk.Label(root, text="URM37 LIVE FEED", style="Caption.TLabel", font=title_font)
    header.pack(anchor="w", pady=(0, 10))

    # 中央に左右2分割のコンテナを置く
    content = ttk.Frame(root, style="Card.TFrame", padding=(12, 12))
    content.pack(fill="both", expand=True)
    content.columnconfigure(0, weight=1, uniform="col")
    content.columnconfigure(1, weight=1, uniform="col")

    # 左カラム: これまでのカード
    card = ttk.Frame(content, style="Card.TFrame", padding=(16, 14))
    card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

    dist_caption = ttk.Label(card, text="Distance", style="Caption.TLabel")
    dist_label = ttk.Label(card, text="-- cm", style="Value.TLabel")
    temp_caption = ttk.Label(card, text="Temperature", style="Caption.TLabel")
    temp_label = ttk.Label(card, text="-- C", style="Value.TLabel")

    dist_caption.pack(anchor="w")
    dist_label.pack(anchor="w", pady=(0, 8))
    temp_caption.pack(anchor="w", pady=(4, 0))
    temp_label.pack(anchor="w", pady=(0, 4))

    # 右カラム: 距離バー＆スケール用キャンバス
    right = ttk.Frame(content, style="Card.TFrame", padding=(12, 12))
    right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
    canvas = tk.Canvas(right, width=200, height=400, bg=BG_MAIN, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # スケール描画用のヘルパー（20cm刻みで 0〜200cm）
    def draw_scale(event=None):
        canvas.delete("scale")
        max_dist = 200.0
        height = canvas.winfo_height() or 400
        width = canvas.winfo_width() or 200

        # モニター風フレームの定義（SF風の横長オペレーションモニターっぽく）
        inset = 10
        frame_left = inset
        frame_top = inset
        frame_right = width - inset
        frame_bottom = height - inset

        # 外枠（ネオンブルーのベゼル）
        canvas.create_rectangle(
            frame_left,
            frame_top,
            frame_right,
            frame_bottom,
            outline=ACCENT_SOFT,
            width=3,
            tags="scale",
        )
        # 上下左右に小さなパネル風の切り欠きを追加
        notch = 12
        canvas.create_line(frame_left, frame_top + notch, frame_left + notch, frame_top, fill=ACCENT_SOFT, width=3, tags="scale")
        canvas.create_line(frame_right - notch, frame_top, frame_right, frame_top + notch, fill=ACCENT_SOFT, width=3, tags="scale")
        canvas.create_line(frame_left, frame_bottom - notch, frame_left + notch, frame_bottom, fill=ACCENT_SOFT, width=3, tags="scale")
        canvas.create_line(frame_right - notch, frame_bottom, frame_right, frame_bottom - notch, fill=ACCENT_SOFT, width=3, tags="scale")

        # 内側スクリーン（暗めのパネル）
        canvas.create_rectangle(
            frame_left + 6,
            frame_top + 6,
            frame_right - 6,
            frame_bottom - 6,
            outline="#263454",
            fill=CARD_BG,
            width=2,
            tags="scale",
        )

        # スケール用のマージン（フレーム内側に収める）
        top_margin = frame_top + 20
        bottom_margin = frame_bottom - 20
        scale_left = frame_left + 56

        # 縦軸
        canvas.create_line(
            scale_left,
            top_margin,
            scale_left,
            bottom_margin,
            fill=TEXT_MUTED,
            width=1,
            tags="scale",
        )

        # 20cm ごとの目盛り（横に長く、薄い線）
        for dist in range(0, 201, 20):
            ratio = dist / max_dist
            # 0cm を下端、200cm を上端にする
            y = bottom_margin - ratio * (bottom_margin - top_margin)
            # 横方向のグリッド線
            canvas.create_line(
                scale_left,
                y,
                frame_right - 16,
                y,
                fill=TEXT_MUTED,
                width=1,
                tags="scale",
            )
            # ラベル（cm）
            canvas.create_text(
                scale_left - 12,
                y,
                text=str(dist),
                anchor="e",
                fill=TEXT_MUTED,
                tags="scale",
            )

        # 主目盛の間に 10cm ごとの副目盛を追加
        for dist in range(10, 200, 10):
            # 20cm 刻み（主目盛）は既に描画済みなのでスキップ
            if dist % 20 == 0:
                continue
            ratio = dist / max_dist
            # 0cm を下端、200cm を上端にする
            y = bottom_margin - ratio * (bottom_margin - top_margin)
            # 主目盛より短い横線（副目盛）を全長の点線に変更
            canvas.create_line(
                scale_left,
                y,
                frame_right - 16,
                y,
                fill=TEXT_MUTED,
                width=1,
                dash=(4, 4),
                tags="scale",
            )

    canvas.bind("<Configure>", draw_scale)
    canvas.after_idle(draw_scale)

    # 縦にスライドする小さめのバー
    initial_height = 400
    bar_width = 50
    bar_height = 80
    x0 = 200 / 2 - bar_width / 2
    x1 = 200 / 2 + bar_width / 2
    y0 = initial_height / 2 - bar_height / 2
    y1 = y0 + bar_height
    bar = canvas.create_rectangle(x0, y0, x1, y1, fill=ACCENT, width=0)

    return {
        "dist": dist_label,
        "temp": temp_label,
        "canvas": canvas,
        "bar": bar,
    }


def main():
    parser = argparse.ArgumentParser(description="シリアル出力の距離/温度を表示する GUI")
    parser.add_argument("--port", "-p", help="シリアルポート名 (例: COM3, /dev/ttyACM0)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="ボーレート (default: 115200)")
    parser.add_argument("--interval", "-i", type=float, default=0.1, help="UI 更新間隔 [秒]")
    args = parser.parse_args()

    q: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    reader = threading.Thread(
        target=_reader_from_serial if args.port else _reader_from_stdin,
        kwargs=(
            {"port": args.port, "baudrate": args.baud, "out_queue": q, "stop_event": stop_event}
            if args.port
            else {"out_queue": q, "stop_event": stop_event}
        ),
        daemon=True,
    )
    reader.start()

    root = tk.Tk()
    widgets = build_ui(root)

    state = {"dist": None, "temp": None, "dist_anim": 0.0}

    def update_bar():
        canvas = widgets["canvas"]
        bar = widgets["bar"]
        # 最大 2m をバーのフルスケールとする
        max_dist = 200.0  # cm

        if state["dist"] is None:
            target = 0.0
        else:
            target = max(0.0, min(float(state["dist"]), max_dist))

        cur = state["dist_anim"]
        # なめらかに追従させる（イージング）
        new = cur + (target - cur) * 0.2
        state["dist_anim"] = new

        # 0.0〜1.0 にクランプ（0cm = 下端, 200cm = 上端）
        ratio = new / max_dist if max_dist > 0 else 0.0
        if ratio < 0.0:
            ratio = 0.0
        elif ratio > 1.0:
            ratio = 1.0

        height = canvas.winfo_height() or 400
        width = canvas.winfo_width() or 200

        # draw_scale と同じ「モニター枠」＋スケール位置を使う
        inset = 12
        frame_left = inset
        frame_top = inset
        frame_right = width - inset
        frame_bottom = height - inset

        top_margin = frame_top + 16
        bottom_margin = frame_bottom - 16
        scale_left = frame_left + 56

        bar_height = 5
        x0 = scale_left + 8                 # 目盛りの少し右から
        x1 = frame_right - 16               # 内側スクリーンの右端手前までの長いバー

        # 距離に応じてバーの上下位置を決定（下: 0cm, 上: 200cm）
        # draw_scale と同じく、0cm を bottom_margin、200cm を top_margin にマッピング
        y_center = bottom_margin - ratio * (bottom_margin - top_margin)
        y0 = y_center - bar_height / 2
        y1 = y_center + bar_height / 2

        canvas.coords(bar, x0, y0, x1, y1)

        # 距離に応じて色を変化（LEDと同じしきい値に合わせる）
        # 白≤10, 赤≤60, 黄≤100, 緑≤150, それ以遠は青
        color_bands = [
            (10, "#ffffff"),
            (60, "#ff0000"),
            (100, "#ffd400"),
            (150, "#00ff00"),
        ]
        color = "#0000ff"  # デフォルト（遠い場合）
        if state["dist"] is not None:
            for threshold, c in color_bands:
                if state["dist"] <= threshold:
                    color = c
                    break
        canvas.itemconfig(bar, fill=color)

        # スケールやフレームより前面にバーを表示
        canvas.tag_raise(bar)

        root.after(30, update_bar)

    def update_ui():
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break

            if kind == "data":
                parsed = _parse_measurement(payload)
                if parsed:
                    dist, temp = parsed
                    if dist is not None:
                        state["dist"] = dist
                        widgets["dist"].config(text=f"{dist} cm")
                    if temp is not None:
                        state["temp"] = temp
                        widgets["temp"].config(text=f"{temp} C")
            # status / error 表示は行わない

        root.after(int(args.interval * 1000), update_ui)

    def on_close():
        stop_event.set()
        time.sleep(0.05)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    update_ui()
    # after_idle で初回を呼び出し、Canvasのサイズ確定後にアニメ開始
    root.after_idle(update_bar)
    root.mainloop()


if __name__ == "__main__":
    main()
