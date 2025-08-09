import argparse
import time
from typing import Optional, Tuple, List

import cv2
import dxcam
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

# --- Desktop/Windows-only bits ---
import psutil
try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None


# ========== Narzędzia do pracy z oknami ==========
def _enum_top_windows() -> List[int]:
    out: List[int] = []
    if win32gui is None:
        return out
    def cb(h, _): out.append(h)
    win32gui.EnumWindows(cb, None)
    return out

def _is_candidate(hwnd: int) -> bool:
    if not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):  # zminimalizowane
        return False
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    return (r - l) > 0 and (b - t) > 0

def _get_info(hwnd: int):
    title = win32gui.GetWindowText(hwnd) or ""
    cls = win32gui.GetClassName(hwnd) or ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        pname = psutil.Process(pid).name()
    except Exception:
        pname = ""
    rect = win32gui.GetWindowRect(hwnd)
    return title, cls, pname, rect

def list_real_windows() -> List[tuple]:
    """Zwraca listę (hwnd, title, class, proc, rect) widocznych okien top-level."""
    if win32gui is None: return []
    out = []
    for h in _enum_top_windows():
        if not _is_candidate(h):
            continue
        title, cls, pname, rect = _get_info(h)
        if (rect[2]-rect[0]) > 0 and (rect[3]-rect[1]) > 0:
            out.append((h, title, cls, pname, rect))
    return out

def find_window_rect_advanced(title_substring=None, class_name=None, proc_name=None, use_active=False):
    """
    Zwraca (l, t, r, b) dla okna. Priorytet:
    1) use_active,
    2) proc_name (dokładne dopasowanie nazwy procesu, np. chrome.exe),
    3) class_name (dokładne dopasowanie klasy, np. Chrome_WidgetWin_1),
    4) title_substring (case-insensitive substring).
    """
    if win32gui is None:
        return None

    # 1) aktywne okno
    if use_active:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and _is_candidate(hwnd):
            _, _, _, rect = _get_info(hwnd)
            return rect

    # przygotuj kandydatów
    cand = list_real_windows()
    def norm(s): return (s or "").lower()

    # 2) po procesie
    if proc_name:
        p = norm(proc_name)
        for h, title, cls, pname, rect in cand:
            if norm(pname) == p:
                return rect

    # 3) po klasie
    if class_name:
        c = norm(class_name)
        for h, title, cls, pname, rect in cand:
            if norm(cls) == c:
                return rect

    # 4) po tytule (substring)
    if title_substring:
        needle = norm(title_substring)
        # najpierw preferuj największe okno z dopasowaniem tytułu
        best = None
        best_area = -1
        for h, title, cls, pname, rect in cand:
            if needle in norm(title):
                area = (rect[2]-rect[0]) * (rect[3]-rect[1])
                if area > best_area:
                    best_area = area
                    best = rect
        if best:
            return best

    return None


# ========== FastAPI / MJPEG ==========
def build_app(camera, region, fps, scale, quality):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"><title>Screen Stream</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ margin:0; background:#111; color:#ddd; font-family:system-ui; }}
    header {{ padding:10px; border-bottom:1px solid #222; }}
    img {{ max-width:100%; height:auto; display:block; margin:auto; }}
    .meta {{ opacity:.7; font-size:14px }}
    .pill {{ display:inline-block; background:#222; padding:2px 8px; border-radius:999px; margin-right:6px; }}
  </style>
</head>
<body>
<header>
  <div>
    <span class="pill">Mode: {'region ' + str(region) if region else 'full screen'}</span>
    <span class="pill">FPS={fps}</span>
    <span class="pill">JPEG Q={quality}</span>
    <span class="pill">scale={scale}</span>
  </div>
  <div class="meta">W trybie okna upewnij się, że okno jest widoczne (niezminimalizowane).</div>
</header>
<img src="/stream.mjpg" alt="screen"/>
</body>
</html>
        """

    def frame_generator():
        period = 1.0 / fps if fps > 0 else 0
        boundary = b"--frame\r\n"
        while True:
            t0 = time.time()
            frame = camera.grab(region=region)  # BGRA
            if frame is None:
                # zabezpieczenie: jeśli dxcam odda None, poczekaj chwilę
                time.sleep(0.01)
                continue

            # BGRA -> BGR
            frame = frame[:, :, :3]

            if scale and scale != 1.0:
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)

            # JPEG encode
            ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
            if not ok:
                continue

            payload = jpg.tobytes()
            yield boundary
            yield b"Content-Type: image/jpeg\r\n"
            yield f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
            yield payload
            yield b"\r\n"

            # throttle to target FPS
            if period > 0:
                dt = time.time() - t0
                if dt < period:
                    time.sleep(period - dt)

    @app.get("/stream.mjpg")
    def stream():
        return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app


def main():
    parser = argparse.ArgumentParser(description="LAN Screen Streamer (MJPEG)")
    parser.add_argument("--host", default="0.0.0.0", help="Adres nasłuchu (domyślnie 0.0.0.0)")
    parser.add_argument("--port", type=int, default=4321, help="Port HTTP (domyślnie 4321)")
    parser.add_argument("--monitor", type=int, default=0, help="Indeks monitora DXGI (domyślnie 0)")
    parser.add_argument("--fps", type=int, default=20, help="Docelowe FPS (domyślnie 20)")
    parser.add_argument("--quality", type=int, default=75, help="Jakość JPEG 1–100 (domyślnie 75)")
    parser.add_argument("--scale", type=float, default=1.0, help="Skala obrazu (np. 0.5 dla 50%)")

    # nowe tryby wyboru okna
    parser.add_argument("--window", type=str, default="", help="Fragment tytułu okna do przechwycenia")
    parser.add_argument("--window-class", type=str, default="", help="Dokładna nazwa klasy okna (np. Chrome_WidgetWin_1)")
    parser.add_argument("--window-proc", type=str, default="", help="Nazwa procesu (np. chrome.exe)")
    parser.add_argument("--window-active", action="store_true", help="Użyj aktualnie aktywnego okna")

    # diagnostyka
    parser.add_argument("--list-windows", action="store_true", help="Wypisz widoczne okna i zakończ")

    args = parser.parse_args()

    # diagnostyka i wyjście
    if args.list_windows:
        if win32gui is None:
            print("[ERR] Brak win32gui; zainstaluj pywin32.")
            return
        rows = list_real_windows()
        if not rows:
            print("[INFO] Brak widocznych okien (upewnij się, że coś jest otwarte i nie zminimalizowane).")
            return
        print("=== Widoczne okna top-level ===")
        for hwnd, title, cls, pname, rect in rows:
            print(f"hwnd={hwnd}  title='{title}'  class='{cls}'  proc='{pname}'  rect={rect}")
        return

    # Inicjalizacja DXCAM
    camera = dxcam.create(output_idx=args.monitor, max_buffer_len=16)

    # Wybór regionu okna
    region = None
    if args.window or args.window_class or args.window_proc or args.window_active:
        rect = find_window_rect_advanced(
            title_substring=args.window or None,
            class_name=args.window_class or None,
            proc_name=args.window_proc or None,
            use_active=args.window_active
        )
        if rect:
            region = rect
            print(f"[INFO] Przechwytywanie regionu okna: {region}")
        else:
            print(f"[WARN] Nie znaleziono okna dla parametrów: "
                  f"title='{args.window}', class='{args.window_class}', proc='{args.window_proc}', active={args.window_active}. "
                  "Przechwytywanie pełnego ekranu.")

    app = build_app(camera, region, args.fps, args.scale, args.quality)
    print(f"[INFO] Start: http://{args.host}:{args.port}  (LAN: http://IP_WIN:{args.port})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
