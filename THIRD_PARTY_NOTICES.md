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

FleetFill uses the open-source LGPLv3 option for the dynamically linked PySide6
and Qt libraries. The local personal-beta build bundles those shared libraries
without modifying them and does not restrict replacing them or reverse
engineering for debugging such replacements. Build metadata and the license
files supplied by the exact dependency wheels are copied into the application's
`licenses` directory where available.

This repository currently documents a locally built personal beta, not a public
binary release. Before publishing an installer, the release process must also
ship the complete LGPLv3 and GPLv3 texts, the applicable Qt third-party
acknowledgements, and a valid corresponding-source offer for the exact Qt build.
The licenses supplied by the release's dependency wheels remain authoritative.

The packaged worker also contains a private Python runtime and a Node.js runtime
used only for local copied-save decoding. A public binary release must include
the exact Python and Node.js distribution notices in the same license payload.

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
