# rhel-node-engine

**Enterprise Hardened Node & Confinement Engine for Red Hat Enterprise Linux (RHEL 9)**

An end-to-end, CIS-Benchmark-compliant reference architecture and administrative toolsuite for enterprise Linux host engineering. Built from the ground up to demonstrate production system administration across storage geometry, kernel sandboxing, Mandatory Access Control (SELinux), and forensic auditing.

---

## Architectural Pillars

```
+---------------------------------------------------------------------------------+
|                                rhel-node-engine                                 |
+---------------------------------------------------------------------------------+
|  1. Storage Geometry (LVM + XFS)                                                |
|     - CIS mount isolation: /tmp, /var, /var/log, /var/log/audit, /home           |
|     - Kernel security mount flags: nodev, nosuid, noexec                        |
|     - Zero-downtime live volume expansion: lvextend + xfs_growfs                |
+---------------------------------------------------------------------------------+
|  2. Hardened Service Layer (Systemd + Cgroups v2)                               |
|     - Dedicated unprivileged system identity (UID < 1000, nologin)              |
|     - VFS Namespace isolation: ProtectSystem=strict, ProtectHome=yes            |
|     - Resource boundaries: MemoryMax=128M, CPUQuota=25%                         |
|     - Self-healing watchdog: Type=notify, WatchdogSec=10s, auto-resurrection    |
+---------------------------------------------------------------------------------+
|  3. Mandatory Access Control (SELinux)                                          |
|     - Custom Type Enforcement (node_agent.te) & File Contexts (node_agent.fc)   |
|     - Policy compiler pipeline: checkmodule -> semodule_package -> node_agent.pp|
|     - Strict domain confinement: blocks unprivileged lateral movement           |
+---------------------------------------------------------------------------------+
|  4. Forensic Kernel Auditing (Auditd)                                           |
|     - Real-time kernel syscall traps on binary & log tampering                  |
|     - AUID (Audit User ID) immutability across sudo / privilege escalation      |
|     - ausearch event decoding & aureport compliance executive summaries         |
+---------------------------------------------------------------------------------+
```

---

## 1. Storage Geometry & LVM Layout

Enterprise RHEL systems mandate partition isolation to prevent resource exhaustion and execution vulnerabilities (CIS Controls 1.1.2 - 1.1.15).

### Logical Volume Matrix

| Mount Point | Logical Volume | Filesystem | Mount Flags | Security / CIS Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `/` | `lv_root` | XFS | `defaults` | Base OS binaries & core system libraries |
| `/tmp` | `lv_tmp` | XFS | `nodev,nosuid,noexec` | Blocks binary execution & SUID escalation |
| `/var` | `lv_var` | XFS | `nodev` | Isolates spool and variable data from root |
| `/var/log` | `lv_log` | XFS | `nodev,nosuid,noexec` | Protects system logs; prevents disk fill exploits |
| `/var/log/audit`| `lv_audit` | XFS | `nodev,nosuid,noexec` | Dedicated partition ensuring auditd never halts |
| `/home` | `lv_home` | XFS | `nodev,nosuid` | User workspace isolation with SUID disabled |

### Verified Security Proofs

#### A. Kernel `noexec` Enforcement
Placing an executable script on a `noexec`-mounted volume is intercepted directly at the VFS syscall layer:
```bash
$ sudo chmod +x /mnt/test_tmp/exploit.sh
$ /mnt/test_tmp/exploit.sh
bash: /mnt/test_tmp/exploit.sh: Permission denied
```

#### B. Zero-Downtime Live Online Resizing
Filesystems are expanded while mounted and serving traffic:
```bash
# 1. Expand LVM container by +2GB
sudo lvextend -L +2G /dev/rhel_vg/lv_log

# 2. Grow active XFS allocation groups live
sudo xfs_growfs /mnt/test_log
```
*Result:* Filesystem capacity expanded from 2.0GB to 4.0GB with zero unmount or reboot.

---

## 2. Hardened Systemd Service Architecture

The core daemon (`node_agent.py`) implements the native `sd_notify` protocol over Unix domain datagram sockets (`$NOTIFY_SOCKET`).

### Production Unit Definition (`/etc/systemd/system/node-agent.service`)

```ini
[Unit]
Description=Enterprise Node Agent Engine
After=network.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=notify
WatchdogSec=10s
Restart=always
RestartSec=2s
ExecStart=/usr/local/bin/node_agent

User=node-agent
Group=node-agent

# Kernel Namespace Sandboxing
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
CapabilityBoundingSet=
ReadWritePaths=/var/log/node-agent

# Cgroups v2 Resource Governance
MemoryMax=128M
CPUQuota=25%

[Install]
WantedBy=multi-user.target
```

### Self-Healing Watchdog Verification

When a process deadlock is simulated via `kill -STOP <PID>`:
1. `systemd` detects the missed heartbeat within `WatchdogSec=10s`.
2. It sends `SIGABRT` to terminate the hung thread.
3. It cleans up the cgroup and automatically respawns a healthy instance with a new PID:

```text
node-agent.service: Watchdog timeout (limit 10s)!
systemd[1]: node-agent.service: Killing process 74501 (python3) with signal SIGABRT.
systemd[1]: node-agent.service: Main process exited, code=dumped, status=6/ABRT
systemd[1]: node-agent.service: Failed with result 'watchdog'.
...
node_agent[75236]: [HEARTBEAT] Cycle 8: System healthy.
```

---

## 3. SELinux Policy Engineering

Rather than disabling Mandatory Access Control (`setenforce 0`), a custom policy module confines the daemon within the `node_agent_t` domain.

### Compilation Pipeline

```bash
# 1. Compile Type Enforcement (.te) into binary module (.mod)
checkmodule -M -m -o node_agent.mod node_agent.te

# 2. Package module with File Contexts (.fc) into Policy Package (.pp)
semodule_package -o node_agent.pp -m node_agent.mod -f node_agent.fc

# 3. Deploy to production RHEL kernel
sudo semodule -i node_agent.pp
sudo restorecon -v /usr/local/bin/node_agent
```

---

## 4. Kernel Auditing (`auditd`) & Forensic Accountability

Critical files and execution binaries are monitored via the kernel audit subsystem.

### Watch Rule Injection

```bash
sudo auditctl -w /usr/local/bin/node_agent -p rwa -k node_agent_audit
```

### Forensic Reconstruction (`ausearch`)

When any process interacts with the binary, the kernel records:
* Exact syscall (`openat`), working directory (`cwd`), and command string (`proctitle`).
* **Audit User ID (`auid`)**: Tracks the original human user identity across `sudo` privilege escalations.

```text
type=PROCTITLE msg=audit(...): proctitle=cat /usr/local/bin/node_agent
type=PATH msg=audit(...): item=0 name=/usr/local/bin/node_agent inode=51388738 ouid=root
type=SYSCALL msg=audit(...): syscall=openat success=yes ppid=74747 pid=78885 auid=pat uid=pat comm=cat key=node_agent_audit
```

### Executive Compliance Reporting (`aureport`)

```text
$ sudo aureport -k

Key Report
===============================================
# date time key success exe auid event
===============================================
1. 10/29/26 16:52:59 node_agent_audit yes /usr/sbin/auditctl 1000 414
2. 10/29/26 16:53:46 node_agent_audit yes /usr/lib/cargo/bin/coreutils/cat 1000 420
```

---

## Repository Structure

```
.
├── README.md                  # System architecture & verification guide
├── .gitignore                 # Excludes raw block storage images & artifacts
├── node_agent.py              # Self-healing Python daemon implementing sd_notify
├── kickstart/
│   ├── cis-rhel9-storage.ks   # Automated RHEL 9 Kickstart installation blueprint
│   └── kickstart-validator.py # Syntax & CIS partition validation tool
├── storage/
│   └── lvm_layout.json        # Declarative CIS partition schema
├── systemd/
│   └── node-agent.service     # Hardened unit definition (cgroups v2 + sandboxing)
├── selinux/
│   ├── node_agent.fc          # File Context specifications
│   ├── node_agent.te          # Type Enforcement source rules
│   ├── node_agent.mod         # Compiled binary module
│   └── node_agent.pp          # Deployable SELinux Policy Package
└── audit/
    └── 99-node-agent.rules    # Persistent kernel audit rules matrix
```

---

## Author
**Patrick Isles**  
Systems & Infrastructure Engineering  
Portland, OR
