#!/bin/bash
# setup_smb.sh — Install CIFS/SMB client and mount FRITZ.NAS Spotibox share
# Mount point: /mnt/albums (used by spotibox to load albums.py)

set -euo pipefail

SMB_SHARE="//fritz.nas/FRITZ.NAS"
MOUNT_POINT="/mnt/albums"
SMB_USER="spotibox"
SMB_PASS="todhoschi"
CREDENTIALS_FILE="/etc/smbcredentials_fritznas"

echo "=== Installing cifs-utils ==="
apt-get update -qq
apt-get install -y cifs-utils

echo "=== Creating credentials file ==="
cat > "$CREDENTIALS_FILE" <<EOF
username=${SMB_USER}
password=${SMB_PASS}
EOF
chmod 600 "$CREDENTIALS_FILE"

echo "=== Creating mount point ==="
mkdir -p "$MOUNT_POINT"

echo "=== Adding fstab entry ==="
FSTAB_ENTRY="${SMB_SHARE} ${MOUNT_POINT} cifs credentials=${CREDENTIALS_FILE},rw,uid=1000,gid=1000,iocharset=utf8,vers=3.0,nofail,_netdev,x-systemd.after=network-online.target 0 0"

echo ""
echo "NOTE: Never create/edit files on the share from macOS!"
echo "      macOS writes resource forks that cause 'Stale file handle' errors on FRITZ.NAS."
echo "      Always edit files from Linux (this Pi) or Windows."
echo ""

# Remove existing entry for this mount point if present
sed -i "\|${MOUNT_POINT}|d" /etc/fstab

echo "$FSTAB_ENTRY" >> /etc/fstab

echo "=== Mounting share ==="
systemctl daemon-reload
mount "$MOUNT_POINT" || mount -a

echo "=== Verifying ==="
echo "=== Creating Spotibox subfolder (if needed) ==="
mkdir -p "$MOUNT_POINT/Spotibox"

if cat "$MOUNT_POINT/Spotibox/albums.py" > /dev/null 2>&1; then
    echo "SUCCESS: albums.py readable at ${MOUNT_POINT}/Spotibox/albums.py"
else
    echo "WARNING: albums.py not found — place it in the Spotibox folder on FRITZ.NAS"
    echo "         IMPORTANT: Create/edit it from Linux, NOT macOS (macOS creates broken resource forks)"
fi
ls -la "$MOUNT_POINT/Spotibox/"
