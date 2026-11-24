#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# EKA DASHBOARD — UNIVERSAL LINUX INSTALLER (CROSS-DISTRO & NON-DESTRUCTIVE)
# Mendukung: Debian/Ubuntu (apt), Fedora/RHEL/Rocky (dnf/yum),
#            Arch/Garuda/Manjaro (pacman), openSUSE (zypper), Alpine (apk)
#
# Opsi Environment / Flag:
#   DASHBOARD_PORT=80           Port host untuk Eka Dashboard (default: 80)
#   INSTALL_DIR=/opt/eka_dashboard  Direktori target instalasi
#   --port <PORT>               Set port host (misal: --port 8080)
#   --dir <PATH>                Set direktori instalasi
#   --reset-admin               Hapus data/security_config.json untuk ulang Setup Wizard
#   --shift-casaos              Pindahkan port CasaOS dari 80 ke 9999 bila terdeteksi
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DASHBOARD_PORT="${DASHBOARD_PORT:-80}"
CURRENT_DIR="$(pwd)"
if [ -f "$CURRENT_DIR/docker-compose.yml" ] && [ -f "$CURRENT_DIR/app.py" ]; then
    INSTALL_DIR="${INSTALL_DIR:-$CURRENT_DIR}"
else
    INSTALL_DIR="${INSTALL_DIR:-/opt/eka_dashboard}"
fi
RESET_ADMIN=0
SHIFT_CASAOS=0

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            DASHBOARD_PORT="${2:-80}"
            shift 2
            ;;
        --dir)
            INSTALL_DIR="${2:-$INSTALL_DIR}"
            shift 2
            ;;
        --reset-admin)
            RESET_ADMIN=1
            shift
            ;;
        --shift-casaos)
            SHIFT_CASAOS=1
            shift
            ;;
        -h|--help)
            echo "Usage: sudo bash install.sh [--port 8080] [--dir /opt/eka_dashboard] [--reset-admin] [--shift-casaos]"
            exit 0
            ;;
        *)
            echo -e "${YELLOW}[WARN] Opsi tidak dikenal diabaikan: $1${NC}"
            shift
            ;;
    esac
done

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   EKA DASHBOARD - UNIVERSAL LINUX INSTALLER     ${NC}"
echo -e "${BLUE}=================================================${NC}"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo -e "${RED}[ERROR] Jalankan skrip ini dengan hak root/sudo.${NC}"
    echo "Usage: sudo bash install.sh [--port 8080]"
    exit 1
fi

# --- Deteksi Distro & Package Manager ---
detect_pkg_manager() {
    for pm in apt-get dnf yum pacman zypper apk; do
        if command -v "$pm" >/dev/null 2>&1; then
            echo "$pm"
            return 0
        fi
    done
    echo "unknown"
}

install_pkg() {
    local pm="$1"
    shift
    case "$pm" in
        apt-get) DEBIAN_FRONTEND=noninteractive apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" ;;
        dnf)     dnf install -y "$@" ;;
        yum)     yum install -y "$@" ;;
        pacman)  pacman -Sy --noconfirm "$@" ;;
        zypper)  zypper --non-interactive install "$@" ;;
        apk)     apk add --no-cache "$@" ;;
        *)       return 1 ;;
    esac
}

PKG_MGR="$(detect_pkg_manager)"
echo -e "${BLUE}[INFO] Package manager terdeteksi: ${PKG_MGR}${NC}"
echo -e "${BLUE}[INFO] Direktori instalasi       : ${INSTALL_DIR}${NC}"
echo -e "${BLUE}[INFO] Port host target          : ${DASHBOARD_PORT}${NC}"

# --- STEP 1: Sinkronisasi direktori instalasi tanpa menimpa ./data ---
if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    echo -e "${BLUE}[INFO] Menyalin berkas proyek ke ${INSTALL_DIR} (mempertahankan data/)...${NC}"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --exclude 'data/' --exclude '.git/' "$CURRENT_DIR/" "$INSTALL_DIR/"
    else
        (cd "$CURRENT_DIR" && tar --exclude='./data' --exclude='./.git' -cf - .) | (cd "$INSTALL_DIR" && tar -xf -)
    fi
    cd "$INSTALL_DIR"
    chmod +x install.sh 2>/dev/null || true
fi

# --- STEP 2: Penanganan opsional CasaOS (hanya bila diminta) ---
CASA_PORT_MOVED=0
if [ "$SHIFT_CASAOS" -eq 1 ] && [ "$DASHBOARD_PORT" = "80" ] && [ -f "/etc/casaos/gateway.ini" ]; then
    CURRENT_CASA_PORT=$(grep -oE 'port[[:space:]]*=[[:space:]]*[0-9]+' /etc/casaos/gateway.ini | grep -oE '[0-9]+' | head -n1 || true)
    if [ "$CURRENT_CASA_PORT" = "80" ]; then
        echo -e "${YELLOW}[ACTION] Memindahkan port CasaOS dari 80 ke 9999...${NC}"
        cp /etc/casaos/gateway.ini /etc/casaos/gateway.ini.bak
        sed -i -E 's/port[[:space:]]*=[[:space:]]*80/port = 9999/g' /etc/casaos/gateway.ini
        systemctl restart casaos-gateway 2>/dev/null || true
        CASA_PORT_MOVED=1
        sleep 3
    fi
fi

# --- STEP 3: Pemeriksaan Port Host Secara Aman (Non-Destructive) ---
port_in_use() {
    local p="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -tlnH "sport = :$p" 2>/dev/null | grep -q .
    elif command -v lsof >/dev/null 2>&1; then
        lsof -Pi ":$p" -sTCP:LISTEN -t >/dev/null 2>&1
    else
        return 1
    fi
}

is_own_dashboard_port() {
    docker ps --filter "name=^/eka_dashboard$" --format '{{.Ports}}' 2>/dev/null | grep -q ":${DASHBOARD_PORT}->"
}

if port_in_use "$DASHBOARD_PORT" && ! is_own_dashboard_port; then
    echo -e "${YELLOW}[WARNING] Port ${DASHBOARD_PORT} sedang digunakan oleh layanan lain di host!${NC}"
    echo -e "${YELLOW}[INFO] Installer tidak akan mematikan web server host (Nginx/Apache/dll.) secara sepihak.${NC}"
    if [ -t 0 ]; then
        read -r -p "Masukkan port alternatif untuk Eka Dashboard (misal 8080, kosong untuk batal): " ALT_PORT
        if [ -n "$ALT_PORT" ] && [[ "$ALT_PORT" =~ ^[0-9]+$ ]]; then
            DASHBOARD_PORT="$ALT_PORT"
            echo -e "${GREEN}[OK] Menggunakan port alternatif: ${DASHBOARD_PORT}${NC}"
        else
            echo -e "${RED}[ABORT] Instalasi dibatalkan. Jalankan ulang dengan: sudo bash install.sh --port 8080${NC}"
            exit 1
        fi
    else
        echo -e "${RED}[ERROR] Jalankan ulang dengan port bebas: sudo bash install.sh --port 8080${NC}"
        exit 1
    fi
fi

# --- STEP 4: Deteksi & Instalasi Docker + Docker Compose (Lintas Distro) ---
if ! command -v docker >/dev/null 2>&1; then
    echo -e "${YELLOW}[INFO] Docker belum terpasang. Memasang Docker...${NC}"
    if [ "$PKG_MGR" = "pacman" ]; then
        install_pkg pacman docker docker-compose
        systemctl enable --now docker 2>/dev/null || true
    elif [ "$PKG_MGR" = "apk" ]; then
        install_pkg apk docker docker-cli-compose
        rc-update add docker default 2>/dev/null || true
        service docker start 2>/dev/null || true
    else
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker 2>/dev/null || true
    fi
fi

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${YELLOW}[INFO] Memasang plugin Docker Compose via ${PKG_MGR}...${NC}"
    case "$PKG_MGR" in
        apt-get|dnf|yum) install_pkg "$PKG_MGR" docker-compose-plugin || install_pkg "$PKG_MGR" docker-compose ;;
        pacman)          install_pkg pacman docker-compose ;;
        zypper)          install_pkg zypper docker-compose ;;
        apk)             install_pkg apk docker-cli-compose ;;
        *)
            echo -e "${RED}[ERROR] Docker Compose tidak ditemukan dan package manager tidak dikenali.${NC}"
            exit 1
            ;;
    esac
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_CMD="docker-compose"
    else
        echo -e "${RED}[ERROR] Gagal memasang Docker Compose.${NC}"
        exit 1
    fi
fi

# --- STEP 5: Konfigurasi Port Dinamis & Deploy Container ---
mkdir -p ./data

if [ "$DASHBOARD_PORT" != "80" ]; then
    cat > docker-compose.override.yml <<EOF
services:
  dashboard:
    ports: !override
      - "${DASHBOARD_PORT}:5000"
EOF
    echo -e "${BLUE}[INFO] Port override ditulis ke docker-compose.override.yml (${DASHBOARD_PORT}:5000).${NC}"
else
    rm -f docker-compose.override.yml 2>/dev/null || true
fi

if [ "$RESET_ADMIN" -eq 1 ] && [ -f "./data/security_config.json" ]; then
    echo -e "${YELLOW}[INFO] Flag --reset-admin aktif: menghapus security_config.json untuk Setup Wizard ulang...${NC}"
    rm -f ./data/security_config.json
fi

echo -e "${BLUE}[INFO] Membangun dan menjalankan Eka Dashboard...${NC}"
$COMPOSE_CMD down 2>/dev/null || true
$COMPOSE_CMD up --build -d

IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}' || ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -n1 || echo "127.0.0.1")
echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}   EKA DASHBOARD BERHASIL DIPASANG & BERJALAN    ${NC}"
echo -e "${GREEN}=================================================${NC}"
if [ "$DASHBOARD_PORT" = "80" ]; then
    echo -e "URL Akses: ${BLUE}http://${IP_ADDR}/${NC}"
else
    echo -e "URL Akses: ${BLUE}http://${IP_ADDR}:${DASHBOARD_PORT}/${NC}"
fi
if [ "$CASA_PORT_MOVED" -eq 1 ]; then
    echo -e "${YELLOW}CasaOS dipindahkan ke: http://${IP_ADDR}:9999${NC}"
fi
