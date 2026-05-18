#!/bin/bash

# Warna untuk output cantik
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}   EKA DASHBOARD - INSTALLER OTOMATIS            ${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""

# Cek apakah dijalankan sebagai root (Sudo)
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}[ERROR] Mohon jalankan script ini dengan sudo!${NC}"
  echo "Usage: sudo bash install.sh"
  exit 1
fi

# --- CONFIGURATION ---
INSTALL_DIR="/root/eka_dashboard"
CURRENT_DIR=$(pwd)

# --- STEP 0: Cek Mode Update ---
# Jika kita tidak berada di INSTALL_DIR, asumsikan ini adalah folder update hasil ekstraksi ZIP
if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
    echo -e "${BLUE}[INFO] Mendeteksi Mode Update/Instalasi Baru...${NC}"
    echo -e "Sumber: $CURRENT_DIR"
    echo -e "Tujuan: $INSTALL_DIR"
    
    # Konfirmasi (Auto-yes jika ada flag -y, tapi sementara manual dulu atau langsung gas)
    echo -e "${YELLOW}Akan mengupdate file sistem di $INSTALL_DIR...${NC}"
    
    # 1. Buat folder tujuan jika belum ada
    if [ ! -d "$INSTALL_DIR" ]; then
        echo -e "Membuat folder instalasi baru..."
        mkdir -p "$INSTALL_DIR"
    fi
    
    # 2. Copy file (kecuali data/ config user)
    echo -e "Menyalin file update..."
    # Copy semua file dari current dir ke install dir
    # Kita pakai rsync atau cp -r. Hati-hati jangan overwrite data jika ada di source (tapi source dari zip update biasanya bersih dari data)
    
    # Exclude data folder dari copy agar tidak menimpa data user (meskipun di zip kosong)
    # Gunakan cp -rf untuk overwrite code
    cp -rf "$CURRENT_DIR/"* "$INSTALL_DIR/" 2>/dev/null
    
    # 3. Pindah ke folder instalasi
    echo -e "Pindah ke $INSTALL_DIR untuk melanjutkan instalasi..."
    cd "$INSTALL_DIR"
    
    # Pastikan executables
    chmod +x install.sh
fi

CASA_PORT_MOVED=0

# --- STEP 1: Deteksi CasaOS & Geser Port ---
if [ -f "/etc/casaos/gateway.ini" ]; then
    echo -e "${YELLOW}[INFO] CasaOS Terdeteksi! Memeriksa konfigurasi port...${NC}"
    
    # Ambil port saat ini
    CURRENT_PORT=$(grep -oP 'port\s*=\s*\K\d+' /etc/casaos/gateway.ini)
    
    if [ "$CURRENT_PORT" == "80" ]; then
        echo -e "${YELLOW}[ACTION] CasaOS menggunakan Port 80. Menggeser ke Port 9999...${NC}"
        
        # Backup config
        cp /etc/casaos/gateway.ini /etc/casaos/gateway.ini.bak
        
        # Ganti Port 80 jadi 9999 pakai sed
        sed -i 's/port = 80/port = 9999/g' /etc/casaos/gateway.ini
        # Kadang formatnya "port=80" tanpa spasi, handle juga
        sed -i 's/port=80/port=9999/g' /etc/casaos/gateway.ini
        
        echo -e "${GREEN}[OK] Config CasaOS diperbarui.${NC}"
        
        # Restart CasaOS Gateway
        echo -e "${YELLOW}[ACTION] Merestart service CasaOS...${NC}"
        systemctl restart casaos-gateway
        
        CASA_PORT_MOVED=1
        sleep 5
    else
        echo -e "${GREEN}[OK] CasaOS aman (Sudah berjalan di Port $CURRENT_PORT).${NC}"
    fi
else
    echo -e "${BLUE}[INFO] CasaOS tidak terdeteksi. Melanjutkan instalasi normal.${NC}"
fi

# --- STEP 2: Cek & Bersihkan Port 80 ---
echo -e "${YELLOW}[INFO] Memastikan Port 80 tersedia...${NC}"

# Loop checking (Max 5 attempts)
for i in {1..5}; do
    if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null ; then
        PID=$(lsof -Pi :80 -sTCP:LISTEN -t)
        PROCESS_NAME=$(ps -p $PID -o comm=)
        
        # Skip check if it's our own docker-proxy (re-run scenario)
        if [ "$PROCESS_NAME" == "docker-proxy" ]; then
             echo -e "${BLUE}[INFO] Port 80 sedang digunakan oleh Docker (Mungkin instalasi sebelumnya). Akan direstart.${NC}"
             break
        fi

        echo -e "${RED}[WARNING] Port 80 masih digunakan oleh: $PROCESS_NAME ($PID) (Percobaan $i/5)${NC}"
        
        if [ "$PROCESS_NAME" == "casaos-gateway" ]; then
             echo -e "${YELLOW}[ACTION] Memaksa restart CasaOS lagi...${NC}"
             systemctl restart casaos-gateway
        elif [ "$PROCESS_NAME" == "apache2" ] || [ "$PROCESS_NAME" == "nginx" ] || [ "$PROCESS_NAME" == "httpd" ]; then
             echo -e "${YELLOW}[ACTION] Menghentikan web server bawaan ($PROCESS_NAME)...${NC}"
             systemctl stop $PROCESS_NAME
             systemctl disable $PROCESS_NAME
        else
             echo -e "${RED}[ACTION] Mematikan paksa proses $PID...${NC}"
             kill -9 $PID
        fi
        
        sleep 3
    else
        echo -e "${GREEN}[OK] Port 80 Kosong & Siap digunakan.${NC}"
        break
    fi
done

# Final Check
if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null ; then
    PID=$(lsof -Pi :80 -sTCP:LISTEN -t)
    PROCESS_NAME=$(ps -p $PID -o comm=)
    if [ "$PROCESS_NAME" != "docker-proxy" ]; then
        echo -e "${RED}[CRITICAL ERROR] Port 80 MASIH digunakan oleh $PROCESS_NAME. Instalasi tidak bisa lanjut.${NC}"
        echo "Mohon matikan proses tersebut manual: kill -9 $PID"
        exit 1
    fi
fi

# --- STEP 3: Persiapan Docker & Deployment ---
echo -e "${BLUE}[INFO] Memeriksa instalasi Docker...${NC}"

# Cek Docker, Install otomatis jika belum ada
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}[WARNING] Docker belum terinstall. Memulai instalasi otomatis Docker...${NC}"
    curl -fsSL https://get.docker.com | sh
    if [ $? -ne 0 ]; then
        echo -e "${RED}[CRITICAL ERROR] Gagal menginstall Docker secara otomatis. Silakan cek koneksi internet atau install manual.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Docker berhasil diinstall.${NC}"
else
    echo -e "${GREEN}[OK] Docker sudah terinstall.${NC}"
fi

# Determine Docker Compose command, Install jika belum ada
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${YELLOW}[WARNING] Docker Compose tidak ditemukan. Menginstall Docker Compose Plugin...${NC}"
    apt-get update && apt-get install -y docker-compose-plugin
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        echo -e "${GREEN}[OK] Docker Compose berhasil diinstall.${NC}"
    else
        echo -e "${RED}[ERROR] Gagal menginstall Docker Compose otomatis. Mohon install manual.${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}[INFO] Membangun dan Menjalankan Dashboard...${NC}"

# Hapus paksa container lama jika ada konflik nama yang tidak terdeteksi docker-compose down
docker rm -f eka_dashboard 2>/dev/null || true

$COMPOSE_CMD down 2>/dev/null

# Hapus security_config.json lama (dimiliki root) agar setup wizard muncul pada fresh install
# File lain di data/ (catalog, dll) dibiarkan agar tidak perlu download ulang
if [ -f "./data/security_config.json" ]; then
    echo -e "${YELLOW}[INFO] Menghapus konfigurasi lama agar Setup Wizard aktif...${NC}"
    rm -f ./data/security_config.json 2>/dev/null || true
fi

$COMPOSE_CMD up --build -d

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=================================================${NC}"
    echo -e "${GREEN}      INSTALASI SUKSES!             ${NC}"
    echo -e "${GREEN}=================================================${NC}"
    echo ""
    
    # Ambil IP (Coba ambil IP non-lokal pertama)
    IP_ADDR=$(hostname -I | awk '{print $1}')
    
    echo -e "Silakan akses Dashboard Admin di:"
    echo -e "${BLUE}   http://$IP_ADDR  (Port 80) ${NC}"
    echo ""
    
    if [ "$CASA_PORT_MOVED" -eq 1 ]; then
        echo -e "${YELLOW}PERHATIAN PENTING:${NC}"
        echo -e "Web Interface CasaOS telah dipindahkan ke:"
        echo -e "${YELLOW}   http://$IP_ADDR:9999 ${NC}"
        echo -e "(Bookmark link ini agar tidak lupa!)"
    fi
    
    echo ""
    echo -e "Terima kasih telah menggunakan produk ini."
else
    echo -e "${RED}[ERROR] Gagal menjalankan Docker Container.${NC}"
    exit 1
fi
