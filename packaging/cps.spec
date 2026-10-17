# PyInstaller onedir build for the supported target: Windows 10/11 x64.
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent.resolve()
sys.path.insert(0, str(ROOT))
from cps import __product__, __version__  # noqa: E402


def _write_version_resource(path: Path) -> None:
    """Create the Windows VERSIONINFO resource from cps package metadata."""
    parts = tuple(int(part) for part in __version__.split("."))
    if len(parts) != 3:
        raise ValueError(f"Windows releases require a three-part version, got {__version__!r}")
    version = ", ".join(str(part) for part in (*parts, 0))
    text = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version}),
    prodvers=({version}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'C.P.S. Team'),
         StringStruct('FileDescription', '{__product__} desktop application'),
         StringStruct('FileVersion', '{__version__}'),
         StringStruct('InternalName', 'CPS'),
         StringStruct('OriginalFilename', 'CPS.exe'),
         StringStruct('ProductName', '{__product__}'),
         StringStruct('ProductVersion', '{__version__}')]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


version_file = ROOT / "build" / "windows_version_info.txt"
_write_version_resource(version_file)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("cps") + ["backend.runtime"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="CPS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    exclude_binaries=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(version_file),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CPS",
)
