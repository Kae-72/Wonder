
# **Wonder**💙
<img width="160" height="160" alt="IMG_5774(1)" src="https://github.com/user-attachments/assets/26bb6c75-0df3-4e00-b486-9c1854045303" />

## Description of the project
Electronics and programming project  
It is a Raspberry Pi Pico 2 W based tamagotchi style mascot keychain designed for students. It is meant to help you recording lectures, staying in the loop with Google Calendar integration and a Pomodoro timer to study without having to look at your phone's timer!
### What is "Wonder"?
Wonder is the name of the mascot! It is also the name of the app, and the physical device.  
### Why "Wonder"?
> "Wisdom begins in wonder." — Socrates
###  What does it do?
- **Records lectures** to a microSD card. The recording is sent over WiFi to Wonder Hub, transcribed (Whisper on the computer, or Gemini) and summarized with Gemini into a Word file and a Google Doc. Before every recording the device asks you to confirm that you asked for permission.
- **Pomodoro timer** for phoneless study sessions (it keeps running in the background).
- **Google Calendar**: shows your next 7 days, plays a sound 10 minutes before each class, and lets you mark a task or class as **done** ("¡Hecho!"), with anti-cheat rules checked against Google Calendar.
- **Status bar** with clock, WiFi and battery; remembers several WiFi networks (home, university, phone hotspot) and connects by itself; sleeps on battery when idle.
- **Wonder's room**: a menu option where the mascot shows its mood (happy, normal, sad, angry) with mood, energy and study bars, based on your completed tasks, Pomodoro minutes and missed classes. Accessories unlock as you complete tasks.
- **Game Boy style sounds** (original, pentatonic scale) through a small speaker.
- **Web app** to log in with Google, link the keychain to WiFi, set the Pomodoro, read the recordings and customize Wonder.

### Languages
- Python (MicroPython on the keychain, Python/Flask on the computer)
- HTML, CSS and JavaScript (web app, no build step)
### Libraries
- Keychain: MicroPython built-ins (`machine`, `network`, `framebuf`, `requests`) + `sdcard.py` (from micropython-lib, MIT)
- Wonder Hub: Flask, Pillow, google-api-python-client, google-auth-oauthlib, google-genai, python-docx, openai-whisper (optional)
### Components
#### Brain (microcontroller):
- Raspberry Pi Pico 2 W
#### Storage:
- MicroSD reader
- MicroSD (FAT32; 32 GB works well — a 90 min lecture is about 170 MB)
#### Inputs and Outputs:
- display: 1.8" TFT ST7735 (160×128)
- usb-c module for charging 
- microphone and microphone module: MEMS I2S (INMP441)
- 3 push buttons (left, select, right)
- tiny speaker with a MAX98357A I2S amplifier
#### Energy source:
- LiPo 3.7v rechargeable battery

## In this repo you will find...
| Folder | What is inside |
|---|---|
| `llavero/` | Everything that goes on the Pico (copy it with Thonny). `llavero/pruebas/` has hardware tests that run from the computer. |
| `wonder-app/hub/` | Wonder Hub: the server that runs on the computer (`python hub.py`). |
| `wonder-app/app/` | The web app (served by the hub at `http://localhost:8000`). |
| `herramientas/` | Tools to convert the designs (PNG) into screens for the Pico. |
| `PRELIMINAR/` | The first versions of each function. |

Setup instructions (in Spanish): `wonder-app/LEEME.md`. Change log: `CAMBIOS.md`.

**Pins (Pico 2 W):** display SPI0 SCK=GP18 MOSI=GP19 CS=GP0 DC=GP1 RST=GP2 BL=GP5 · buttons left=GP14 select=GP15 right=GP16 · microphone SCK=GP6 WS=GP7 SD=GP8 · microSD SPI1 SCK=GP10 MOSI=GP11 MISO=GP12 CS=GP13 · amplifier BCLK=GP20 LRC=GP21 DIN=GP22 SD=GP26.

Secrets (`credentials.json`, tokens, WiFi passwords) are never stored in this repo.

You will also find (coming soon)...  
- Schematics or pictures of the connections
- the file of the 3d printed device's case
- photo of the finished device

## The group behind Wonder
- (yet to put the github accounts)
