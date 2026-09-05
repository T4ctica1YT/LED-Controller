#!/usr/bin/env python3
"""
setup.py - One-shot dependency installer/updater for the LED Controller app.

What it does:
  1. Checks that Python is a supported version (3.9+)
  2. Upgrades pip itself
  3. Installs/updates the packages this app needs (see REQUIREMENTS below)
  4. Prints a final summary so you know it's ready to go

Run it with:
    python setup.py
or on some systems:
    python3 setup.py

Optional flags:
    --venv       Create (or reuse) a local virtual environment in ./venv
                 and install everything there instead of system-wide.
    --check-only Just report versions/status, don't install anything.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 9)

# The app's dependencies live right here instead of in a separate
# requirements.txt - there's only a couple of them, so one source of
# truth is simpler than juggling two files. Add version pins the same
# way you would in a requirements.txt line, e.g. "bleak>=0.21".
REQUIREMENTS = [
    "bleak>=0.21",
]


def banner(text):
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def check_python_version():
    banner("Checking Python version")
    version = sys.version_info
    print(f"Found Python {version.major}.{version.minor}.{version.micro} at {sys.executable}")
    if (version.major, version.minor) < MIN_PYTHON:
        print(f"\nERROR: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")
        print("Please install a newer Python from https://www.python.org/downloads/")
        sys.exit(1)
    print("Python version OK.")


def get_venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(venv_dir: Path):
    banner(f"Setting up virtual environment at {venv_dir}")
    if venv_dir.exists():
        print("Virtual environment already exists, reusing it.")
    else:
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("Virtual environment created.")
    return get_venv_python(venv_dir)


def run_pip(python_exe, args, description):
    banner(description)
    cmd = [str(python_exe), "-m", "pip"] + args
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: '{description}' failed (exit code {result.returncode}).")
        sys.exit(result.returncode)


def check_installed_versions(python_exe):
    banner("Installed package versions")
    subprocess.run([str(python_exe), "-m", "pip", "list"], check=False)


def main():
    parser = argparse.ArgumentParser(description="Install/update dependencies for the LED Controller app.")
    parser.add_argument("--venv", action="store_true", help="Use/create a local virtual environment (./venv)")
    parser.add_argument("--check-only", action="store_true", help="Only report status, don't install/update anything")
    args = parser.parse_args()

    check_python_version()

    # This script lives in a "Setup" subfolder; the app itself lives one
    # level up, in the project root. Only project_root is needed now for
    # locating/creating the venv.
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    python_exe = sys.executable
    if args.venv:
        venv_dir = project_root / "venv"
        python_exe = ensure_venv(venv_dir)

    if args.check_only:
        check_installed_versions(python_exe)
        banner("Check complete (no changes made)")
        return

    run_pip(python_exe, ["install", "--upgrade", "pip"], "Upgrading pip")
    run_pip(python_exe, ["install", "--upgrade"] + REQUIREMENTS, "Installing/updating requirements (bleak, etc.)")
    check_installed_versions(python_exe)

    banner("All set!")
    if args.venv:
        activate_hint = (
            f"{venv_dir}\\Scripts\\activate" if os.name == "nt" else f"source {venv_dir}/bin/activate"
        )
        print(f"Activate the virtual environment with:\n    {activate_hint}")
        print(f"Then run:\n    python led_controller.py")
    else:
        print("Run the app with:\n    python led_controller.py")


if __name__ == "__main__":
    main()
