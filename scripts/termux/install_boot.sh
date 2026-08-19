#!/data/data/com.termux/files/usr/bin/bash
# 安装 Termux:Boot 自启动脚本

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOT_DIR="$HOME/.termux/boot"
TARGET="$BOOT_DIR/start_loam_boot.sh"

mkdir -p "$BOOT_DIR"

cat >"$TARGET" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
bash "$SCRIPT_DIR/boot_loam.sh"
EOF

chmod +x "$TARGET"

echo "已安装自启动脚本: $TARGET"
echo "请确认你已安装并授权 Termux:Boot 应用。"