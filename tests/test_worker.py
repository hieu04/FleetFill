from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fleetfill.worker import configure_utf8_stdio, main


class RecordingStream:
    def __init__(self) -> None:
        self.calls = []

    def reconfigure(self, **kwargs) -> None:
        self.calls.append(kwargs)


class WorkerTests(unittest.TestCase):
    def test_configures_packaged_pipes_for_unicode_ocr_output(self):
        stdout = RecordingStream()
        stderr = RecordingStream()
        with patch("fleetfill.worker.sys.stdout", stdout), patch(
            "fleetfill.worker.sys.stderr", stderr
        ):
            configure_utf8_stdio()
        expected = [{"encoding": "utf-8", "errors": "backslashreplace"}]
        self.assertEqual(stdout.calls, expected)
        self.assertEqual(stderr.calls, expected)

    def test_requires_a_target(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = main([])

        self.assertEqual(result, 2)
        self.assertIn("requires a Python script", stderr.getvalue())

    def test_dispatches_a_python_script(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            marker = Path(temporary_directory) / "marker.txt"
            script = Path(temporary_directory) / "probe.py"
            script.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8')\n",
                encoding="utf-8",
            )

            result = main([str(script), str(marker), "dispatched"])

            self.assertEqual(result, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "dispatched")


if __name__ == "__main__":
    unittest.main()
