import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clauder_workbench import installer


class StableBridgeLauncherTests(unittest.TestCase):
    def test_unix_launcher_is_real_file_and_direct_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            runtime = SimpleNamespace(
                system="macos",
                home=home,
                bridge_name="clauder-mcp",
                bridge_python_path=home / "uv-python",
                bridge_path=home / ".local" / "bin" / "clauder-mcp",
            )
            with patch.object(installer, "_atomic_write", wraps=installer._atomic_write):
                target = installer._install_stable_bridge_launcher(runtime)
            self.assertTrue(target.is_file())
            self.assertFalse(target.is_symlink())
            text = target.read_text()
            self.assertIn("clauder_mcp import main", text)
            self.assertIn("uv-python", text)


if __name__ == "__main__":
    unittest.main()
