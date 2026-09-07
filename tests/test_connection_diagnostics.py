from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from clauder_workbench import cli, diagnostics, mcp_client, transport


class HttpDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.write_session("A", 48879)
        self.patch = mock.patch.object(transport, "DISCOVERY_DIR", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_session(self, name, port, **extra):
        (self.root / f"{name}.json").write_text(json.dumps({"session_name": name, "port": port, "pid": 42, "token": "secret-test-token", **extra}))

    def probe(self, body=None, *, status=200, error=None, **kwargs):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = status

        def opened(req, timeout):
            if error:
                raise error
            code = json.loads(req.data)["code"]
            marker = code.split("'")[1]
            doc = body(marker) if callable(body) else body
            if doc is None:
                doc = {"success": True, "output": marker}
            response.read.return_value = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
            return response

        opener = mock.Mock()
        opener.open.side_effect = opened
        with mock.patch.object(transport.urllib.request, "build_opener", return_value=opener):
            result = transport.http_execute_probe(**kwargs)
        return result, opener

    def test_discovered_port_auth_and_fresh_marker(self):
        result, opener = self.probe()
        self.assertTrue(result["ok"])
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "http://127.0.0.1:48879/execute")
        self.assertEqual(req.get_header("X-clauder-token"), "secret-test-token")
        self.assertNotIn("secret-test-token", json.dumps(result))

    def test_error_json_is_not_success(self):
        result, _ = self.probe({"error": "R execution failed"})
        self.assertFalse(result["ok"])

    def test_marker_with_error_is_not_success(self):
        result, _ = self.probe(lambda m: {"success": True, "output": m, "error": "failed later"})
        self.assertFalse(result["ok"])

    def test_false_success_flag_is_not_success(self):
        result, _ = self.probe(lambda m: {"success": False, "output": m})
        self.assertFalse(result["ok"])

    def test_unrelated_or_stale_output_rejected(self):
        for body in ({"success": True, "output": "hello"}, {"success": True, "output": "clauder_http_probe_ok_old"}, b"<html>OK</html>", [], {"success": "true", "output": "x"}):
            with self.subTest(body=body):
                result, _ = self.probe(body)
                self.assertFalse(result["ok"])

    def test_auth_failure_and_timeout(self):
        for error in (urllib.error.HTTPError("http://localhost", 401, "Unauthorized", {}, None), TimeoutError("secret-test-token")):
            result, _ = self.probe(error=error)
            self.assertFalse(result["ok"])
            self.assertNotIn("secret-test-token", json.dumps(result))

    def test_bad_status_rejected(self):
        self.assertFalse(self.probe(status=500)[0]["ok"])

    def test_oversized_response_rejected(self):
        self.assertFalse(self.probe(b"x" * (1024 * 1024 + 1))[0]["ok"])

    def test_multiple_sessions_need_explicit_selection(self):
        self.write_session("B", 48880)
        result, opener = self.probe()
        self.assertFalse(result["ok"])
        opener.open.assert_not_called()
        result, opener = self.probe(session_name="B")
        self.assertTrue(result["ok"])
        self.assertEqual(result["port"], 48880)

    def test_wrong_port_and_name_do_not_fallback(self):
        for kwargs in ({"port": 8787}, {"session_name": "missing"}, {"port": 48879, "session_name": "missing"}):
            result, opener = self.probe(**kwargs)
            self.assertFalse(result["ok"])
            opener.open.assert_not_called()

    def test_malformed_discovery_does_not_crash(self):
        (self.root / "bad.json").write_text("[]")
        self.assertTrue(self.probe()[0]["ok"])
        with mock.patch.object(transport, "port_open", return_value=True):
            self.assertEqual(len(transport.discovery_sessions()), 2)

    def test_legacy_no_token_session(self):
        self.write_session("A", 48879, token=None)
        result, opener = self.probe()
        self.assertTrue(result["ok"])
        self.assertIsNone(opener.open.call_args.args[0].get_header("X-clauder-token"))

    def test_no_redirect_and_proxy_disabled(self):
        # 使用真实 opener，捕获其 handler；不进行网络访问。
        real = transport.urllib.request.build_opener
        built = []

        def capture(*handlers):
            opener = real(*handlers)
            built.extend(opener.handlers)
            opener.open = mock.Mock(side_effect=TimeoutError())
            return opener

        with mock.patch.object(transport.urllib.request, "build_opener", side_effect=capture):
            transport.http_execute_probe()
        redirects = [h for h in built if isinstance(h, transport.urllib.request.HTTPRedirectHandler)]
        self.assertEqual(len(redirects), 1)
        self.assertIsNone(redirects[0].redirect_request(None, None, 302, "", {}, "https://example.com"))
        self.assertFalse(any(isinstance(h, transport.urllib.request.ProxyHandler) and h.proxies for h in built))


class LayerTests(unittest.TestCase):
    def test_inventory_never_proves_native(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tools.json"
            for names, expected in (([], "OBSERVED_ABSENT"), (["mcp__r_studio__execute_r"], "OBSERVED_PRESENT")):
                p.write_text(json.dumps(names))
                result = diagnostics.agent_tool_status(p)
                self.assertEqual(result["status"], expected)
                self.assertFalse(result["native_verified"])
            p.write_text("null")
            self.assertEqual(diagnostics.agent_tool_status(p)["status"], "INVALID")
        self.assertEqual(diagnostics.agent_tool_status(None)["status"], "UNKNOWN")

    def test_runtime_success_independent_of_config_and_native(self):
        with mock.patch.object(diagnostics, "connection_probe", return_value={"ok": True, "bridge_ok": True, "pid": 42}), mock.patch.object(diagnostics, "discovery_sessions", return_value=[{"session_name": "A", "pid": 42}]):
            layers = diagnostics.connection_layers({"ok": False}, session_name="A")
        self.assertFalse(layers["client_config"]["ok"])
        self.assertTrue(layers["rstudio"]["ok"])
        self.assertTrue(layers["bridge"]["ok"])
        self.assertEqual(layers["agent_tools"]["status"], "UNKNOWN")

    def test_wrong_live_pid_rejected(self):
        with mock.patch.object(diagnostics, "connection_probe", return_value={"ok": True, "bridge_ok": True, "pid": 99}), mock.patch.object(diagnostics, "discovery_sessions", return_value=[{"session_name": "A", "pid": 42}]):
            self.assertFalse(diagnostics.connection_layers({"ok": True}, session_name="A")["rstudio"]["ok"])

    def test_configured_bridge_only_no_implicit_install(self):
        with mock.patch.object(mcp_client, "_load_codex_rstudio_server", return_value=None), mock.patch.object(mcp_client, "_session_run") as run:
            self.assertFalse(mcp_client.connection_probe()["bridge_ok"])
            run.assert_not_called()

    def test_no_selected_session_does_not_execute(self):
        result, called = self.run_probe("")
        self.assertTrue(result["bridge_ok"])
        self.assertFalse(result["ok"])
        self.assertEqual(called, ["list_sessions"])

    def run_probe(self, name, *, marker=True, error=False):
        called = []
        class Session:
            async def list_tools(self):
                return SimpleNamespace(tools=[SimpleNamespace(name=n) for n in mcp_client.EXPECTED_R_STUDIO_TOOLS])

            async def call_tool(self, name, args):
                called.append(name)
                text = "OK"
                if name == "execute_r" and marker:
                    text = args["code"].split("'")[1] + "42 r=4.6.1\n"
                return SimpleNamespace(isError=error, content=[SimpleNamespace(text=text)])

        async def run(timeout, runner):
            return await runner(Session(), "/test/clauder-mcp", [])

        with mock.patch.object(mcp_client, "_load_codex_rstudio_server", return_value=("/test/clauder-mcp", [], {})), mock.patch.object(mcp_client, "_session_run", side_effect=run):
            return mcp_client.connection_probe(name), called

    def test_live_marker_required(self):
        result, calls = self.run_probe("A")
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 42)
        self.assertEqual(calls, ["list_sessions", "connect_session", "execute_r"])
        self.assertFalse(self.run_probe("A", marker=False)[0]["ok"])
        self.assertFalse(self.run_probe("A", error=True)[0]["ok"])

    def test_cli_diagnostic_cannot_emit_native_pass(self):
        layers = {"bridge": {"ok": True}, "rstudio": {"ok": True}, "client_config": {"ok": True}, "agent_tools": {"status": "OBSERVED_PRESENT"}}
        args = cli.build_parser().parse_args(["connection-diagnose", "--session-name", "A"])
        with mock.patch.object(cli, "connection_layers", return_value=layers), mock.patch.object(cli, "_load_install_info", return_value=({}, None)), mock.patch.object(cli, "_check_codex_rstudio_mcp_config", return_value={}), mock.patch.object(cli, "emit", side_effect=lambda doc: doc):
            result = cli.cmd_connection_diagnose(args)
        self.assertEqual(result["decision"], "WARN")
        self.assertEqual(result["transport_class"], "MCP_STDIO_OK")
        self.assertEqual(result["extra"]["native_gate"], "NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
