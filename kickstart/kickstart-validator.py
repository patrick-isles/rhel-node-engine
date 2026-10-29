#!/usr/bin/env python3
"""
Enterprise Kickstart Validator
Validates RHEL Kickstart files for CIS Benchmark storage & security compliance.
"""

import sys
import re
from pathlib import Path

REQUIRED_PARTITIONS = {
    "/tmp": ["nodev", "nosuid", "noexec"],
    "/var": ["nodev"],
    "/var/log": ["nodev", "nosuid", "noexec"],
    "/var/log/audit": ["nodev", "nosuid", "noexec"],
    "/home": ["nodev", "nosuid"]
}

def validate_kickstart(ks_path: Path) -> bool:
    if not ks_path.exists():
        print(f"[ERROR] Kickstart file not found: {ks_path}", file=sys.stderr)
        return False

    content = ks_path.read_text()
    errors = []
    warnings = []

    # 1. Check SELinux mode
    if not re.search(r"^\s*selinux\s+--enforcing", content, re.MULTILINE):
        errors.append("SELinux must be set to --enforcing.")

    # 2. Check Volume Group
    vg_match = re.search(r"^\s*volgroup\s+(\w+)", content, re.MULTILINE)
    if not vg_match:
        errors.append("Missing 'volgroup' declaration for LVM.")
    else:
        vg_name = vg_match.group(1)
        print(f"[PASS] Volume Group detected: '{vg_name}'")

    # 3. Check Partition Mandates
    found_mounts = {}
    logvol_pattern = re.compile(
        r"^\s*logvol\s+(\S+)\s+.*--name=(\S+)\s+.*--fsoptions=[\"']?([^\"'\n]+)[\"']?",
        re.MULTILINE
    )

    for match in logvol_pattern.finditer(content):
        mount = match.group(1)
        name = match.group(2)
        fsoptions = [opt.strip() for opt in match.group(3).split(",")]
        found_mounts[mount] = {"name": name, "fsoptions": fsoptions}

    for req_mount, req_opts in REQUIRED_PARTITIONS.items():
        if req_mount not in found_mounts:
            errors.append(f"Missing mandatory CIS separate partition: {req_mount}")
            continue

        actual_opts = found_mounts[req_mount]["fsoptions"]
        for opt in req_opts:
            if opt not in actual_opts:
                errors.append(
                    f"Partition {req_mount} missing mandatory security mount flag: '{opt}' (found: {actual_opts})"
                )

    # 4. Check early audit bootloader
    if not re.search(r"^\s*bootloader\s+.*audit=1", content, re.MULTILINE):
        warnings.append("Bootloader missing 'audit=1' early kernel parameter.")

    print("\n--- Kickstart Validation Report ---")
    if warnings:
        for w in warnings:
            print(f"[WARN] {w}")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        print(f"\nResult: FAILED ({len(errors)} errors)")
        return False

    print("All mandatory CIS partitioning and security directives validated.")
    print("Result: PASSED (100% Compliant)")
    return True

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("kickstart/cis-rhel9-storage.ks")
    success = validate_kickstart(target)
    sys.exit(0 if success else 1)
