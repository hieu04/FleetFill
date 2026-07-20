# Third-party notices

FleetFill's original source code is licensed under the MIT License in
[`LICENSE`](LICENSE). The packages and tools below remain under their own
licenses; the FleetFill license does not replace or modify those terms.

## Runtime dependencies

| Component | Use | License |
| --- | --- | --- |
| [NumPy](https://github.com/numpy/numpy) | Image-recognition arrays | BSD-3-Clause |
| [Pillow](https://github.com/python-pillow/Pillow) | Screen capture and image handling | MIT-CMU |
| [PySide6 / Qt for Python](https://doc.qt.io/qtforpython-6/) | Windows desktop interface | LGPL-3.0-only, GPL alternatives, or a commercial Qt license |

FleetFill intends to use the open-source LGPLv3 option for PySide6/Qt. The
source repository installs these packages separately and does not vendor their
source or binaries.

Before FleetFill distributes a packaged executable or installer, its release
process must preserve all applicable dependency notices and license texts and
must satisfy Qt's LGPLv3 requirements for the Qt libraries included with the
application. The licenses shipped inside the exact dependency wheels used for
that release are authoritative.

## Optional research dependencies

| Component | Use | License |
| --- | --- | --- |
| [`@trucky/sii-decrypt-ts` 1.0.0](https://github.com/Trucky/sii-decrypt-ts) | Local copied-save inspection | MIT |
| [OpenCV](https://github.com/opencv/opencv) | Optional video storyboard extraction | Apache-2.0 |

Some development research used separately downloaded tools, including
`sk-zk/Extractor` and Easy SCS Mod Manager. Their source and binaries are not
included in FleetFill; users who supply those tools must follow their respective
upstream license terms.

Euro Truck Simulator 2 game files, save data, screenshots, video, fonts,
artwork, and other SCS Software assets are not distributed by this repository.
FleetFill is unofficial and is not affiliated with or endorsed by SCS Software.
