# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller specification for TianYue SSH Bridge (天玥SSH运维桥接器).

This script instructs PyInstaller to bundle the application into a single
Windows executable file. It assumes the following source modules are present
in the same directory:

    connection.py, params.py, config.py, logger.py,
    ssh_client.py, api_server.py, main.py, requirements.txt

The output filename is intentionally ASCII (tianyue_ssh_bridge.exe) to avoid
batch-file and command-line encoding issues on Windows. Users may rename the
EXE to 天玥SSH运维桥接器.exe after building if they prefer a localized name.

Usage:
    python -m PyInstaller tianyue_ssh_bridge.spec --clean --noconfirm
"""

from PyInstaller.building.build_main import Analysis, PYZ, EXE

# PyInstaller cipher (legacy option kept for compatibility).
block_cipher = None


analysis = Analysis(
    # Application entry point.
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # Hidden imports ensure these packages are pulled into the frozen EXE.
    # Without them, dynamic imports in paramiko / Flask-SocketIO may be
    # missed at runtime.
    hiddenimports=[
        # SSH engine
        "paramiko",
        "paramiko.transport",
        "paramiko.rsakey",
        "paramiko.ed25519key",
        "paramiko.ecdsakey",
        "paramiko.sftp",
        # Web server (chosen by api_and_main agent for easier packaging)
        "flask",
        "flask_socketio",
        "engineio",
        "engineio.async_drivers.threading",
        # Common transitive dependencies
        "cryptography",
        "bcrypt",
        # PyNaCl is installed as 'pynacl' but imported as 'nacl'.
        "nacl",
        "nacl.bindings",
        "werkzeug",
        # Declared in requirements.txt; include so future config validation works
        "jsonschema",
        # Standard library modules sometimes dynamically imported
        "uuid",
        "json",
        "logging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Reduce bundle size / build time by omitting packages not used.
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "tkinter",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    # ASCII filename avoids batch-file / command-line encoding issues on some
    # Windows consoles. The display name in README and the TianYue console is
    # still "天玥SSH运维桥接器".
    name="tianyue_ssh_bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Console=True keeps a visible console window. This is useful for
    # diagnostics while the gateway launches the EXE. Logs are also written
    # to %LOCALAPPDATA%\sshbridge\TianYueSSHBridge\logs\bridge.log.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Optional: add a branded icon later.
)
