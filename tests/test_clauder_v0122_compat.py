from pathlib import Path
import json
import unittest

from clauder_workbench import __version__
from clauder_workbench.mcp_client import EXPECTED_R_STUDIO_TOOLS


EXPECTED_V0166_TOOLS = {
    "annotate",
    "cancel_annotation_job",
    "cancel_async_job",
    "check_cross_references",
    "check_messages",
    "checkpoint_session",
    "clean_error_log",
    "connect_session",
    "coordination_roster",
    "create_task_list",
    "execute_r",
    "execute_r_async",
    "execute_r_with_plot",
    "generate_codebook",
    "generate_notebook",
    "get_active_document",
    "get_annotation_job_status",
    "get_async_result",
    "get_bibtex",
    "get_r_info",
    "get_session_history",
    "get_viewer_content",
    "insert_text",
    "list_checkpoints",
    "list_sessions",
    "load_annotation_data",
    "modify_code_section",
    "probe_scripts",
    "read_file",
    "reconcile_values",
    "restore_session",
    "run_annotation_job",
    "screening_report",
    "search_citations",
    "search_project_code",
    "send_message",
    "set_agent_name",
    "suggest_edit",
    "update_task_status",
    "verify_references",
    "wait_for_message",
    "wake_on_message",
}


class ClaudeRV0166CompatibilityTests(unittest.TestCase):
    def test_workbench_candidate_version(self) -> None:
        self.assertEqual(__version__, "0.7.0")

    def test_exact_42_tool_surface(self) -> None:
        self.assertEqual(len(EXPECTED_R_STUDIO_TOOLS), 42)
        self.assertEqual(EXPECTED_R_STUDIO_TOOLS, EXPECTED_V0166_TOOLS)

    def test_candidate_provenance_is_documented(self) -> None:
        pair = json.loads(Path("runtime-compatibility.json").read_text(encoding="utf-8"))
        self.assertEqual(pair["workbench_version"], "0.7.0")
        self.assertEqual(pair["r_package_version"], "0.16.6.9001")
        self.assertEqual(pair["mcp_bridge_version"], "0.16.6.post1")
        self.assertEqual(pair["clauder_ref"], pair["clauder_commit"])
        self.assertRegex(pair["clauder_commit"], r"^[0-9a-f]{40}$")
        documents = [Path("README.md"), Path("README.zh-TW.md")]
        documents.extend(sorted(Path("skills").glob("*/SKILL.md")))
        self.assertEqual(len(documents), 6)  # 雙語入口與四項技能都必須配對。
        for path in documents:
            with self.subTest(document=str(path)):
                text = path.read_text(encoding="utf-8")
                for key in ("workbench_version", "r_package_version", "mcp_bridge_version"):
                    self.assertIn(pair[key], text)
                self.assertIn("runtime-compatibility.json", text)
                self.assertIn("PENDING", text)
                self.assertIn("UPGRADE_0.7.0", text)


if __name__ == "__main__":
    unittest.main()
