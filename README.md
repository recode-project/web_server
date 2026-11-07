<div align="center">

# 🛡️ Eka Dashboard
### All-in-One Autonomous Linux Server & Infrastructure Management Suite

![Version](https://img.shields.io/badge/version-1.4.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![LXD](https://img.shields.io/badge/LXD-Containers-FF6B6B?style=for-the-badge&logo=canonical&logoColor=white)
![AdGuard](https://img.shields.io/badge/AdGuard%20Home-DNS%20Suite-00B06F?style=for-the-badge&logo=adguard&logoColor=white)
![License](https://img.shields.io/badge/Copyright-Eka%20Harefa-orange?style=for-the-badge)

<p align="center">
  <b>Eka Dashboard</b> adalah platform kontrol server modern, ringan, dan elegan berbasis web untuk memantau performa perangkat keras, mengatur kontainer virtualisasi (LXD & Docker), melindungi jaringan lokal melalui server DNS mandiri (AdGuard Home), serta menangkal serangan siber pada website secara real-time.
</p>

---

[Fitur Utama](#-fitur-utama) • [Arsitektur & Port](#-arsitektur--port-mapping) • [Panduan Instalasi](#-panduan-instalasi-cepat) • [Konfigurasi DNS](#-panduan-dns-adblocker) • [Troubleshooting](#-troubleshooting) • [Hak Kepemilikan](#-hak-cipta--kepemilikan)

---

</div>

## 📌 Sekilas Pandang

Dibangun dengan arsitektur **Glassmorphism UI** dengan wallpaper dinamis animasi gradient, Eka Dashboard dirancang untuk berjalan di server rumahan (*homelab*), server VPS cloud, hingga server bare-metal produksi tanpa membebani resource CPU dan memori. Seluruh antarmuka bersifat responsif dan dapat dioperasikan penuh melalui browser desktop maupun layar smartphone.

---

## ✨ Fitur Utama

### 1. 📊 Telemetri Sistem Real-Time (Live Telemetry)
* **Hardware Gauges:** Monitoring beban CPU multi-core, temperatur prosesor, penggunaan RAM, partisi penyimpanan (NVMe/SSD/HDD), serta statistik pemakaian energi (kWh / estimasi rupiah).
* **Network Monitor:** Grafik tren *bandwidth* real-time (download & upload per detik) serta total akumulasi transfer data sejak boot server.
* **Informasi Host:** Tampilan nama host, kernel Linux, arsitektur CPU, dan waktu aktif (*uptime*) yang diperbarui otomatis.

### 2. 🛡️ AdBlocker DNS Protection Suite (AdGuard Home Integration)
* **Master Protection Toggle:** Saklar proteksi global DNS AdGuard Home aktif/nonaktif dalam hitungan milidetik.
* **Quick Security Switches:** Kontrol instan untuk modul *SafeBrowsing* (blokir malware/phishing), *SafeSearch* (pencarian bersih di mesin telusur), dan *Parental Control* (pemblokiran konten dewasa).
* **Aktivitas Query 24 Jam:** Grafik time-series interaktif (HTML5 Canvas retina-ready) membandingkan total permintaan DNS vs query yang berhasil diblokir filter.
* **Analitik 3 Kolom Sejajar:**
  * **Top Blocked Domains:** 10 domain ancaman/pelacak yang paling banyak dicegat.
  * **Top Queried Domains:** 10 domain yang paling sering diminta oleh perangkat klien.
  * **Klien Teratas:** Daftar IP klien aktif lengkap dengan pengenalan jenis perangkat cerdas (ponsel, laptop, server, router), visual rasio persentase, serta tombol modal untuk mengganti nama/alias perangkat secara langsung.
* **Live Query Log:** Riwayat permintaan DNS real-time dengan status *Blocked* atau *Processed*.
* **Custom Filter Editor:** Editor aturan filter khusus (format Adblock Plus, AdGuard, dan file hosts standar) langsung dari browser.

### 3. 📦 LXD Container Orchestrator & Virtualization
* **Manajemen Kontainer:** Daftar seluruh kontainer LXD, inspeksi status (*Running / Stopped*), IP address (LAN & Tailscale), serta kontrol *Start, Stop, Restart*, dan *Delete*.
* **Web Terminal xterm.js:** Akses konsol shell root interaktif langsung ke dalam kontainer melalui browser tanpa perlu konfigurasi SSH manual.
* **Resource Quota Limits:** Konfigurasi batas RAM (contoh: `2GB`), CPU core limits (contoh: `2`), dan kuota penyimpanan per kontainer langsung dari antarmuka modal.
* **Port Forwarding Manager:** Pemetaan port host ke port internal kontainer dengan integrasi firewall otomatis.
* **1-Click Network Mesh:** Skrip instalasi otomatis Tailscale dan WireGuard untuk kontainer LXD.

### 4. 🔒 Website Threat Mitigation (Web Shield)
* **Log Traffic Inspector:** Pemeriksaan lalu lintas web server Nginx secara periodik untuk mendeteksi anomali akses.
* **Brute-Force & Vulnerability Scanning Detection:** Identifikasi otomatis bot jahat yang mencoba memindai celah keamanan (`wp-login.php`, `.env`, path traversal, SQL injection).
* **Firewall Quick-Ban:** Kemampuan memblokir alamat IP penyerang secara instan menggunakan aturan iptables / nftables.

### 5. 💻 Web-Based Terminal & File Explorer
* **Full Login Shell:** Terminal berbasis web dengan dukungan penuh ANSI escape codes, resize canvas dinamis, font monospace adaptif, dan eksekusi perintah aman.
* **Storage Inspector:** Ringkasan visual ruang penyimpanan per partisi sistem.

---

## 🏗️ Arsitektur & Port Mapping

Eka Dashboard dikemas dalam arsitektur container Docker mandiri yang terisolasi namun terhubung langsung ke daemon host:

| Layanan / Protokol | Port Host | Port Kontainer | Deskripsi |
| :--- | :--- | :--- | :--- |
| **Eka Dashboard Web UI** | `80` (HTTP) | `5000` (TCP) | Antarmuka panel web utama (dapat dialihkan via reverse-proxy) |
| **AdGuard DNS Server** | `53` (TCP/UDP) | `53` (TCP/UDP) | Resolver DNS lokal untuk seluruh perangkat jaringan |
| **AdGuard Home Web UI** | `8053` (HTTP) | `80` (TCP) | Antarmuka web konsol native AdGuard Home |
| **LXD REST Socket** | Local Unix Socket | `/var/snap/lxd/common/lxd/unix.socket` | Manajemen kontainer virtualisasi |
| **Docker Socket** | Local Unix Socket | `/var/run/docker.sock` | Manajemen kontainer pendukung |

---

## 🚀 Panduan Instalasi Cepat

### Prasyarat Sistem
* Sistem Operasi: Linux (Ubuntu 20.04+, Debian 11+, Arch Linux, atau CentOS Stream).
* Docker Engine (v20.10+) & Docker Compose Plugin (v2.0+).
* Port `80` dan Port `53` belum terikat oleh layanan lain.

### Langkah Pemasangan:
```bash
# 1. Kloning repositori resmi
git clone https://github.com/recode-project/web_server.git eka_dashboard
cd eka_dashboard

# 2. Jalankan dan bangun kontainer via Docker Compose
docker compose up --build -d

# 3. Periksa status kontainer
docker compose ps
```

Setelah kontainer berjalan, buka browser dan akses antarmuka dashboard pada:
```text
http://<IP_SERVER_ANDA>/
```

---

## 📡 Panduan DNS AdBlocker

Untuk mengaktifkan proteksi iklan dan pelacak di seluruh perangkat rumah atau kantor:

1. Buka halaman pengaturan router Wi-Fi Anda (biasanya `192.168.1.1` atau `192.168.0.1`).
2. Masuk ke menu **DHCP Server / DNS Settings**.
3. Masukkan IP server Anda pada kolom **Primary DNS Server** (contoh: `192.168.1.4` tanpa menambahkan nomor port).
4. Simpan konfigurasi router dan lakukan *reconnect* Wi-Fi pada perangkat Anda.
5. Pantau statistik query yang masuk melalui menu **AdBlocker DNS** di Eka Dashboard.

---

## 🔧 Troubleshooting

### 1. Port 53 Bentrok dengan `systemd-resolved`
Pada instalasi Ubuntu/Debian default, layanan `systemd-resolved` biasanya mengikat port 53 lokal (`127.0.0.53:53`). Untuk membebaskan port 53 bagi AdGuard Home:
```bash
# Matikan DNSStubListener pada systemd-resolved
sudo sed -i 's/#DNSStubListener=yes/DNSStubListener=no/' /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved

# Pastikan port 53 kini telah bebas
sudo ss -tulpn | grep :53
```

### 2. Memperbarui Dashboard ke Versi Terbaru
Untuk memperbarui instalasi yang sudah ada tanpa kehilangan data konfigurasi:
```bash
cd eka_dashboard
git pull origin main
docker compose build
docker compose up -d
```

---

## ⚖️ Hak Cipta & Kepemilikan

© **2026 Eka Harefa**. Seluruh hak cipta dilindungi undang-undang.

Seluruh kode sumber (*source code*), struktur arsitektur, aset desain antarmuka, dan algoritma logika sistem di dalam repositori ini adalah karya cipta dan milik eksklusif dari **Eka Harefa** (`recode-project`).

**KETENTUAN PENGGUNAAN:**
* Dilarang keras menyalin, menduplikasi, mempublikasikan ulang (*re-upload*), atau memperjualbelikan kode proyek ini tanpa izin tertulis resmi dari pemilik hak cipta.
* Modifikasi untuk kebutuhan personal diizinkan selama tidak menghilangkan atribusi hak cipta resmi **Eka Harefa**.
* Segala bentuk pelanggaran hak kekayaan intelektual akan ditindaklanjuti sesuai dengan hukum perlindungan hak cipta yang berlaku.
