from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clauder_workbench import transport


class DiscoveryRedactionTests(unittest.TestCase):
    def test_discovery_bearer_token_never_enters_doctor_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cmaverse.json").write_text(
                json.dumps(
                    {
                        "session_name": "cmaverse-new47",
                        "port": 8788,
                        "pid": 73538,
                        "token": "super-secret-local-bearer",
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(transport, "DISCOVERY_DIR", root), mock.patch.object(
                transport, "port_open", return_value=True
            ):
                sessions = transport.discovery_sessions()

        self.assertEqual(len(sessions), 1)
        self.assertNotIn("token", sessions[0])
        self.assertTrue(sessions[0]["token_present"])
        self.assertNotIn("super-secret-local-bearer", json.dumps(sessions))


if __name__ == "__main__":
    unittest.main()
