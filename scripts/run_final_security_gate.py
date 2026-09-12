from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# Run only TW-SEC-FINAL-owned audit files; do not absorb unrelated tests/security files.
GROUPS=[
    ("TW-002/TW-011 rate limiting", ["tests/test_token_workspace_rate_limit.py","tests/test_shared_rate_limit_store.py"]),
    ("TW-003/TW-009 Jupiter coordination", ["tests/test_jupiter_swap_service.py"]),
    ("TW-010 headers/boundary", ["tests/test_production_security.py","tests/test_tw_sec_010_security_headers.py"]),
    ("FINAL abuse/security harness", [
        "tests/security/test_final_request_boundary.py",
        "tests/security/test_final_rate_limit_abuse.py",
        "tests/security/test_final_multi_replica.py",
        "tests/security/test_final_security_headers.py",
        "tests/security/test_final_source_audit.py",
        "tests/security/test_final_jupiter_invariants.py",
    ]),
]

def main():
    failures=[]
    for name, paths in GROUPS:
        existing=[p for p in paths if (ROOT/p).exists()]
        if not existing:
            print(f"[SKIP] {name}: no matching tests found")
            continue
        result=subprocess.run([sys.executable,"-m","pytest",*existing,"-q"],cwd=ROOT)
        if result.returncode:
            failures.append(name)
            print(f"[FAIL] {name}")
        else:
            print(f"[PASS] {name}")

    archive_candidates=list((ROOT/"tests").glob("*archive*.py")) + list((ROOT/"tests").glob("*discovery*storage*.py"))
    if archive_candidates:
        args=[str(p.relative_to(ROOT)) for p in archive_candidates]
        result=subprocess.run([sys.executable,"-m","pytest",*args,"-q"],cwd=ROOT)
        if result.returncode:
            failures.append("TW-001 archive read/write regression")
            print("[FAIL] TW-001 archive read/write regression")
        else:
            print("[PASS] TW-001 archive read/write regression")
    else:
        print("[REVIEW] TW-001 archive-specific regression test not auto-discovered; verify before Railway staging")

    if failures:
        print("FINAL SECURITY GATE = FAIL")
        print("Failed groups: " + ", ".join(failures))
        return 1
    print("FINAL SECURITY GATE = PASS (local harness)")
    print("Railway staging still requires live proxy/client-IP and 1→2 replica verification.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
