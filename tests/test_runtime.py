from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fleetfill.runtime import data_root, node_executable, python_executable, resource_root


class RuntimePathTests(unittest.TestCase):
    def test_resource_and_data_overrides_are_respected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(
                os.environ,
                {
                    "FLEETFILL_RESOURCE_ROOT": str(root / "resources"),
                    "FLEETFILL_DATA_ROOT": str(root / "data"),
                },
                clear=False,
            ):
                self.assertEqual(resource_root(), (root / "resources").resolve())
                self.assertEqual(data_root(), (root / "data").resolve())

    def test_worker_and_node_overrides_are_respected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(
                os.environ,
                {
                    "FLEETFILL_WORKER_EXECUTABLE": str(root / "FleetFillWorker.exe"),
                    "FLEETFILL_NODE_EXECUTABLE": str(root / "node.exe"),
                },
                clear=False,
            ):
                self.assertEqual(
                    python_executable(), (root / "FleetFillWorker.exe").resolve()
                )
                self.assertEqual(node_executable(), (root / "node.exe").resolve())


if __name__ == "__main__":
    unittest.main()
