from pathlib import Path
import unittest

from clauder_workbench import __version__
from clauder_workbench.mcp_client import EXPECTED_R_STUDIO_TOOLS


EXPECTED_V0141_TOOLS = {
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
}


class ClaudeRV0141CompatibilityTests(unittest.TestCase):
    def test_workbench_candidate_version(self) -> None:
        self.assertEqual(__version__, "0.4.5")

    def test_exact_41_tool_surface(self) -> None:
        self.assertEqual(len(EXPECTED_R_STUDIO_TOOLS), 41)
        self.assertEqual(EXPECTED_R_STUDIO_TOOLS, EXPECTED_V0141_TOOLS)

    def test_candidate_provenance_is_documented(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        skill = Path("skills/clauder-rstudio-workbench/SKILL.md").read_text(encoding="utf-8")
        for text in (readme, skill):
            self.assertIn("ClaudeR `0.14.1`", text)
            self.assertIn("0.14.5", text)


if __name__ == "__main__":
    unittest.main()
