# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['bridge.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=[
        # Python source modules (非包目录)
        ('config_manager.py',   '.'),
        ('main.py',             '.'),
        ('XianyuAgent.py',      '.'),
        ('XianyuApis.py',       '.'),
        ('context_manager.py',  '.'),
        ('login_browser.py',    '.'),
        # utils 包
        ('utils/*.py',          'utils'),
        # knowledge_base 包
        ('knowledge_base/*.py', 'knowledge_base'),
        # 默认提示词模板（../data/ 相对于 python/）
        ('../data/*_example.txt', 'data'),
    ],
    hiddenimports=[
        # 本项目模块
        'config_manager',
        'main',
        'XianyuAgent',
        'XianyuApis',
        'context_manager',
        'login_browser',
        'utils.xianyu_utils',
        'knowledge_base',
        'knowledge_base.manager',
        'knowledge_base.retriever',
        # 第三方库
        'openai',
        'openai.types',
        'openai.types.chat',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.client',
        'websockets.legacy.server',
        'websockets.asyncio',
        'websockets.asyncio.client',
        'loguru',
        'requests',
        'requests.adapters',
        'requests.packages',
        'faiss',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        # stdlib
        'sqlite3',
        'asyncio',
        'json',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型库，减小体积
        'tkinter',
        'matplotlib',
        'PIL',
        'cv2',
        'scipy',
        'pandas',
        'pytest',
        'IPython',
        'notebook',
    ],
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
    # UPX 会破坏 faiss/numpy 等 C 扩展，关闭
    upx=False,
    console=True,  # 必须为 True，Electron 通过 stdout 读取 JSON
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
    upx=False,
    upx_exclude=[],
    name='bridge',
)
