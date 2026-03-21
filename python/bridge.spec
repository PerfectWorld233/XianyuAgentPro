# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['bridge.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        ('utils/*.py', 'utils'),
    ],
    hiddenimports=[
        'config_manager',
        'main',
        'XianyuAgent',
        'XianyuApis',
        'context_manager',
        'utils.xianyu_utils',
        'openai',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        'loguru',
        'requests',
        'dotenv',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Must be True so Electron can read stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bridge',
)
