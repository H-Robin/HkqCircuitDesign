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

    card = ttk.Frame(root, style="Card.TFrame", padding=(16, 14))
    card.pack(fill="both", expand=True)

    dist_caption = ttk.Label(card, text="Distance", style="Caption.TLabel")
    dist_label = ttk.Label(card, text="-- cm", style="Value.TLabel")
    temp_caption = ttk.Label(card, text="Temperature", style="Caption.TLabel")
    temp_label = ttk.Label(card, text="-- C", style="Value.TLabel")

    dist_caption.pack(anchor="w")
    dist_label.pack(anchor="w", pady=(0, 8))
    temp_caption.pack(anchor="w", pady=(4, 0))
    temp_label.pack(anchor="w", pady=(0, 4))

    status_label = ttk.Label(root, text="待機中...", style="Status.TLabel")
    raw_label = ttk.Label(root, text="", style="Raw.TLabel", wraplength=1000, justify="left")

    status_label.pack(anchor="w", pady=(12, 4))
    raw_label.pack(anchor="w")

    return {
        "dist": dist_label,
        "temp": temp_label,
        "status": status_label,
        "raw": raw_label,
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

    state = {"dist": None, "temp": None}

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
                widgets["raw"].config(text=payload)
            elif kind == "status":
                widgets["status"].config(text=payload, foreground=ACCENT_SOFT)
            elif kind == "error":
                widgets["status"].config(text=payload, foreground=ERROR)

        root.after(int(args.interval * 1000), update_ui)

    def on_close():
        stop_event.set()
        time.sleep(0.05)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    update_ui()
    root.mainloop()


if __name__ == "__main__":
    main()
