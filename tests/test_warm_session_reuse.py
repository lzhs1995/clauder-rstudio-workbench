import unittest
from pathlib import Path

from clauder_workbench import diagnostics


SKILL_ROOT = Path(__file__).parents[1] / "skills" / "clauder-rstudio-workbench"


class WarmSessionReuseTests(unittest.TestCase):
    def test_active_session_requires_no_addin_startup_message(self):
        layers = {
            "client_config": {"ok": True},
            "bridge": {"ok": True},
            "rstudio": {
                "ok": True,
                "discovery": [{
                    "session_name": "chapter4-mac",
                    "pid": 19087,
                    "port_open": True,
                    "token_present": True,
                }],
            },
            "agent_tools": {"status": "OBSERVED_PRESENT"},
        }
        contract = diagnostics.startup_contract(layers, session_name="chapter4-mac")
        self.assertEqual(contract["reason"], "NATIVE_SMOKE_NOT_VERIFIED")
        self.assertNotIn("Start Server", contract["next_action"])


    def test_warm_session_reference_contains_real_reuse_contract(self):
        text = (SKILL_ROOT / "references" / "warm-session-reuse.md").read_text()
        for marker in (
            "chapter4-mac",
            "port 8788 / pid 19087",
            "job_id=b422a3bc",
            "NATIVE_ASYNC_DONE",
            "do not ask the user to start `claudeAddin()` again",
            "CODEX_NATIVE_TOOLS_NOT_REGISTERED",
            "Copyable agent prompt",
            "全部成功后再提交正式 R 任务",
            "Warm reuse",
            "Addin startup required",
            "Task tool registration missing",
            "NATIVE_MCP_OK",
            "native-smoke --require-raw-file",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
