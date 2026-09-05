#!/usr/bin/env python3
"""
ELK-BLEDOM Bluetooth LED Controller
------------------------------------
A lightweight GUI app to control ELK-BLEDOM (and compatible: LEDBLE, MELK,
ELK-BULB, ELK-LAMPL) Bluetooth LE LED strips/bulbs.

Features:
  - Scan for and auto-detect compatible LED devices
  - Turn LEDs on / off
  - Set any custom RGB color
  - Quick preset color buttons
  - Brightness control
  - Settings menu: App theme (System / Light / Dark)
  - Debug Terminal: in-app window showing every raw command/value sent
    to the strip (the background OS console is hidden on Windows since
    this replaces it)

Requires: bleak  (pip install bleak)
Tkinter ships with most Python installs already.

Run:
    python led_controller.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, colorchooser, messagebox, scrolledtext

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    raise SystemExit(
        "The 'bleak' package is required.\n"
        "Install it with:  pip install bleak"
    )

# --------------------------------------------------------------------------
# Protocol details
#
# ELK-BLEDOM style strips (and clones sold as LEDBLE / MELK / ELK-BULB /
# ELK-LAMPL) use a simple 9-byte command frame:
#
#   [0x7e, 0x00, CMD, ARG1, ARG2, ARG3, ARG4, 0x00, 0xef]
#
# Known commands:
#   Power ON  : 7e 00 04 f0 00 01 ff 00 ef
#   Power OFF : 7e 00 04 00 00 00 ff 00 ef
#   Set Color : 7e 00 05 03 RR GG BB 00 ef
#   Brightness: 7e 00 01 LL 00 00 00 00 ef   (LL = 0-100)
#
# The write characteristic is usually one of these UUIDs depending on the
# exact clone/firmware:
#   0000fff3-0000-1000-8000-00805f9b34fb   (most common - "ELK-BLE" type)
#   0000ffe1-0000-1000-8000-00805f9b34fb   (LEDBLE / MELK type)
# --------------------------------------------------------------------------

CANDIDATE_WRITE_UUIDS = [
    "0000fff3-0000-1000-8000-00805f9b34fb",
    "0000ffe1-0000-1000-8000-00805f9b34fb",
]

# Name prefixes for the family of devices that speak this protocol.
COMPATIBLE_NAME_PREFIXES = (
    "ELK-BLE",
    "ELK-BULB",
    "ELK-LAMPL",
    "LEDBLE",
    "MELK",
    "BLEDOM",
)

PRESET_COLORS = [
    ("Red",         (255, 0, 0)),
    ("Green",       (0, 255, 0)),
    ("Blue",        (0, 0, 255)),
    ("White",       (255, 255, 255)),
    ("Warm White",  (255, 214, 170)),
    ("Purple",      (128, 0, 255)),
    ("Pink",        (255, 20, 147)),
    ("Orange",      (255, 140, 0)),
    ("Yellow",      (255, 255, 0)),
    ("Cyan",        (0, 255, 255)),
    ("Teal",        (0, 128, 128)),
    ("Magenta",     (255, 0, 255)),
]


def cmd_power_on() -> bytes:
    return bytes([0x7E, 0x00, 0x04, 0xF0, 0x00, 0x01, 0xFF, 0x00, 0xEF])


def cmd_power_off() -> bytes:
    return bytes([0x7E, 0x00, 0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0xEF])


def cmd_set_color(r: int, g: int, b: int) -> bytes:
    r, g, b = (max(0, min(255, v)) for v in (r, g, b))
    return bytes([0x7E, 0x00, 0x05, 0x03, r, g, b, 0x00, 0xEF])


def cmd_set_brightness(level: int) -> bytes:
    level = max(0, min(100, level))
    return bytes([0x7E, 0x00, 0x01, level, 0x00, 0x00, 0x00, 0x00, 0xEF])


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def describe_command(data: bytes) -> str:
    """Turn a raw 9-byte command frame into a human-readable description,
    for the Debug Terminal."""
    if len(data) != 9 or data[0] != 0x7E or data[-1] != 0xEF:
        return "Unknown command"
    cmd = data[2]
    if cmd == 0x04:
        return "Power ON" if data[3] == 0xF0 else "Power OFF"
    if cmd == 0x05 and data[3] == 0x03:
        return f"Set Color -> RGB({data[4]}, {data[5]}, {data[6]})"
    if cmd == 0x01:
        return f"Set Brightness -> {data[3]}%"
    return "Unknown command"


# --------------------------------------------------------------------------
# Settings persistence
#
# A tiny JSON file in the user's home directory remembers the chosen theme
# and whether the Debug Terminal should reopen automatically next launch.
# --------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".led_controller"
CONFIG_FILE = CONFIG_DIR / "settings.json"
CRASH_LOG_FILE = CONFIG_DIR / "crash.log"

DEFAULT_SETTINGS = {
    "theme": "System",          # "System" | "Light" | "Dark"
    "debug_terminal": False,    # show the in-app Debug Terminal on launch
}


def load_settings() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        settings = DEFAULT_SETTINGS.copy()
        settings.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        return settings
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass  # settings are a convenience, not critical - never crash on save


# --------------------------------------------------------------------------
# Theming
#
# ttk doesn't ship a real dark mode, so we hand-roll a Light and Dark
# palette and switch the ttk "clam" theme's colors at runtime. "System"
# just picks whichever of the two matches the OS's current setting.
# --------------------------------------------------------------------------

THEMES = {
    "Light": {
        "bg": "#f0f0f0", "fg": "#1a1a1a", "panel": "#ffffff",
        "entry_bg": "#ffffff", "select_bg": "#3d8bfd", "muted": "#555555",
        "border": "#c8c8c8",
    },
    "Dark": {
        "bg": "#202124", "fg": "#e8e8e8", "panel": "#2c2d30",
        "entry_bg": "#3a3b3e", "select_bg": "#3d8bfd", "muted": "#a0a0a0",
        "border": "#454545",
    },
}


def detect_system_theme() -> str:
    """Best-effort OS dark/light detection. Falls back to Light."""
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "Light" if value else "Dark"
        elif sys.platform == "darwin":
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return "Dark" if "Dark" in result.stdout else "Light"
    except Exception:
        pass
    return "Light"


# --------------------------------------------------------------------------
# Windows console hiding
#
# When this script is launched with the regular python.exe (rather than
# pythonw.exe), Windows opens a console window behind the GUI. The app no
# longer needs that console for anything - all BLE traffic is now shown in
# the in-app Debug Terminal instead - so we hide it automatically. Nothing
# is closed, just hidden, and uncaught errors are still captured (see
# install_crash_handler below) so hiding it doesn't hide real problems.
# --------------------------------------------------------------------------

def hide_console_window():
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass


def install_crash_handler():
    """With the console hidden, an uncaught exception would otherwise be
    invisible. Log it to disk and show a message box instead."""
    def handle_exception(exc_type, exc_value, exc_tb):
        import traceback
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.datetime.now()} ---\n{text}\n")
        except Exception:
            pass
        try:
            messagebox.showerror(
                "Unexpected error",
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"Details were saved to:\n{CRASH_LOG_FILE}",
            )
        except Exception:
            pass
    sys.excepthook = handle_exception


# --------------------------------------------------------------------------
# Background asyncio loop so bleak (async) can be driven from a normal
# synchronous Tkinter GUI.
# --------------------------------------------------------------------------

class AsyncLoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_coro(self, coro, on_done=None):
        """Schedule a coroutine on the background loop from the GUI thread."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        if on_done:
            def _cb(fut):
                try:
                    result = fut.result()
                    error = None
                except Exception as e:  # noqa: BLE001
                    result = None
                    error = e
                on_done(result, error)
            future.add_done_callback(_cb)
        return future


class LedClient:
    """Wraps a bleak client + figures out which write UUID actually works."""

    def __init__(self):
        self.client: BleakClient | None = None
        self.write_uuid: str | None = None
        self.address: str | None = None
        # Optional callback: log_fn(direction: str, description: str, data: bytes | None)
        # Set by the GUI to feed the Debug Terminal. Left as None it's a no-op.
        self.log_fn = None

    @property
    def connected(self):
        return self.client is not None and self.client.is_connected

    async def connect(self, address: str):
        client = BleakClient(address)
        await client.connect(timeout=15)

        services = client.services
        found_uuid = None
        for uuid in CANDIDATE_WRITE_UUIDS:
            for service in services:
                for char in service.characteristics:
                    if char.uuid.lower() == uuid.lower():
                        found_uuid = uuid
                        break
                if found_uuid:
                    break
            if found_uuid:
                break

        if not found_uuid:
            # Fall back: look for any characteristic that supports write
            for service in services:
                for char in service.characteristics:
                    if "write" in char.properties or "write-without-response" in char.properties:
                        found_uuid = char.uuid
                        break
                if found_uuid:
                    break

        if not found_uuid:
            await client.disconnect()
            raise RuntimeError("No writable characteristic found on this device.")

        self.client = client
        self.write_uuid = found_uuid
        self.address = address

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.client = None
        self.write_uuid = None

    async def _write(self, data: bytes):
        if not self.connected:
            raise RuntimeError("Not connected to a device.")
        if self.log_fn:
            self.log_fn("TX", describe_command(data), data)
        await self.client.write_gatt_char(self.write_uuid, data, response=False)

    async def power_on(self):
        await self._write(cmd_power_on())

    async def power_off(self):
        await self._write(cmd_power_off())

    async def set_color(self, r, g, b):
        await self._write(cmd_set_color(r, g, b))

    async def set_brightness(self, level):
        await self._write(cmd_set_brightness(level))


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bluetooth LED Controller")
        self.geometry("460x560")
        self.resizable(False, False)

        self.settings = load_settings()
        self.theme_var = tk.StringVar(value=self.settings["theme"])
        self.debug_var = tk.BooleanVar(value=self.settings["debug_terminal"])
        self.debug_buffer = []  # rolling text history, replayed if the window reopens
        self.debug_win = None
        self.debug_text = None
        self._current_theme_colors = THEMES["Light"]

        self.loop_thread = AsyncLoopThread()
        self.led = LedClient()
        # _write() runs on the background asyncio thread, so hop back to the
        # main thread before touching any Tkinter widgets.
        self.led.log_fn = lambda direction, desc, data=None: self.after(
            0, self._debug_log_ui, direction, desc, data
        )
        self.discovered = {}  # display name -> address

        self._build_menu()
        self._build_ui()
        self.apply_theme(self.settings["theme"])
        if self.settings["debug_terminal"]:
            self.open_debug_terminal()

    # ---- Menu / settings ---------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        settings_menu = tk.Menu(menubar, tearoff=0)

        theme_menu = tk.Menu(settings_menu, tearoff=0)
        for label in ("System", "Light", "Dark"):
            theme_menu.add_radiobutton(
                label=label, value=label, variable=self.theme_var,
                command=self.on_theme_change,
            )
        settings_menu.add_cascade(label="App Theme", menu=theme_menu)

        settings_menu.add_checkbutton(
            label="Debug Terminal", variable=self.debug_var,
            command=self.on_debug_toggle,
        )
        settings_menu.add_separator()
        settings_menu.add_command(label="Exit", command=self.on_closing)

        menubar.add_cascade(label="Settings", menu=settings_menu)
        self.config(menu=menubar)

    def on_theme_change(self):
        self.settings["theme"] = self.theme_var.get()
        save_settings(self.settings)
        self.apply_theme(self.settings["theme"])

    def on_debug_toggle(self):
        show = self.debug_var.get()
        self.settings["debug_terminal"] = show
        save_settings(self.settings)
        if show:
            self.open_debug_terminal()
        elif self.debug_win is not None and self.debug_win.winfo_exists():
            self.debug_win.destroy()
            self.debug_win = None
            self.debug_text = None

    def apply_theme(self, theme_name: str):
        resolved = detect_system_theme() if theme_name == "System" else theme_name
        colors = THEMES.get(resolved, THEMES["Light"])
        self._current_theme_colors = colors

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=colors["bg"], foreground=colors["fg"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"],
                         bordercolor=colors["border"])
        style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        style.configure("TButton", background=colors["panel"], foreground=colors["fg"])
        style.map("TButton", background=[("active", colors["select_bg"])])
        style.configure("TCombobox", fieldbackground=colors["entry_bg"],
                         background=colors["panel"], foreground=colors["fg"])
        style.configure("TScale", background=colors["bg"], troughcolor=colors["panel"])
        style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"])
        style.configure("TRadiobutton", background=colors["bg"], foreground=colors["fg"])

        self.configure(bg=colors["bg"])
        if hasattr(self, "log_label"):
            self.log_label.configure(foreground=colors["muted"])
        if self.debug_win is not None and self.debug_win.winfo_exists():
            self.debug_win.configure(bg=colors["bg"])
            self.debug_text.configure(
                bg=colors["panel"], fg=colors["fg"], insertbackground=colors["fg"]
            )

    # ---- Debug Terminal -----------------------------------------------------
    def open_debug_terminal(self):
        if self.debug_win is not None and self.debug_win.winfo_exists():
            self.debug_win.lift()
            return

        colors = self._current_theme_colors
        win = tk.Toplevel(self)
        win.title("Debug Terminal - BLE Traffic")
        win.geometry("620x360")
        win.configure(bg=colors["bg"])

        text = scrolledtext.ScrolledText(
            win, wrap="word", state="disabled",
            bg=colors["panel"], fg=colors["fg"], insertbackground=colors["fg"],
            font=("Consolas" if os.name == "nt" else "Menlo", 10),
        )
        text.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_frame, text="Clear", command=self._clear_debug_text).pack(side="right")

        self.debug_win = win
        self.debug_text = text
        for line in self.debug_buffer:
            self._append_debug_line(line)

        def on_close():
            self.debug_var.set(False)
            self.settings["debug_terminal"] = False
            save_settings(self.settings)
            win.destroy()
            self.debug_win = None
            self.debug_text = None

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _append_debug_line(self, line: str):
        self.debug_text.configure(state="normal")
        self.debug_text.insert("end", line + "\n")
        self.debug_text.see("end")
        self.debug_text.configure(state="disabled")

    def _clear_debug_text(self):
        self.debug_buffer.clear()
        if self.debug_text is not None:
            self.debug_text.configure(state="normal")
            self.debug_text.delete("1.0", "end")
            self.debug_text.configure(state="disabled")

    def _debug_log_ui(self, direction: str, description: str, data: bytes | None = None):
        """Runs on the main thread. Appends a line to the buffer and, if the
        Debug Terminal window is open, to its text widget too."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        if data is not None:
            hexstr = " ".join(f"{b:02x}" for b in data)
            line = f"[{ts}] {direction:<4} {description:<26} bytes: {hexstr}"
        else:
            line = f"[{ts}] {direction:<4} {description}"

        self.debug_buffer.append(line)
        if len(self.debug_buffer) > 500:
            self.debug_buffer.pop(0)

        if self.debug_text is not None and self.debug_win is not None and self.debug_win.winfo_exists():
            self._append_debug_line(line)

    # ---- UI construction -------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # --- Connection frame ---
        conn_frame = ttk.LabelFrame(self, text="Device")
        conn_frame.pack(fill="x", **pad)

        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(conn_frame, textvariable=self.device_var, state="readonly", width=40)
        self.device_combo.grid(row=0, column=0, columnspan=2, padx=8, pady=6, sticky="ew")

        self.scan_btn = ttk.Button(conn_frame, text="Scan", command=self.on_scan)
        self.scan_btn.grid(row=0, column=2, padx=6, pady=6)

        self.connect_btn = ttk.Button(conn_frame, text="Connect", command=self.on_connect)
        self.connect_btn.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")

        self.disconnect_btn = ttk.Button(conn_frame, text="Disconnect", command=self.on_disconnect, state="disabled")
        self.disconnect_btn.grid(row=1, column=1, padx=8, pady=(0, 8), sticky="ew")

        self.status_label = ttk.Label(conn_frame, text="Not connected", foreground="#a33")
        self.status_label.grid(row=1, column=2, padx=6, pady=(0, 8))

        # --- Power frame ---
        power_frame = ttk.LabelFrame(self, text="Power")
        power_frame.pack(fill="x", **pad)

        self.on_btn = ttk.Button(power_frame, text="Turn ON", command=self.on_power_on)
        self.on_btn.pack(side="left", expand=True, fill="x", padx=8, pady=8)

        self.off_btn = ttk.Button(power_frame, text="Turn OFF", command=self.on_power_off)
        self.off_btn.pack(side="left", expand=True, fill="x", padx=8, pady=8)

        # --- Brightness frame ---
        bright_frame = ttk.LabelFrame(self, text="Brightness")
        bright_frame.pack(fill="x", **pad)

        self.brightness_var = tk.IntVar(value=100)
        self.brightness_scale = ttk.Scale(
            bright_frame, from_=0, to=100, orient="horizontal",
            variable=self.brightness_var, command=self._on_brightness_drag,
        )
        self.brightness_scale.pack(side="left", expand=True, fill="x", padx=8, pady=8)
        # Only send the command once the user releases the slider, so we
        # don't flood the device with BLE writes while dragging.
        self.brightness_scale.bind("<ButtonRelease-1>", self._on_brightness_release)

        self.brightness_readout = ttk.Label(bright_frame, text="100%", width=5)
        self.brightness_readout.pack(side="left", padx=(0, 8))

        # --- Custom color frame ---
        custom_frame = ttk.LabelFrame(self, text="Custom Color")
        custom_frame.pack(fill="x", **pad)

        self.color_preview = tk.Canvas(custom_frame, width=40, height=24, bg="#ffffff", highlightthickness=1, highlightbackground="#888")
        self.color_preview.pack(side="left", padx=8, pady=8)

        self.pick_color_btn = ttk.Button(custom_frame, text="Pick Color...", command=self.on_pick_color)
        self.pick_color_btn.pack(side="left", padx=8, pady=8)

        # --- Presets frame ---
        preset_frame = ttk.LabelFrame(self, text="Preset Colors")
        preset_frame.pack(fill="both", expand=True, **pad)

        cols = 3
        for i, (name, rgb) in enumerate(PRESET_COLORS):
            hexcolor = rgb_to_hex(rgb)
            btn = tk.Button(
                preset_frame, text=name, bg=hexcolor,
                fg=self._readable_fg(rgb),
                activebackground=hexcolor,
                relief="raised", bd=2,
                command=lambda c=rgb: self.on_preset(c),
            )
            r, c = divmod(i, cols)
            btn.grid(row=r, column=c, sticky="nsew", padx=6, pady=6, ipady=10)

        for c in range(cols):
            preset_frame.grid_columnconfigure(c, weight=1)

        # --- Log ---
        self.log_var = tk.StringVar(value="Ready. Click 'Scan' to find your LED strip.")
        self.log_label = ttk.Label(self, textvariable=self.log_var, foreground="#555", wraplength=430)
        self.log_label.pack(fill="x", padx=10, pady=(0, 10))

        self._set_controls_enabled(False)

    @staticmethod
    def _readable_fg(rgb):
        r, g, b = rgb
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#000000" if brightness > 150 else "#ffffff"

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for w in (self.on_btn, self.off_btn, self.pick_color_btn, self.brightness_scale):
            w.configure(state=state)
        self.disconnect_btn.configure(state=state)
        self.connect_btn.configure(state="disabled" if enabled else "normal")

    def log(self, msg):
        self.log_var.set(msg)

    # ---- Actions -----------------------------------------------------------
    def on_scan(self):
        self.scan_btn.configure(state="disabled")
        self.device_combo.set("")
        self.device_combo["values"] = []
        self.log("Scanning for Bluetooth LE devices (5s)...")
        self._debug_log_ui("INFO", "Scanning for BLE devices (5s)...")

        async def scan():
            devices = await BleakScanner.discover(timeout=5.0)
            return devices

        def done(devices, error):
            self.scan_btn.configure(state="normal")
            if error:
                self.log(f"Scan failed: {error}")
                return
            self.discovered.clear()
            display_names = []
            compatible_first = []
            other = []
            for d in devices:
                name = d.name or "Unknown device"
                label = f"{name}  ({d.address})"
                self.discovered[label] = d.address
                if name.upper().startswith(COMPATIBLE_NAME_PREFIXES):
                    compatible_first.append(label)
                else:
                    other.append(label)
            display_names = compatible_first + other
            self.device_combo["values"] = display_names
            if compatible_first:
                self.device_combo.set(compatible_first[0])
                self.log(f"Found {len(compatible_first)} compatible device(s). Select one and click Connect.")
            elif display_names:
                self.log("No device matched known ELK-BLEDOM names, but here's everything nearby - pick one to try.")
            else:
                self.log("No Bluetooth LE devices found. Make sure the LED strip is powered and in range.")
            self._debug_log_ui("INFO", f"Scan complete - {len(display_names)} device(s) found")

        self.loop_thread.run_coro(scan(), lambda r, e: self.after(0, done, r, e))

    def on_connect(self):
        label = self.device_var.get()
        if not label or label not in self.discovered:
            messagebox.showinfo("Select a device", "Please scan and select a device first.")
            return
        address = self.discovered[label]
        self.log(f"Connecting to {label} ...")
        self._debug_log_ui("INFO", f"Connecting to {label}")
        self.connect_btn.configure(state="disabled")

        def done(_, error):
            if error:
                self.connect_btn.configure(state="normal")
                self.log(f"Connection failed: {error}")
                self._debug_log_ui("INFO", f"Connection failed: {error}")
                messagebox.showerror("Connection failed", str(error))
                return
            self.status_label.configure(text="Connected", foreground="#2a7")
            self._set_controls_enabled(True)
            self.log(f"Connected to {label}.")
            self._debug_log_ui("INFO", f"Connected - using characteristic {self.led.write_uuid}")

        self.loop_thread.run_coro(self.led.connect(address), lambda r, e: self.after(0, done, r, e))

    def on_disconnect(self):
        def done(_, error):
            self.status_label.configure(text="Not connected", foreground="#a33")
            self._set_controls_enabled(False)
            self.log("Disconnected." if not error else f"Error during disconnect: {error}")
            self._debug_log_ui("INFO", "Disconnected" if not error else f"Disconnect error: {error}")

        self.loop_thread.run_coro(self.led.disconnect(), lambda r, e: self.after(0, done, r, e))

    def _run_or_warn(self, coro, success_msg):
        def done(_, error):
            if error:
                self.log(f"Error: {error}")
            else:
                self.log(success_msg)
        self.loop_thread.run_coro(coro, lambda r, e: self.after(0, done, r, e))

    def on_power_on(self):
        self._run_or_warn(self.led.power_on(), "LEDs turned ON.")

    def on_power_off(self):
        self._run_or_warn(self.led.power_off(), "LEDs turned OFF.")

    def on_preset(self, rgb):
        self.color_preview.configure(bg=rgb_to_hex(rgb))
        self._run_or_warn(self.led.set_color(*rgb), f"Color set to {rgb_to_hex(rgb)}.")

    def on_pick_color(self):
        rgb, hexcolor = colorchooser.askcolor(title="Choose LED color")
        if rgb is None:
            return
        r, g, b = (int(v) for v in rgb)
        self.color_preview.configure(bg=hexcolor)
        self._run_or_warn(self.led.set_color(r, g, b), f"Color set to {hexcolor}.")

    def _on_brightness_drag(self, _value):
        level = int(self.brightness_var.get())
        self.brightness_readout.configure(text=f"{level}%")

    def _on_brightness_release(self, _event):
        level = int(self.brightness_var.get())
        self._run_or_warn(self.led.set_brightness(level), f"Brightness set to {level}%.")

    def on_closing(self):
        try:
            if self.led.connected:
                fut = self.loop_thread.run_coro(self.led.disconnect())
                fut.result(timeout=3)
        except Exception:
            pass
        if self.debug_win is not None and self.debug_win.winfo_exists():
            self.debug_win.destroy()
        self.destroy()


def main():
    install_crash_handler()
    hide_console_window()
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
