#!/bin/bash
# ============================================================================
# Wall Clock - Raspberry Pi Installation Script
# Automated installation with cleanup of old versions
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/home/admin/wallclock"
SERVICE_NAME="wallclock"
OLD_SERVICE_NAME="wall-clock"
USER="admin"

# Banner
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Wall Clock - Pi Installation${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}  [OK]${NC} $1"
}

print_error() {
    echo -e "${RED}  [ERROR]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}  [INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}  [WARNING]${NC} $1"
}

# Check if running as root (via sudo)
if [ "$EUID" -ne 0 ]; then
    print_error "Please run with sudo: sudo ./install.sh"
    exit 1
fi

# ============================================================================
# STEP 0: Cleanup Old Installation
# ============================================================================

print_status "Cleaning up old installations..."

# Stop and disable old wall-clock service (if exists)
if systemctl is-active --quiet wall-clock.service 2>/dev/null; then
    print_info "Stopping old wall-clock service..."
    systemctl stop wall-clock.service
    systemctl disable wall-clock.service > /dev/null 2>&1 || true
    rm -f /etc/systemd/system/wall-clock.service
    print_success "Old wall-clock service removed"
fi

# Stop and disable old wallclock service (if exists from previous attempts)
if systemctl is-active --quiet wallclock.service 2>/dev/null; then
    print_info "Stopping existing wallclock service..."
    systemctl stop wallclock.service
    systemctl disable wallclock.service > /dev/null 2>&1 || true
    rm -f /etc/systemd/system/wallclock.service
    print_success "Existing wallclock service stopped"
fi

# Kill any running wall_clock.py processes
if pgrep -f "wall_clock.py" > /dev/null; then
    print_info "Stopping old wall_clock.py processes..."
    pkill -f "wall_clock.py" || true
    sleep 2
    print_success "Old Python processes stopped"
fi

# Kill any running backend_api.py processes
if pgrep -f "backend_api.py" > /dev/null; then
    print_info "Stopping existing backend processes..."
    pkill -f "backend_api.py" || true
    sleep 2
    print_success "Existing backend stopped"
fi

# Remove old autostart entries
if [ -f "/home/admin/.config/autostart/wall-clock.desktop" ]; then
    print_info "Removing old autostart configuration..."
    rm -f /home/admin/.config/autostart/wall-clock.desktop
    print_success "Old autostart removed"
fi

# Remove old wallclock autostart if it exists
if [ -f "/home/admin/.config/autostart/wallclock.desktop" ]; then
    rm -f /home/admin/.config/autostart/wallclock.desktop
    print_info "Existing wallclock autostart removed"
fi

# Clean up old installation directories (but keep the new one)
if [ -d "/home/admin/wall-clock" ]; then
    print_info "Removing old wall-clock directory..."
    rm -rf /home/admin/wall-clock
    print_success "Old installation directory removed"
fi

if [ -d "/home/admin/wall_clock_install" ]; then
    print_info "Removing old wall_clock_install directory..."
    rm -rf /home/admin/wall_clock_install
    print_success "Old install directory removed"
fi

# Reload systemd to clear removed services
systemctl daemon-reload

print_success "Cleanup completed"
echo ""

# ============================================================================
# STEP 1: System Update
# ============================================================================

print_status "Updating system packages..."
apt-get update -qq > /dev/null 2>&1
print_success "System packages updated"
echo ""

# ============================================================================
# STEP 2: Install System Dependencies
# ============================================================================

print_status "Installing system dependencies..."

# Install Python 3 and pip
#print_info "Installing Python 3 and pip..."
#apt-get install -y python3 python3-pip python3-venv > /dev/null 2>&1

# Install Chromium browser for kiosk mode
#print_info "Installing Chromium browser..."
#apt-get install -y chromium-browser unclutter xdotool > /dev/null 2>&1

# Install x11-xserver-utils for screen control
print_info "Installing X11 utilities..."
apt-get install -y x11-xserver-utils > /dev/null 2>&1

print_success "System dependencies installed"
echo ""

# ============================================================================
# STEP 3: Install Python Dependencies (using virtual environment)
# ============================================================================

print_status "Installing Python dependencies..."

# Change to install directory
cd $INSTALL_DIR

# Create virtual environment if it doesn't exist
if [ ! -d "$INSTALL_DIR/venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv $INSTALL_DIR/venv
fi

# Install Python packages in virtual environment
print_info "Installing FastAPI, uvicorn, and other packages..."
$INSTALL_DIR/venv/bin/pip install --upgrade pip > /dev/null 2>&1
$INSTALL_DIR/venv/bin/pip install -r requirements.txt > /dev/null 2>&1

print_success "Python dependencies installed"
echo ""

# ============================================================================
# STEP 4: Create Notes Directory
# ============================================================================

print_status "Creating notes directory..."
mkdir -p /home/admin/ClockNotes
touch /home/admin/ClockNotes/ClockNote.txt
chown -R $USER:$USER /home/admin/ClockNotes
print_success "Notes directory created at /home/admin/ClockNotes"
echo ""

# ============================================================================
# STEP 5: Create Systemd Service for Backend
# ============================================================================

print_status "Creating systemd service for backend..."

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Wall Clock Backend API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/backend_api.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start service
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}.service > /dev/null 2>&1
systemctl start ${SERVICE_NAME}.service

# Wait for service to start
sleep 3

# Check if service started successfully
if systemctl is-active --quiet ${SERVICE_NAME}.service; then
    print_success "Backend service created and started"
else
    print_warning "Backend service created but may have issues"
    print_info "Check logs: journalctl -u ${SERVICE_NAME} -n 50"
fi

print_info "Service name: ${SERVICE_NAME}"
echo ""

# ============================================================================
# STEP 6: Disable Screen Blanking and Screensaver
# ============================================================================

print_status "Disabling screen blanking and screensaver..."

# Create autostart directory if it doesn't exist
mkdir -p /home/admin/.config/lxsession/LXDE-pi
mkdir -p /home/admin/.config/autostart

# Disable screen blanking in LXDE autostart
cat > /home/admin/.config/lxsession/LXDE-pi/autostart << 'EOF'
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xscreensaver -no-splash

# Disable screen blanking
@xset s off
@xset -dpms
@xset s noblank

# Hide mouse cursor
@unclutter -idle 0.5 -root
EOF

chown -R $USER:$USER /home/admin/.config/lxsession
print_success "Screen blanking disabled"
echo ""

# ============================================================================
# STEP 7: Create Auto-start Script for Chromium Kiosk
# ============================================================================

print_status "Creating auto-start script for kiosk mode..."

cat > /home/admin/.config/autostart/wallclock.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Wall Clock Display
Exec=/home/admin/wallclock/launch-kiosk.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

# Create the launch script
cat > /home/admin/wallclock/launch-kiosk.sh << 'EOF'
#!/bin/bash
# Wait for the backend to start
sleep 10

# Disable screen blanking
xset s off
xset -dpms
xset s noblank

# Hide mouse cursor after 0.5 seconds of inactivity
unclutter -idle 0.5 -root &

# Kill any existing Chromium instances
pkill chromium-browser

# Launch Chromium in kiosk mode
chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --app=http://localhost:8000 \
    --start-fullscreen \
    --window-position=0,0 \
    --window-size=1920,1080
EOF

chmod +x /home/admin/wallclock/launch-kiosk.sh
chown $USER:$USER /home/admin/wallclock/launch-kiosk.sh
chown $USER:$USER /home/admin/.config/autostart/wallclock.desktop

print_success "Kiosk mode configured"
print_info "Display will auto-launch on boot"
echo ""

# ============================================================================
# STEP 8: Set File Permissions
# ============================================================================

print_status "Setting file permissions..."
chown -R $USER:$USER $INSTALL_DIR
chmod +x $INSTALL_DIR/backend_api.py
print_success "Permissions set"
echo ""

# ============================================================================
# STEP 9: Verify Installation
# ============================================================================

print_status "Verifying installation..."

# Check if service is running
if systemctl is-active --quiet ${SERVICE_NAME}.service; then
    print_success "Backend service is running"
else
    print_error "Backend service failed to start"
    print_info "Check logs: journalctl -u ${SERVICE_NAME} -n 50"
fi

# Check if backend is responding
sleep 3
if curl -s http://localhost:8000/api/time > /dev/null 2>&1; then
    print_success "Backend API is responding"
else
    print_warning "Backend API may still be starting..."
    print_info "Try: curl http://localhost:8000/api/time"
fi

echo ""

# ============================================================================
# Installation Complete
# ============================================================================

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${CYAN}Summary:${NC}"
echo -e "  ${YELLOW}✓${NC} Old installations cleaned up"
echo -e "  ${YELLOW}✓${NC} Backend service: ${SERVICE_NAME}"
echo -e "  ${YELLOW}✓${NC} Installation directory: ${INSTALL_DIR}"
echo -e "  ${YELLOW}✓${NC} Notes directory: /home/admin/ClockNotes"
echo -e "  ${YELLOW}✓${NC} Auto-start on boot: Enabled"
echo -e "  ${YELLOW}✓${NC} Kiosk mode: Configured"
echo ""
echo -e "${CYAN}Access your wall clock:${NC}"
echo -e "  ${YELLOW}•${NC} Local: http://localhost:8000"
echo -e "  ${YELLOW}•${NC} Network: http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo -e "  ${YELLOW}•${NC} View logs: ${GREEN}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  ${YELLOW}•${NC} Restart service: ${GREEN}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  ${YELLOW}•${NC} Stop service: ${GREEN}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo -e "  ${YELLOW}•${NC} Service status: ${GREEN}systemctl status ${SERVICE_NAME}${NC}"
echo ""
echo -e "${CYAN}Next steps:${NC}"
echo -e "  ${YELLOW}1.${NC} Add your notes to: /home/admin/ClockNotes/ClockNote.txt"
echo -e "  ${YELLOW}2.${NC} Reboot to start kiosk mode: ${GREEN}sudo reboot${NC}"
echo -e "  ${YELLOW}3.${NC} Or manually test: ${GREEN}/home/admin/wallclock/launch-kiosk.sh${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT:${NC} The new web-based wall clock will replace the old Tkinter version."
echo -e "${YELLOW}The display will automatically launch in kiosk mode after reboot.${NC}"
echo ""
echo -e "${GREEN}============================================${NC}"

# Option to reboot now
echo ""
echo -e "${YELLOW}Would you like to reboot now to start the new wall clock? (y/n)${NC}"
read -t 30 -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Rebooting in 5 seconds..."
    sleep 5
    reboot
else
    print_info "Installation complete."
    print_warning "Remember to reboot to see the new wall clock in kiosk mode!"
    echo ""
    print_info "To reboot: ${GREEN}sudo reboot${NC}"
    echo ""
fi
