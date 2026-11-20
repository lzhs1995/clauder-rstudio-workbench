"""Verify actual installed runtimes, separately from a source compatibility check.

The probes start new, bounded processes. They do not reload existing RStudio or
MCP processes and therefore never establish what an existing client has loaded.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


PYTHON_PROBE = """
import hashlib, importlib.metadata as m, json, sys
import clauder_mcp.server as server
from pathlib import Path
p = Path(server.__file__).resolve()
result = {'python': sys.executable, 'bridge_version': m.version('clauder-mcp'),
          'bridge_source': str(p), 'bridge_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
try:
    import clauder_workbench
    result['workbench_version'] = m.version('clauder-rstudio-workbench-harness')
    result['workbench_source'] = str(Path(clauder_workbench.__file__).resolve())
except (m.PackageNotFoundError, ModuleNotFoundError):
    result['workbench_version'] = None
    result['workbench_source'] = None
print('CLAUDER_INSTALL_PROBE=' + json.dumps(result))
"""


def _probe(command: list[str], marker: str) -> dict:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="strict", timeout=180, check=True)
    matches = [line[len(marker):] for line in result.stdout.splitlines() if line.startswith(marker)]
    if len(matches) != 1:
        raise RuntimeError("Runtime probe did not return exactly one structured result")
    return json.loads(matches[0])


def verify_bridge(manifest: dict, python: Path, *, require_workbench: bool = False) -> dict:
    actual = _probe([str(python), "-I", "-B", "-c", PYTHON_PROBE], "CLAUDER_INSTALL_PROBE=")
    expected_hash = manifest["critical_file_sha256"]["clauder-mcp/src/clauder_mcp/server.py"]
    checks = {
        "bridge_version": actual["bridge_version"] == manifest["mcp_bridge_version"],
        "bridge_source_hash": actual["bridge_sha256"] == expected_hash,
    }
    if require_workbench:
        checks["workbench_version"] = actual["workbench_version"] == manifest["workbench_version"]
    return {"ok": all(checks.values()), "checks": checks, "actual": actual,
            "scope": "fresh probe process; not the running agent's MCP process"}


def verify_r(manifest: dict, rscript: Path, library: Path | None = None) -> dict:
    lib = json.dumps(str(library.resolve()).replace("\\", "/"), ensure_ascii=True) if library else "NULL"
    code = (
        f"candidate_lib <- {lib}; "
        "if (!is.null(candidate_lib)) .libPaths(c(candidate_lib, .libPaths())); "
        "ns <- loadNamespace('ClaudeR'); "
        "cat('CLAUDER_R_PROBE=', jsonlite::toJSON(list("
        "version=as.character(getNamespaceVersion(ns)), "
        "path=normalizePath(getNamespaceInfo(ns, 'path'), winslash='/'), "
        "R_version=R.version.string), auto_unbox=TRUE), '\\n', sep='')"
    )
    actual = _probe([str(rscript), "--vanilla", "-e", code], "CLAUDER_R_PROBE=")
    checks = {"R_package_version": actual["version"] == manifest["r_package_version"]}
    if library:
        checks["R_package_library"] = Path(actual["path"]).resolve() == (library / "ClaudeR").resolve()
    return {"ok": all(checks.values()), "checks": checks, "actual": actual,
            "scope": "fresh R process; not an existing RStudio namespace"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--rscript", type=Path)
    parser.add_argument("--r-library", type=Path)
    parser.add_argument("--require-workbench", action="store_true")
    args = parser.parse_args(argv)
    if not args.python and not args.rscript:
        parser.error("specify a bridge Python and/or Rscript")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = {}
    if args.python:
        result["bridge"] = verify_bridge(manifest, args.python, require_workbench=args.require_workbench)
    if args.rscript:
        result["R"] = verify_r(manifest, args.rscript, args.r_library)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(x["ok"] for x in result.values()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
