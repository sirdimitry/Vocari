# PyInstaller build spec for Vocari — see README "Сборка .exe" for how to
# run this (`pyinstaller vocari.spec`) and what the output looks like.
#
# --onedir (not --onefile): config.json/logs/silero_cache/assets need to
# live as plain, persistent files right next to Vocari.exe (see
# vocari/paths.py's app_root()) — onefile's temp-extraction-per-run model
# would make that awkward (files would need copying out on every launch)
# and slows down startup for no benefit here.
#
# torch is excluded on purpose (see requirements.txt's comment on it) —
# Silero stays an "install torch yourself" optional feature even in the
# packaged build; the app already shows a friendly error instead of
# crashing when it's unavailable (see vocari/tts/silero_provider.py).
#
# Nothing here ever bundles config.json, logs/, or silero_cache/ — those
# don't exist until the app actually runs and are created fresh next to
# whatever copy of Vocari.exe is running (never inside the build itself).

block_cipher = None

a = Analysis(
    ['run_vocari.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchaudio'],
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
    name='Vocari',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Vocari',
)
