"""客户端配置与已安装文件预检；不访问客户端注册表或执行R/MCP。"""
from pathlib import Path
from .config import BLOCK, EVIDENCE_DIR, PASS
from .evidence import build_evidence, print_json, write_evidence
from .runtime_provenance import inspect_client

def run(*, client="codex", fail_closed=True, config_file=None):
    check = inspect_client(client, config_file)
    decision = "PASS" if check["ok"] else "BLOCK"
    exit_code = PASS if check["ok"] else BLOCK
    evidence = build_evidence("session_bootstrap", decision, exit_code=exit_code,
        transport_class="NOT_VERIFIED", agent=client,
        reasons=check["reasons"] + check["warnings"] or ["selected client configuration and installed bridge files passed"],
        extra={"client": client, "client_check": check, "scope": "client_configuration_and_installed_bridge_files",
               "native_registration": "UNKNOWN", "fail_closed": fail_closed,
               "not_verified": ["current_native_tools", "loaded_bridge_process", "live_R_namespace"]})
    path = write_evidence(evidence, evidence_dir=EVIDENCE_DIR)
    output = {"continue": check["ok"]}
    if not check["ok"]:
        output["stopReason"] = "; ".join(evidence["reasons"])
        output["systemMessage"] = f"ClaudeR {client} preflight blocked; evidence: {path}"
    print_json(output)
    return exit_code if fail_closed else PASS

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="session-bootstrap")
    parser.add_argument("--client", choices=["codex", "claude", "copilot"], default="codex")
    parser.add_argument("--config-file", type=Path)
    parser.add_argument("--no-fail-closed", action="store_true")
    args = parser.parse_args(argv)
    return run(client=args.client, fail_closed=not args.no_fail_closed, config_file=args.config_file)

if __name__ == "__main__":
    raise SystemExit(main())
