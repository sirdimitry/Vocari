# PyInstaller build spec for Vocari — see README "Сборка .exe" for how to
# run this (`pyinstaller vocari.spec`) and what the output looks like.
#
# --onedir (not --onefile): config.json/logs/silero_cache/assets need to
# live as plain, persistent files right next to Vocari.exe (see
# vocari/paths.py's app_root()) — onefile's temp-extraction-per-run model
# would make that awkward (files would need copying out on every launch)
# and slows down startup for no benefit here.
#
# torch is excluded on purpose (see requirements.txt's comment on it) — it's
# ~600 MB, and bundling it here would make every Vocari user pay that cost
# even the ones who never touch the offline Silero voices. Settings ->
# Silero instead downloads a prebuilt torch-CPU bundle on demand (see
# vocari/runtime_deps.py) into runtime_deps/ next to Vocari.exe.
#
# Nothing here ever bundles config.json, logs/, silero_cache/, or
# runtime_deps/ — those don't exist until the app actually runs and are
# created fresh next to whatever copy of Vocari.exe is running (never
# inside the build itself).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# omegaconf (+ its own deps) is a real requirements.txt dependency, but
# nothing in vocari's own code imports it directly - it's only reached from
# *inside* the Silero model's code, which torch.hub downloads from GitHub at
# runtime (see silero_provider.py), so PyInstaller's static analysis has no
# way to see that need on its own and silently drops it.
#
# The big list below is every stdlib top-level module `import torch` (plus
# loading/running an actual Silero model through it) touches, computed
# empirically by diffing sys.modules before/after against a normal install -
# torch itself is excluded from this build (see `excludes` below), so
# PyInstaller's own static analysis never sees any of this and would
# otherwise silently drop every one of them, exactly like omegaconf above.
#
# Each name goes through collect_submodules() rather than being listed bare:
# a bare package name in hiddenimports does NOT recursively pull in its
# submodules, only whatever PyInstaller's own analysis happens to discover
# elsewhere - `xml` for instance was already getting bundled (something else
# needs xml.sax), but only that partial slice, and Python resolves `import
# xml.etree` through the *already-imported* xml package's own __path__, not
# through sys.path - so even a complete, separate copy sitting elsewhere on
# sys.path (the runtime_deps download's supplementary stdlib copy - see
# vocari/runtime_deps.py) never gets consulted once xml itself has already
# resolved from an incomplete source. collect_submodules() sidesteps that
# entirely by making PyInstaller bundle the real, complete package itself;
# it's a no-op (returns just the name) for plain, non-package modules.
_STDLIB_FOR_TORCH = [
    '__future__', 'argparse', 'ast', 'asyncio', 'atexit', 'base64',
    'binascii', 'bisect', 'bz2', 'calendar', 'cmath', 'collections',
    'concurrent', 'contextlib', 'contextvars', 'copy', 'copyreg', 'csv',
    'ctypes', 'dataclasses', 'datetime', 'difflib', 'dis', 'email',
    'enum', 'errno', 'fnmatch', 'functools', 'gc', 'gettext', 'glob',
    'gzip', 'hashlib', 'heapq', 'http', 'importlib', 'inspect',
    'ipaddress', 'itertools', 'json', 'keyword', 'linecache', 'locale',
    'logging', 'lzma', 'math', 'msvcrt', 'multiprocessing', 'numbers',
    'opcode', 'operator', 'pathlib', 'pickle', 'pickletools', 'pkgutil',
    'platform', 'posixpath', 'pprint', 'queue', 'quopri', 'random',
    're', 'reprlib', 'runpy', 'select', 'selectors', 'shutil', 'signal',
    'socket', 'ssl', 'string', 'struct', 'subprocess', 'sysconfig',
    'tarfile', 'tempfile', 'textwrap', 'threading', 'timeit', 'token',
    'tokenize', 'traceback', 'types', 'typing', 'unittest', 'urllib',
    'uuid', 'warnings', 'weakref', 'xml', 'zipfile', 'zlib',
]
_hidden_imports = ['omegaconf', 'antlr4', 'yaml']
for _name in _STDLIB_FOR_TORCH:
    _hidden_imports += collect_submodules(_name)

a = Analysis(
    ['run_vocari.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=_hidden_imports,
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
    icon='assets/branding/icon.ico',
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
