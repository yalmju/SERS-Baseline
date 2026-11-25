# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = []
hiddenimports = []
datas += collect_data_files('pybaselines')
hiddenimports += collect_submodules('pybaselines')


a = Analysis(
    ['calibration_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not used by the app — kept out to shrink the bundle.
        'IPython', 'jedi', 'zmq', 'pyzmq', 'jupyter_client', 'jupyter_core',
        'tkinter', '_tkinter', 'PyQt5', 'PySide2', 'PySide6', 'pytest',
        'notebook', 'nbconvert', 'nbformat', 'sphinx', 'docutils',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SERS_Calibration',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
