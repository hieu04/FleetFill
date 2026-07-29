"""Decode every calibration image required by the frozen 5+5 workflow.

This entry point performs no capture and sends no input.  Packaging invokes it
through FleetFillWorker so missing, misplaced, or corrupt runtime resources fail
the build before an installer can be produced.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


CALIBRATION_FILES = (
    "research/output/video-020357/frames/frame-0010-000005.000s.jpg",
    "research/output/video-020357/frames/frame-0014-000007.000s.jpg",
    "research/output/video-020357/frames/frame-0018-000009.000s.jpg",
    "research/output/video-020357/frames/frame-0019-000009.500s.jpg",
    "research/output/video-020129/frames/frame-0027-000013.500s.jpg",
    "research/output/video-020129/frames/frame-0042-000021.000s.jpg",
    "research/output/video-020129/frames/frame-0043-000021.500s.jpg",
    "research/output/video-020129/frames/frame-0045-000022.500s.jpg",
    "research/output/video-020129/frames/frame-0052-000026.000s.jpg",
    "research/output/video-020129/frames/frame-0058-000029.000s.jpg",
    "research/output/video-020129/frames/frame-0062-000031.000s.jpg",
    "research/output/live-wake-home-test/direct-capture-20260721-005704-141212.png",
    "research/output/live-hover-services-test/direct-capture-20260721-005945-220477.png",
    "research/output/live-open-recruitment-from-home-test/direct-capture-20260721-010250-822667.png",
)


def check_calibration(root: Path | None = None) -> dict:
    runtime_root = root or Path(__file__).resolve().parents[2]
    checked = []
    for relative in CALIBRATION_FILES:
        path = runtime_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing packaged calibration image: {path}")
        with Image.open(path) as image:
            image.load()
            checked.append(
                {
                    "path": str(path),
                    "format": image.format,
                    "size": list(image.size),
                }
            )
    return {"status": "passed", "checked": checked}


def main() -> int:
    report = check_calibration()
    print(json.dumps(report, indent=2))
    print(f"PACKAGED_CALIBRATION_CHECK: passed ({len(report['checked'])} images)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
