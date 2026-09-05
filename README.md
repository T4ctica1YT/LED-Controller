# Bluetooth LED Controller

A simple and lightweight LED Controller script similar to those found on mobile devices, but made for PC with Python.

## Features

- Simple UI
- auto-detect compatible LED devices nearby
- Turn LEDs **On** / **Off**
- Pick **any custom RGB color** via a color picker
- One-click **preset colors** (Red, Green, Blue, Purple, Pink, Orange,
  Yellow, Cyan, Teal, Magenta, White, Warm White)
- **Brightness** slider (0–100%)
- **Settings menu**: switch App Theme between System / Light / Dark
- **Debug Terminal**: an in-app window (toggled from Settings) that
  logs every raw command/value sent to the strip, in place of the
  background console window

## Requirements

- Python 3.9+
- A computer with Bluetooth LE support
- The `bleak` library (cross-platform BLE for Windows / macOS / Linux)
If you dont know where to install Bleak, there is a Setup.py file you can run that will auto install Bleak with the correct version. More about the Setup files is in the next section.

## Setup (easiest way)

Run the setup script for your OS. It checks for a valid Python
installation, tells you what it found, then **asks for confirmation**
before installing/updating anything (`bleak`, plus anything else added
to the `REQUIREMENTS` list in `Setup/setup.py` later):
 
**Windows:**

 double-click `setup_windows.bat` (or run it in a terminal)
 
**macOS / Linux:**

```bash
chmod +x setup_unix.sh   # only needed once
./setup_unix.sh
```
 
Both scripts locate Python (`py`/`python`/`python3`, or versioned
names like `python3.13` on macOS/Linux), then hand off to
`Setup/setup.py` if you confirm. You can also run that directly:
```bash
python Setup/setup.py                # install/update in your current Python
python Setup/setup.py --venv         # install into a self-contained ./venv instead
python Setup/setup.py --check-only   # just report what's installed, change nothing
```
 

## Usage

1. Turn on your LED strip's power (it needs to already be powered/plugged
   in — Bluetooth only controls the light state, not mains power).

2. Click **Scan**. Devices whose name starts with `ELK-BLE`, `LEDBLE`,
   `MELK`, `ELK-BULB`, or `ELK-LAMPL` are listed first. If your strip
   isn't recognized by name, it'll still show up in the "everything
   nearby" list — just pick it and try Connect.

3. Select your device and click **Connect**.

4. Use the On/Off buttons, brightness slider, preset color buttons, or
   "Pick Color..." for a custom RGB value.

## Settings

Open the **Settings** menu in the app's menu bar:

- **App Theme** — `System` (matches your OS), `Light`, or `Dark`.
- **Debug Terminal** — check this to open a window that logs every
  command sent to the strip: a timestamp, what the command does (e.g.
  "Set Color -> RGB(255, 0, 0)"), and the exact 9 raw bytes written
  over Bluetooth. It has a **Clear** button, and un-checking the menu
  item (or closing the window) hides it again.

Both preferences are remembered between runs (stored in
`~/.led_controller/settings.json`).

On Windows, the background console window that normally pops up
behind the app is now hidden automatically at startup — the Debug
Terminal above is the intended replacement for watching what the app
is doing. If the app crashes unexpectedly, the error is still written
to `~/.led_controller/crash.log` and shown in a pop-up, so hiding the
console doesn't hide real problems.

## How it talks to the strip (For Nerds)

These strips use a simple 9-byte command format over a BLE GATT
characteristic (no pairing/PIN required):

| Action     | Bytes (hex)                              |
|------------|-------------------------------------------|
| Power ON   | `7e 00 04 f0 00 01 ff 00 ef`               |
| Power OFF  | `7e 00 04 00 00 00 ff 00 ef`               |
| Set Color  | `7e 00 05 03 RR GG BB 00 ef`               |
| Brightness | `7e 00 01 LL 00 00 00 00 ef` (LL = 0–100)  |

The app tries the two most common write-characteristic UUIDs
(`fff3` and `ffe1`) and falls back to any writable characteristic it
finds if neither matches.

If you would like to see this app function in real time, turn on the Debug Terminal in settings, more about settings in the section above this one (Aka, the settings section).

## Troubleshooting

- **Nothing shows up when scanning**: make sure the strip is powered on
  and within a few meters, and that your computer's Bluetooth is on.
  On Linux you may need `bluetoothctl` set up and the app run with
  appropriate permissions; on macOS you may be prompted to grant
  Bluetooth permission the first time.

  If you have used the App before and it worked once, make sure that instance of
  the app is closed. More then one instance of the app open at once can, and will
  cause issues.

- **Connects but nothing happens**: some strips use slightly different
  command bytes. Open an issue-style note for yourself with the exact
  device name from the Scan list — that name often reveals which
  clone/firmware it is, which sometimes needs a tweak to the command
  bytes at the top of `led_controller.py`.

- **"No writable characteristic found"**: your controller may use a
  different UUID scheme. You can inspect available services/characteristics
  with a general BLE scanner app on your phone (e.g. "nRF Connect") to
  find the correct write UUID and add it to `CANDIDATE_WRITE_UUIDS`.

## Forks

If you would like to fork this repo and custom fix, change, 
or do anything else with this repo, that is fine. All i ask is that
credit is given to me (T4ctica1) for the Original Script / code.
