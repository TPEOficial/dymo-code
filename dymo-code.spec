# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Dymo Code
Builds standalone executables for Windows, macOS, and Linux
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
project_root = Path(SPECPATH)

# Check for icon file and report status
icon_path = project_root / 'docs' / 'images' / 'icon.ico'
icon_exists = icon_path.exists()
print(f"[BUILD INFO] Project root: {project_root}")
print(f"[BUILD INFO] Icon path: {icon_path}")
print(f"[BUILD INFO] Icon exists: {icon_exists}")
if icon_exists:
    print(f"[BUILD INFO] Icon size: {icon_path.stat().st_size} bytes")
else:
    print(f"[BUILD WARNING] Icon file not found! The executable will have no icon.")

# Get certifi certificate path for SSL support
try:
    import certifi
    certifi_path = (certifi.where(), 'certifi')
except ImportError:
    certifi_path = None

# Data files to include
datas = [
    # Include version.json for update checking
    (str(project_root / 'static-api'), 'static-api'),
    # Include logo image for documentation
    (str(project_root / 'docs' / 'images' / 'logo.png'), 'docs/images'),
]

# Add certifi certificates if available
if certifi_path:
    datas.append(certifi_path)

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'groq',
    'openai',
    'anthropic',
    'httpx',
    'dotenv',
    'rich',
    'rich.console',
    'rich.table',
    'rich.panel',
    'rich.text',
    'rich.box',
    'rich.markdown',
    'rich.syntax',
    'rich.progress',
    'rich.spinner',
    'rich.live',
    'prompt_toolkit',
    'prompt_toolkit.shortcuts',
    'prompt_toolkit.history',
    'prompt_toolkit.auto_suggest',
    'prompt_toolkit.completion',
    'questionary',
    'sqlite3',
    'json',
    'threading',
    'urllib.request',
    'urllib.error',
    'ssl',
    'certifi',
    # Include all src modules
    'src',
    'src.main',
    'src.agent',
    'src.agents',
    'src.clients',
    'src.command_handler',
    'src.commands',
    'src.config',
    'src.history',
    'src.memory',
    'src.mcp',
    'src.queue_manager',
    'src.storage',
    'src.terminal_ui',
    'src.ui',
    'src.tools',
    'src.logger',
    'src.name_detector',
    'src.interactive_input',
    'src.async_input',
    'src.context_manager',
    'src.utils',
    'src.utils.basics',
    'src.ignore_patterns',
    'src.prompt_enhancer',
    # Cloudscraper bypass modules
    'src.utils.bypasses',
    'src.utils.bypasses.cloudscraper',
    'src.utils.bypasses.cloudscraper.main',
    'src.utils.bypasses.cloudscraper.exceptions',
    'src.utils.bypasses.cloudscraper.user_agent',
    'src.utils.bypasses.cloudscraper.interpreters',
    'src.utils.bypasses.cloudscraper.captcha',
    # Cloudscraper dependencies
    'requests',
    'requests.adapters',
    'requests.sessions',
    'requests_toolbelt',
    'requests_toolbelt.utils',
    'requests_toolbelt.utils.dump',
    'brotli',
]

a = Analysis(
    [str(project_root / 'src' / 'main.py')],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='dymo-code',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_exists else None,
)
