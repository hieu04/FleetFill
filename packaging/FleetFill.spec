# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import shutil
from importlib.metadata import distribution

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
TOOLS = ROOT / "research" / "tools"

reference_files = (
    "research/output/video-020357/frames/frame-0010-000005.000s.jpg",
    "research/output/video-020357/frames/frame-0014-000007.000s.jpg",
    "research/output/video-020357/frames/frame-0018-000009.000s.jpg",
    "research/output/video-020357/frames/frame-0019-000009.500s.jpg",
    "research/output/video-020129/frames/frame-0027-000013.500s.jpg",
    "research/output/video-020129/frames/frame-0042-000021.000s.jpg",
    "research/output/video-020129/frames/frame-0058-000029.000s.jpg",
    "research/output/video-020129/frames/frame-0062-000031.000s.jpg",
)

required_paths = [ROOT / relative for relative in reference_files]
required_paths.extend(
    [
        TOOLS / "save-inspector" / "decrypt-save.mjs",
        TOOLS / "save-inspector" / "node_modules" / "@trucky" / "sii-decrypt-ts",
    ]
)
missing = [str(path) for path in required_paths if not path.exists()]
if missing:
    raise SystemExit("FleetFill packaging inputs are missing:\n" + "\n".join(missing))

node = shutil.which("node")
if not node:
    raise SystemExit("FleetFill packaging requires node.exe on PATH")


def distribution_notices(package_name):
    package = distribution(package_name)
    notices = []
    for relative in package.files or ():
        relative_path = Path(str(relative))
        relative_text = relative_path.as_posix().casefold()
        if relative_path.name == "METADATA" or "/licenses/" in relative_text or relative_path.name.casefold().startswith(("license", "copying", "notice")):
            source = Path(package.locate_file(relative))
            if source.is_file():
                notices.append((str(source), f"licenses/dependencies/{package_name}"))
    return notices

runtime_datas = [
    *((str(path), "research/tools") for path in sorted(TOOLS.glob("*.py"))),
    *(
        (str(ROOT / relative), str(Path(relative).parent))
        for relative in reference_files
    ),
    (
        str(TOOLS / "save-inspector" / "decrypt-save.mjs"),
        "research/tools/save-inspector",
    ),
    (
        str(TOOLS / "save-inspector" / "node_modules" / "@trucky" / "sii-decrypt-ts"),
        "research/tools/save-inspector/node_modules/@trucky/sii-decrypt-ts",
    ),
    (str(node), "runtime"),
    (str(ROOT / "LICENSE"), "licenses"),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "licenses"),
    *distribution_notices("numpy"),
    *distribution_notices("pillow"),
    *distribution_notices("pyside6"),
    *distribution_notices("shiboken6"),
]

gui = Analysis(
    [str(SRC / "fleetfill" / "personal_beta.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

worker = Analysis(
    [str(SRC / "fleetfill" / "worker.py")],
    pathex=[str(SRC), str(TOOLS)],
    binaries=[],
    datas=runtime_datas,
    hiddenimports=["fleetfill.simulated_controller"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6"],
    noarchive=False,
    optimize=0,
)

gui_pyz = PYZ(gui.pure)
worker_pyz = PYZ(worker.pure)

gui_exe = EXE(
    gui_pyz,
    gui.scripts,
    [],
    exclude_binaries=True,
    name="FleetFill",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

worker_exe = EXE(
    worker_pyz,
    worker.scripts,
    [],
    exclude_binaries=True,
    name="FleetFillWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    gui_exe,
    worker_exe,
    gui.binaries,
    gui.datas,
    worker.binaries,
    worker.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FleetFill",
)
