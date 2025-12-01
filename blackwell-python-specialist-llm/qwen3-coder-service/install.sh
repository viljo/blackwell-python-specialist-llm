#!/bin/bash
set -e

SERVICE_NAME="qwen3-coder"
INSTALL_DIR="/opt/qwen3-coder-service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Qwen3-Coder service..."

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run as root (sudo ./install.sh)"
    exit 1
fi

# Stop existing service if running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping existing service..."
    systemctl stop "$SERVICE_NAME"
fi

# Copy project to /opt
echo "Copying project to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
rm -f "$INSTALL_DIR/install.sh"  # Don't need install script in /opt

# Update service file with correct path
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" "$INSTALL_DIR/$SERVICE_NAME.service"

# Install systemd service
echo "Installing systemd service..."
cp "$INSTALL_DIR/$SERVICE_NAME.service" /etc/systemd/system/
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting service..."
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "Installation complete!"
echo ""
echo "Commands:"
echo "  sudo systemctl status $SERVICE_NAME   # Check status"
echo "  sudo systemctl stop $SERVICE_NAME     # Stop service"
echo "  sudo systemctl start $SERVICE_NAME    # Start service"
echo "  sudo systemctl restart $SERVICE_NAME  # Restart service"
echo "  journalctl -u $SERVICE_NAME -f        # View logs"
echo ""
echo "Docker logs:"
echo "  docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
