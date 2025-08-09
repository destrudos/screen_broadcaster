# Screen Streamer (MJPEG) for Windows 11

Real‑time udostępnianie ekranu przez sieć lokalną (LAN) z użyciem Python + FastAPI + MJPEG.  
Działa w przeglądarce (Windows/macOS/Linux). Obsługuje **cały ekran** lub **pojedyncze okno** (aktywny/po tytule/klasie/procesie).

---

## Spis treści

- [Screen Streamer (MJPEG) for Windows 11](#screen-streamer-mjpeg-for-windows-11)
  - [Spis treści](#spis-treści)
  - [Funkcje](#funkcje)
  - [Wymagania](#wymagania)
  - [Instalacja](#instalacja)
  - [Szybki start](#szybki-start)
  - [Pełna lista opcji](#pełna-lista-opcji)
  - [Przykłady użycia](#przykłady-użycia)
  - [Diagnostyka okien](#diagnostyka-okien)
  - [Wydajność i strojenie](#wydajność-i-strojenie)
  - [Sieć i zapora](#sieć-i-zapora)
  - [Bezpieczeństwo](#bezpieczeństwo)
  - [Znane ograniczenia](#znane-ograniczenia)
  - [FAQ](#faq)
  - [Changelog](#changelog)
  - [Licencja](#licencja)

---

## Funkcje

- Stream MJPEG (`multipart/x-mixed-replace`) — działa w dowolnej nowoczesnej przeglądarce.
- Przechwytywanie:
  - **pełnego ekranu** (wybór monitora),
  - **pojedynczego okna**:
    - aktualnie aktywne okno,
    - po **fragmencie tytułu** (case‑insensitive),
    - po **klasie okna** (np. `Chrome_WidgetWin_1`),
    - po **nazwie procesu** (np. `chrome.exe`).
- Regulacja **FPS**, **jakości JPEG** i **skali** (redukcja pasma/CPU).
- Tryb diagnostyczny: **lista okien** (tytuł/klasa/proces/rect).
- Wielu klientów jednocześnie (każdy dostaje własny strumień).

---

## Wymagania

- Windows 10/11.
- GPU z obsługą DirectX 11+ (dla `dxcam`).
- Python 3.9+.
- Sieć lokalna z dostępem HTTP pomiędzy hostem a klientem.

---

## Instalacja

1. Skopiuj plik `screen_streamer.py` do katalogu roboczego.
2. Utwórz virtualenv i zainstaluj zależności:

~~~powershell
python -m venv venv
.\venv\Scripts\activate
pip install fastapi uvicorn[standard] dxcam opencv-python pywin32 psutil
~~~

---

## Szybki start

Uruchom serwer na Windows:

~~~powershell
python screen_streamer.py --host 0.0.0.0 --port 4321
~~~

Na komputerze klienckim (np. macOS) otwórz w przeglądarce:

Przykład: `http://192.168.1.199:4321`

---

## Pełna lista opcji

| Flaga                | Domyślnie  | Opis |
|----------------------|------------|------|
| `--host`             | `0.0.0.0`  | Adres nasłuchu HTTP. Użyj `0.0.0.0`, aby udostępnić w LAN. |
| `--port`             | `4321`     | Port HTTP serwera. |
| `--monitor`          | `0`        | Indeks monitora dla przechwytywania pełnego ekranu (0 = główny). Ignorowane, jeśli ustawiono przechwytywanie okna. |
| `--fps`              | `20`       | Docelowa liczba klatek na sekundę. |
| `--quality`          | `75`       | Jakość JPEG (1–100). Wyższa = lepsza jakość, większe pasmo. |
| `--scale`            | `1.0`      | Skala obrazu (np. `0.5` = 50% szer./wys.). |
| `--window`           | *(puste)*  | Fragment tytułu okna (wyszukiwanie case‑insensitive, substring). |
| `--window-class`     | *(puste)*  | Dokładna nazwa klasy okna (np. `Chrome_WidgetWin_1`). |
| `--window-proc`      | *(puste)*  | Dokładna nazwa procesu (np. `chrome.exe`, `Code.exe`). |
| `--window-active`    | *(flaga)*  | Użyj aktualnie aktywnego okna jako źródła. |
| `--list-windows`     | *(flaga)*  | Wypisz listę widocznych okien top‑level i zakończ program. |

**Priorytet wyboru okna**: `--window-active` → `--window-proc` → `--window-class` → `--window`.

---

## Przykłady użycia

**Pełny ekran, 30 FPS, skala 50%, jakość 80**
~~~powershell
python screen_streamer.py --fps 30 --scale 0.5 --quality 80
~~~

**Aktywne okno (najprostsze)**
~~~powershell
python screen_streamer.py --window-active
~~~

**Po nazwie procesu (stabilne dla Chrome/VSCode/UWP)**
~~~powershell
python screen_streamer.py --window-proc chrome.exe --fps 25
~~~

**Po klasie okna**
~~~powershell
python screen_streamer.py --window-class Chrome_WidgetWin_1
~~~

**Po fragmencie tytułu**
~~~powershell
python screen_streamer.py --window "YouTube"
~~~

**Inny monitor**
~~~powershell
python screen_streamer.py --monitor 1
~~~

---

## Diagnostyka okien

Wyświetl listę widocznych okien top‑level i ich parametry:

~~~powershell
python screen_streamer.py --list-windows
~~~

Przykładowy output:

`=== Widoczne okna top-level ===`

`hwnd=32986 title='YouTube - Google Chrome' class='Chrome_WidgetWin_1' proc='chrome.exe' rect=(100, 100, 1600, 900)
hwnd=48274 title='Visual Studio Code' class='Chrome_WidgetWin_1' proc='Code.exe' rect=(200, 150, 1800, 950)`

Użyj `title/class/proc` w odpowiednich flagach, by precyzyjnie wybrać okno.

---

## Wydajność i strojenie

- **Pasmo**: MJPEG jest „tłusty”. Ogranicz `--fps`, `--scale`, albo zwiększ kompresję (niższe `--quality`).
- **CPU/GPU**: zmniejsz `--fps` i `--scale`. `dxcam` korzysta z DirectX i jest szybki, ale enkodowanie JPEG to CPU.
- **Wiele klientów**: każdy klient utrzymuje własny strumień; rośnie obciążenie przy wielu odbiorcach.
- **Opóźnienia**: MJPEG zwykle <200 ms. Jeśli chcesz niższe i lepszą kompresję — rozważ WebRTC/H.264 (poza zakresem tego README).

---

## Sieć i zapora

- **Windows Defender Firewall**: przy pierwszym uruchomieniu zezwól Pythonowi na ruch w sieci **prywatnej**.
- **Port**: upewnij się, że `--port` jest otwarty w zaporze (domyślnie 4321).
- **Adres w LAN**: na kliencie otwieraj `http://IP_WINDOWS:PORT`, np. `http://192.168.1.199:4321`.

---

## Bezpieczeństwo

- Brak wbudowanej autoryzacji. Uruchamiaj tylko w **zaufanej sieci** (np. domowa/VPN).
- Jeśli potrzebujesz ochrony:
  - uruchom serwer wyłącznie na `127.0.0.1` i wystaw reverse proxy z auth,
  - dodaj prosty token do ścieżki `/stream.mjpg` lub middleware Basic Auth,
  - ogranicz dostęp regułą zapory do wybranych adresów IP.

---

## Znane ograniczenia

- **Okno zminimalizowane** nie jest przechwytywane (to ograniczenie Windows/DXGI).
- Niektóre aplikacje UWP mają top‑level `ApplicationFrameWindow`, a właściwy tytuł jest w child — używaj `--window-proc`.
- Przy wielu pasujących oknach wybierane jest **pierwsze największe** (względnie). Można dodać ranking wg. pozycji/rozmiaru (TODO).
- MJPEG nie zawiera audio; ten streamer nie przesyła dźwięku.

---

## FAQ

**Q: Dostaję „[WARN] Nie znaleziono okna…”**  
A: Użyj `--list-windows`, sprawdź dokładną nazwę procesu/klasy/tytułu. Spróbuj `--window-active` albo `--window-proc chrome.exe`.  
Upewnij się, że okno **nie jest zminimalizowane** i jest widoczne (ma dodatni rozmiar).

**Q: Czarny obraz lub „rwie”**  
A: Zmniejsz `--fps` i `--scale`. Zamknij obciążające GPU aplikacje. Upewnij się, że wybrane okno nie jest zminimalizowane.

**Q: Chcę 60 FPS**  
A: Możliwe, ale CPU/pasmo rośnie wykładniczo w MJPEG. Spróbuj `--fps 30`, `--scale 0.7`, `--quality 70` jako kompromis.

**Q: Obsługa wielu monitorów**  
A: Użyj `--monitor <index>` dla pełnego ekranu. Przy oknie flaga monitora jest ignorowana.

---

## Changelog

- **v1.1**: Zaawansowany wybór okna (`--window-active`, `--window-class`, `--window-proc`), diagnostyka `--list-windows`, wybór największego okna przy dopasowaniu po tytule.
- **v1.0**: Pierwsza wersja MJPEG (pełny ekran / tytuł okna).

---

## Licencja

MIT — bez gwarancji. Używaj komercyjnie i prywatnie na własną odpowiedzialność.
