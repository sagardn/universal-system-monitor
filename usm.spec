# -*- mode: python ; coding: utf-8 -*-
"""
USM — Universal System Monitor
PyInstaller spec file for building standalone executables.
"""

import platform

block_cipher = None
system = platform.system()

# Determine icon by platform
if system == "Darwin":
    icon_file = None  # .icns file would go here
elif system == "Windows":
    icon_file = None  # .ico file would go here
else:
    icon_file = None

a = Analysis(
    ['daemon/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('frontend/dist', 'frontend/dist'),
    ],
    hiddenimports=[
        'daemon.collectors.system',
        'daemon.collectors.processes',
        'daemon.collectors.gpu',
        'daemon.collectors.docker',
        'daemon.collectors.services',
        'daemon.collectors.cgroups',
        'daemon.collectors.battery',
        'daemon.collectors.network',
        'daemon.collectors.security',
        'daemon.collectors.pipewire',
        'daemon.collectors.packages',
        'daemon.collectors.btrfs',
        'daemon.collectors.scheduler',
        'daemon.collectors.thermal',
        'daemon.collectors.disks',
        'daemon.collectors.icons',
        'daemon.actions.process_actions',
        'daemon.actions.docker_actions',
        'daemon.actions.service_actions',
        'daemon.actions.power_actions',
        'daemon.actions.package_actions',
        'daemon.actions.snapshot_actions',
        'daemon.actions.pipewire_actions',
        'daemon.actions.network_actions',
        'daemon.alerts.engine',
        'daemon.alerts.rules',
        'daemon.alerts.watchdog',
        'daemon.storage.database',
        'daemon.config',
        'daemon.server',
        'aiohttp',
        'aiosqlite',
        'psutil',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='usm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True,
    icon=icon_file,
)

# macOS .app bundle
if system == "Darwin":
    app = BUNDLE(
        exe,
        name='USM.app',
        icon=icon_file,
        bundle_identifier='com.usm.monitor',
        info_plist={
            'CFBundleName': 'Universal System Monitor',
            'CFBundleShortVersionString': '0.2.0',
            'CFBundleVersion': '0.2.0',
            'LSMinimumSystemVersion': '10.15',
            'NSHighResolutionCapable': True,
        },
    )
