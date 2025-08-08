import argparse
import time
from typing import Optional, Tuple

import cv2
import dxcam
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

# --- Windows window-finder (opcjonalnie dla przechwytywania okna) ---
try:
    import win32gui
except ImportError:
    win32gui = None


def find_window_rect(title_substring: str) -> Optional[Tuple[int, int, int, int]]:
    """Zwraca (left, top, right, bottom) pierwszego widocznego okna,
    którego tytuł zawiera podany fragment (case-insensitive)."""
    if win32gui is None:
        return None

    target = {"rect": None, "needle": title_substring.lower()}

    def enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title and target["needle"] in title.lower():
            rect = win32gui.GetWindowRect(hwnd)  # (l,t,r,b)
            target["rect"] = rect

    win32gui.EnumWindows(enum_handler, None)
    return target["rect"]


def build_app(camera, region, fps, scale, quality):
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return f"""
        <!doctype html>
        <html><head><meta charset="utf-8"><title>Screen Stream</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          body {{ margin:0; background:#111; color:#ddd; font-family:system-ui; }}
          header {{ padding:10px; }}
          img {{ max-width:100%; height:auto; display:block; margin:auto; }}
          .meta {{ opacity:.7; font-size:14px }}
        </style></head>
        <body>
        <header>
          <div>Streaming: <b>{'region ' + str(region) if region else 'full screen'}</b>,
          FPS={fps}, JPEG Q={quality}, scale={scale}</div>
          <div class="meta">Upewnij się, że okno nie jest zminimalizowane (dla trybu okna).</div>
        </header>
        <img src="/stream.mjpg" alt="screen"/>
        </body></html>
        """

    def frame_generator():
        period = 1.0 / fps if fps > 0 else 0
        boundary = b"--frame\r\n"
        while True:
            t0 = time.time()
            frame = camera.grab(region=region)  # BGRA
            if frame is None:
                continue
            # BGRA -> BGR
            frame = frame[:, :, :3]

            if scale and scale != 1.0:
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

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
    parser.add_argument("--window", type=str, default="", help="Fragment tytułu okna do przechwycenia")
    args = parser.parse_args()

    # Inicjalizacja DXCAM
    camera = dxcam.create(output_idx=args.monitor, max_buffer_len=16)

    region = None
    if args.window:
        rect = find_window_rect(args.window)
        if rect:
            # DXCAM używa (l, t, r, b)
            region = rect
            print(f"[INFO] Przechwytywanie okna: '{args.window}' -> region={region}")
        else:
            print(f"[WARN] Nie znaleziono okna zawierającego: '{args.window}'. Przechwytywanie pełnego ekranu.")

    app = build_app(camera, region, args.fps, args.scale, args.quality)
    print(f"[INFO] Start na http://{args.host}:{args.port}  (otwórz w LAN: http://IP_WIN:{args.port})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
