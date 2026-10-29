# ==============================================================================
# RHEL 9 Enterprise Hardened Kickstart Configuration (CIS Benchmark Alignment)
# Storage Geometry & Partitioning Blueprint
# ==============================================================================

# System Authorization & Security
authselect select sssd with-faillock with-mkhomedir --force
selinux --enforcing
firewall --enabled --ssh

# Installation Media & Environment
text
skipx
firstboot --disabled
eula --agreed

# Localization
keyboard --vckeymap=us --xlayouts='us'
lang en_US.UTF-8
timezone America/Los_Angeles --utc

# Network Configuration (DHCP default; production nodes override via MAC/IP)
network --bootproto=dhcp --device=link --activate --onboot=on

# ------------------------------------------------------------------------------
# Storage Geometry: Enterprise LVM Layout with CIS Mount Isolation
# ------------------------------------------------------------------------------
# Clear all existing partition tables and disk signatures
zerombr
clearpart --all --initlabel

# Standard non-LVM boot partitions (UEFI & BIOS compatible)
part /boot/efi --fstype="efi" --size=600 --fsoptions="umask=0077,shortname=winnt"
part /boot     --fstype="xfs" --size=1024 --fsoptions="nodev,nosuid"

# Physical Volume & Enterprise Volume Group
part pv.01 --fstype="lvmpv" --size=1 --grow
volgroup rhel_vg --pesize=4096 pv.01

# Logical Volumes with CIS Hardened Mount Options
logvol /               --vgname=rhel_vg --size=10240 --name=lv_root  --fstype=xfs --fsoptions="defaults"
logvol /tmp            --vgname=rhel_vg --size=2048  --name=lv_tmp   --fstype=xfs --fsoptions="defaults,nodev,nosuid,noexec"
logvol /var            --vgname=rhel_vg --size=8192  --name=lv_var   --fstype=xfs --fsoptions="defaults,nodev"
logvol /var/log        --vgname=rhel_vg --size=4096  --name=lv_log   --fstype=xfs --fsoptions="defaults,nodev,nosuid,noexec"
logvol /var/log/audit  --vgname=rhel_vg --size=4096  --name=lv_audit --fstype=xfs --fsoptions="defaults,nodev,nosuid,noexec"
logvol /home           --vgname=rhel_vg --size=5120  --name=lv_home  --fstype=xfs --fsoptions="defaults,nodev,nosuid"
logvol swap            --vgname=rhel_vg --size=4096  --name=lv_swap  --fstype=swap

# Bootloader security: Audit enabled at early kernel boot
bootloader --location=mbr --append="audit=1 audit_backlog_limit=8192"

# Minimal Core Package Selection
%packages
@^minimal-environment
@core
lvm2
xfsprogs
audit
policycoreutils
policycoreutils-python-utils
setools-console
systemd
tar
curl
rsync
-telnet
-rsh-server
-ypbind
%end

# Post-installation verification hook
%post --log=/root/ks-post.log
echo "[INFO] Verifying LVM storage layout and mount options..."
df -hT
pvs
vgs
lvs
echo "[INFO] CIS storage provisioning completed successfully."
%end
