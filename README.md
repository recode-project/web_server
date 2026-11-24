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

[Fitur Utama](#-fitur-utama) • [Arsitektur & Port](#-arsitektur--port-mapping) • [Design System](#-design-system--arsitektur-tema) • [Panduan Instalasi](#-panduan-instalasi-cepat) • [Konfigurasi DNS](#-panduan-dns-adblocker) • [Troubleshooting](#-troubleshooting) • [Hak Kepemilikan](#-hak-cipta--kepemilikan)

---

</div>

## 📌 Sekilas Pandang

Dibangun dengan arsitektur **Glassmorphism UI** dengan wallpaper dinamis animasi gradient, Eka Dashboard dirancang untuk berjalan di server rumahan (*homelab*), server VPS cloud, hingga server bare-metal produksi tanpa membebani resource CPU dan memori. Seluruh antarmuka bersifat responsif dan dapat dioperasikan penuh melalui browser desktop maupun layar smartphone.

---

## 🎨 Design System & Arsitektur Tema

Seluruh modul dan tampilan antarmuka Eka Dashboard dibakukan di bawah panduan desain terpusat pada berkas `DESIGN_SYSTEM.md`.

Prinsip inti sistem desain ini meliputi:
* **Signature Dynamic Wallpaper:** Animasi 4-stop gradient (`#ee7752`, `#e73c7e`, `#23a6d5`, `#23d5ab`) 15 detik dengan akselerasi GPU, posisi `fixed`, elevasi `z-index: 0`, dan `pointer-events: none`.
* **Universal Stacking Context & Auto-Scroll:** Aturan kanvas transparan (`body { background: transparent !important; }`), scrolling aktif penuh (`overflow-y: auto !important; height: auto !important; min-height: 100vh !important;`), dan buffer bawah 100px pada `.main-content`.
* **Unified Glassmorphism Component Library:** Tombol standar `.btn`, `.btn-secondary`, `.btn-primary` dengan efek frosted glass (`backdrop-filter: blur(12px)`), kartu metrik telemetri 4-kolom, tab navigasi interaktif, badge status, dan konsol terminal monospace.
* **Separasi Kode 100%:** Bebas inline JavaScript — seluruh logika frontend dimuat secara modular melalui `static/*.js`.

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

### 4. 🌐 Web & Reverse Proxy Shield (Unifikasi Websites & Web Shield)
* **Nginx Virtual Hosts Manager:** Pemindaian dinamis seluruh vhosts aktif dari `/etc/nginx/sites-enabled` (dengan resolusi symlink transparan di Docker), inspeksi server name, listen port, document root, dan target reverse proxy.
* **Kontrol Service Nginx Host:** Uji validasi sintaks otomatis (`nginx -t`), reload, dan restart service Nginx secara aman via `nsenter` pada kernel host.
* **Trafik & Analisis Real-Time:** Statistik 24 jam dengan grafik batang fleksibel per jam, pemantauan pengunjung unik, rata-rata durasi sesi, rasio status HTTP, dan Top 5 URL yang sering diakses dari `access.log`.
* **Shield & Keamanan Bot:** Deteksi otomatis signature scanner (Nikto, SQLmap, Nmap, Gobuster), exploit path (`.env`, `wp-login`, traversal), percobaan login SSH gagal (`auth.log`), dan pemblokiran instan IP penyerang ke aturan `iptables DROP` host.
* **Pemantau SSL Dinamis & Cadangan Web:** Pemeriksaan masa berlaku sertifikat SSL seluruh domain vhost secara multi-domain otomatis (tanpa hardcode domain), serta fitur 1-klik unduh arsip ZIP direktori web.
* **Separasi Kode Penuh:** 100% logika frontend dimuat secara modular melalui `static/websites.js` tanpa inline JavaScript.

### 5. 💻 Web-Based Terminal & File Explorer
* **Full Login Shell:** Terminal berbasis web dengan dukungan penuh ANSI escape codes, resize canvas dinamis, font monospace adaptif, dan eksekusi perintah aman.
* **Storage Inspector:** Ringkasan visual ruang penyimpanan per partisi sistem.

### 6. ⚙️ Services & System Daemons Manager (`/services`)
* **Kontrol Siklus Hidup Systemd:** Start, Stop, Restart, Enable, Disable, Mask, dan Unmask service host secara instan melalui wrapper `systemctl` berbasis `nsenter` pada kernel host.
* **Telemetri & Status Host:** Ringkasan visual total unit service, service running, service failed (crash-loop), dan status integritas sistem host (*running, degraded, maintenance*).
* **Shortcut Cepat Service Krusial:** Tombol filter instan 1-klik untuk daemons inti (Docker, Nginx, Tailscale, Samba, SSH, Cron).
* **Inspeksi Properti & cgroup:** Modal inspeksi detail menampilkan Main PID, konsumsi memori cgroup riil (`MemoryCurrent`), durasi CPU (`CPUUsageNSec`), Exit Code terakhir, dan active enter timestamp.
* **Journald Log Explorer:** Pembacaan 40 baris log `journalctl -u <unit>` real-time per service dengan tombol salin log.
* **Separasi Logika Frontend:** 100% kode JavaScript dimuat secara modular melalui `static/services.js` tanpa inline JavaScript.

### 7. 📜 System Logs & Journald Explorer (`/logs`)
* **Journald Explorer Terpadu:** Pemfilteran multi-parameter log `journalctl` host: per unit service, level prioritas error (`emerg` s.d. `debug`), rentang waktu fleksibel (15m s.d. 7d), limit baris, dan pencarian teks regex secara real-time.
* **Audit Keamanan SSH & Autentikasi:** Deteksi upaya serangan brute-force login SSH, pemantauan riwayat login sukses (`publickey` / `password`), eksekusi perintah `sudo` lokal, serta daftar Top Attacker IPs lengkap dengan tombol 1-klik "Ban IP" via iptables host.
* **Kernel Ring Buffer (`dmesg`):** Inspeksi kernel events host dengan indikator otomatis untuk mendeteksi insiden OOM-Killer (Out of Memory) dan error hardware / disk storage I/O.
* **Live Telemetry & Auto-Refresh:** 4 kartu ringkasan (Error Logs 24h, SSH Failed 24h, OOM Events, Kernel Alerts) serta mode auto-refresh stream 5 detik.
* **Separasi Logika Frontend:** 100% kode JavaScript dimuat secara modular melalui `static/system_logs.js` tanpa inline JavaScript.

### 8. 🛡️ Central Firewall Manager (`/firewall`)
* **Kontrol Host Firewall UFW Terpadu:** Saklar Master Protection (Active / Inactive), reload konfigurasi real-time, dan pemantauan status logging kernel.
* **Manajemen Aturan Bernomor (Numbered Rules):** Daftar interaktif seluruh aturan UFW (IPv4 & IPv6), filter kategori (Allow, Deny, Reject, Limit), pencarian instan, dan penghapusan aturan bernomor 1-klik (`ufw --force delete <num>`).
* **Modal Tambah Aturan Granular:** Pembuatan aturan port, rentang port (`8080:8090`), protokol (TCP, UDP, Any), filter subnet IP sumber (CIDR), serta pengikatan interface jaringan spesifik (`tailscale0`, `lxdbr0`, `eth0`).
* **Preset Cepat & Rate-Limiting:** Proteksi otomatis SSH anti brute-force (`ufw limit 22/tcp`), pembukaan port web server (80 & 443), serta isolasi subnet jaringan mesh Tailscale.
* **Kebijakan Default Traffic:** Konfigurasi arah lalu lintas Incoming (DENY/REJECT/ALLOW), Outgoing (ALLOW/DENY), dan Routed forward (ALLOW/DENY).
* **Inspeksi Raw Kernel Filter:** Pembacaan tabel filter `iptables -L -n -v` dan ruleset `nftables` native untuk verifikasi tingkat lanjut.
* **Separasi Logika Frontend:** 100% kode JavaScript dimuat secara modular melalui `static/firewall.js` tanpa inline JavaScript.

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
3. Masukkan IP server Anda pada kolom **Primary DNS Server** (contoh: `192.168.1.10` tanpa menambahkan nomor port).
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

## 📝 Catatan Kemajuan & Pembaruan Terakhir (Multi-Agent Sync)

*Catatan ini disediakan agar agen AI pada sesi berikutnya dapat langsung melanjutkan tanpa perlu menelaah ulang codebase:*

1. **Perombakan Total Modul Jaringan / Network Manager (`/network`):**
   - Mengubah tampilan kaku menjadi UI Glassmorphism modern terbagi dalam 4 Tab Navigasi:
     - **Tab 1: Antarmuka (Interfaces):** Menampilkan kartu tiap antarmuka fisik, bridge, virtual, dan VPN lengkap dengan status akurat (memperbaiki bug virtual TUN `tailscale0` yang sebelumnya dilaporkan 'DOWN' karena `operstate: UNKNOWN` pada Linux TUN/TAP; kini dievaluasi secara akurat via kernel flags `UP`/`LOWER_UP` dan assigned IP menjadi 'UP'), traffic counter Rx/Tx bytes, serta tombol toggle filter untuk menyembunyikan ephemeral container veth/tap.
     - **Tab 2: Port & Layanan Terbuka:** Pemindai real-time seluruh port listening host via `ss -tulpn`, memetakan bind address (Public vs Local), PID, nama program, serta filter pencarian instan.
     - **Tab 3: Diagnostik Terpadu (Ping & DNS):** Fitur uji latensi ICMP Ping dan resolusi DNS domain langsung dari antarmuka web tanpa perlu SSH manual.
     - **Tab 4: Konfigurasi & Tabel Routing:** Manajemen Hostname, DNS server, dan visualisasi tabel perutean host (*Routing Table*).
   - Seluruh logika JavaScript diekstrak ke `static/network.js` mematuhi aturan isolasi berkas website.
2. **Perombakan Total VPN Manager & Integrasi Tailscale Mesh (`/vpn`):**
   - Mengintegrasikan **Tailscale Mesh Network** sebagai Tab Utama (Tab 1 default):
     - Memantau status node lokal dan seluruh peer devices yang terhubung secara dinamis.
     - Menampilkan indikator koneksi P2P Direct vs Relay (DERP), OS icon, IP Tailscale, dan Tx/Rx transfer counter.
     - Fitur **Tailscale Ping Tool** terintegrasi: menguji latensi direct P2P rute paket antar node langsung dari web UI.
   - **WireGuard Hub (Tab 2):** Manajemen klien WireGuard host, pembuatan QR code konfigurasi mobile, dan unduhan file konfigurasi `.conf`.
   - **ZeroTier & Multi-Tunnel Scanner (Tab 3):** Dukungan join/leave network ZeroTier serta pemindai menyeluruh seluruh daemon tunnel aktif pada host.
   - Seluruh kode JavaScript diekstrak ke `static/vpn.js`.
3. **Sinkronisasi Tema & Ekstraksi Modular Modul Metrics (`/metrics`):**
   - Mengganti styling legacy yang terisolasi dengan sistem desain resmi Eka Dashboard (`Inter` font, `<div class="wallpaper"></div>` ambient gradient, glassmorphism `backdrop-filter: blur(20px)`).
   - Menyelaraskan palet warna grafik Chart.js ke palet resmi dashboard (`--cpu-color: #ff6b6b`, `--ram-color: #4ecdc4`, `--disk-color: #ffe66d`, `--net-color: #23a6d5`).
   - Mematuhi aturan pemisahan logika JavaScript ke berkas modular terpisah: `static/metrics.js`.
4. **Restrukturisasi File Manager Berbasis Disk Fisik (`/files`):**
   - Menghilangkan mount point mentah membingungkan dan partisi sistem `/boot/efi`.
   - Mengelompokkan penyimpanan ke disk fisik riil host melalui `lsblk -J` secara dinamis (NVMe, SSD, HDD).
   - Mengklik drive fisik membuka daftar volume partisi terkait.
5. **Dukungan LXD Multi-Project & Terminal PTY (`/lxd`, `/terminal`):**
   - Menambahkan filter dan parameter `--project` pada backend API LXD (`/api/lxd/containers?project=...`).
   - Memperbaiki urutan argumen canonical eksekusi terminal: `lxc --project <project> exec <target> -- bash --login -i`.
   - Tombol terminal pada card container membuka PTY di tab peramban baru yang terisolasi.
6. **Optimasi Latensi Dashboard & App Store (`/api/stats`, `/api/store/apps`):**
   - Mengganti query berulang per-aplikasi dengan `_get_host_active_snapshot()` dan cache 8 detik, memangkas latensi dari >2 detik menjadi ~0.2 detik.
7. **Perombakan Total Modul File Sharing / SMB (`/sharing`):**
   - Memperbaiki deteksi IP server host (LAN IP primer dan Tailscale IP), menggantikan IP internal bridge kontainer Docker sehingga tautan akses Windows UNC (`\\<IP>\<share>`) dan URL SMB (`smb://<IP>/<share>`) valid dan dapat langsung diakses dari klien LAN/remote.
   - Menggunakan wrapper `nsenter` untuk mengontrol daemon Samba host (`systemctl reload/restart/start/stop smbd`) dan memetakan path direktori host riil.
   - Menambahkan pemantau sesi aktif (*Active SMB Client Sessions*) real-time melalui `smbstatus -b` (`GET /api/smb/sessions`).
   - Menyediakan tombol satu-klik salin (*one-click copy*) untuk path Windows Explorer dan Finder macOS.
   - Mematuhi aturan pemisahan logika JavaScript ke berkas modular terpisah: `static/sharing.js` dan antarmuka Glassmorphism terpadu.
8. **Pembangunan Modul Services & System Daemons (`/services`):**
   - Menambahkan menu baru "Services" pada Grid APPS Eka Dashboard (ikon gears, gradient cyan/blue).
   - Membangun backend handler universal di `app.py` (`/services`, `/api/services/summary`, `/api/services/list`, `/api/services/detail/<unit>`, `/api/services/control`).
   - Menyediakan tampilan Glassmorphism responsif di `templates/services.html` dengan ambient gradient wallpaper resmi.
   - Mengisolasi 100% logika interaksi, live filter, shortcut chips, modal inspeksi, dan toast ke `static/services.js`.
9. **Pembangunan Modul System Logs & Journald Explorer (`/logs`):**
   - Menambahkan menu baru "System Logs" pada Grid APPS Eka Dashboard (ikon file-waveform, gradient pink/red).
   - Membangun backend handler universal di `app.py` (`/logs`, `/api/logs/summary`, `/api/logs/journal`, `/api/logs/auth`, `/api/logs/dmesg`, `/api/logs/units`) berbasis `nsenter` pada kernel host.
   - Menyediakan tampilan Glassmorphism responsif 3 Tab di `templates/system_logs.html`: Journald Explorer, SSH & Auth Security Audit, dan Kernel Buffer (dmesg).
   - Mengisolasi 100% logika frontend interaktif ke `static/system_logs.js`.
10. **Pembangunan Modul Central Firewall Manager (`/firewall`):**
    - Menambahkan menu baru "Firewall" pada Grid APPS Eka Dashboard (ikon shield, gradient fire red/orange).
    - Membangun backend handler universal di `app.py` (`/firewall`, `/api/firewall/status`, `/api/firewall/rule/add`, `/api/firewall/rule/delete`, `/api/firewall/default`, `/api/firewall/toggle`, `/api/firewall/reload`, `/api/firewall/iptables`) berbasis `nsenter` pada kernel host.
    - Menyediakan antarmuka Glassmorphism responsif 4 Tab di `templates/firewall.html`: Rules Manager, Quick Presets & Rate-Limit, Default Policies, dan Raw Iptables / Nftables.
    - Mengisolasi 100% logika frontend interaktif ke `static/firewall.js`.
11. **Pembangunan Modul Task Scheduler & Cron Jobs (`/scheduler`):**
    - Menambahkan menu baru "Task Scheduler" pada Grid APPS Eka Dashboard (ikon clock-rotate-left, gradient emerald green).
    - Membangun backend handler universal di `app.py` (`/scheduler`, `/api/cron/summary`, `/api/cron/list`, `/api/cron/save`, `/api/cron/toggle`, `/api/cron/delete`, `/api/cron/timers`, `/api/cron/test_run`) berbasis `nsenter` pada kernel host.
    - Menyediakan antarmuka Glassmorphism responsif 3 Tab di `templates/scheduler.html`: Crontab Jobs Visual Manager, Systemd Timers Inspector, dan Script Dry-Run & Tester Console.
    - Mengisolasi 100% logika frontend interaktif ke `static/scheduler.js`.
12. **Pembangunan Modul Drive Health & S.M.A.R.T. Inspector (`/smart`):**
    - Menambahkan menu baru "Drive Health" pada Grid APPS Eka Dashboard (ikon heart-pulse, gradient red/coral).
    - Membangun backend handler universal di `app.py` (`/smart`, `/api/smart/summary`, `/api/smart/detail/<disk_name>`, `/api/smart/test/start`, `/api/smart/test/abort`, `/api/smart/raid`) berbasis `smartctl`, `lsblk`, `/proc/mdstat`, dan `zpool` via `nsenter` pada kernel host.
    - Telemetri mendalam NVMe & SATA: Wear Level percentage, Total Bytes Written (TBW), Reallocated Sectors, Current Pending Sectors, suhu real-time, Power-On Hours, dan tabel atribut lengkap ATA.
    - Runner S.M.A.R.T. Self-Test interaktif (Short / Long test) dengan tombol Abort dan console log live.
    - Inspector Software RAID (`mdadm`) & ZFS Pool terintegrasi.
    - Menyediakan antarmuka Glassmorphism responsif 3 Tab di `templates/drive_health.html`: Physical Drives, Self-Test Runner, dan RAID / Storage Arrays.
    - Mengisolasi 100% logika frontend interaktif ke `static/drive_health.js`.
13. **Pembangunan Modul Package & OS Update Manager (`/packages`):**
    - Menambahkan menu baru "Package Manager" pada Grid APPS Eka Dashboard (ikon box-open, gradient cyan/blue).
    - Membangun backend handler universal di `app.py` (`/packages`, `/api/packages/summary`, `/api/packages/list`, `/api/packages/refresh`, `/api/packages/upgrade`) berbasis `apt list --upgradable`, `apt-get`, `dpkg`, dan `/var/run/reboot-required` via `nsenter` pada kernel host.
    - Klasifikasi otomatis Security Updates vs Regular Updates dengan penandaan visual badge khusus.
    - Deteksi status reboot host dan identifikasi berkas paket pemicu reboot di `/var/run/reboot-required.pkgs`.
    - Telemetri Kernel Linux: pendeteksian kernel aktif (`uname -r`), histori image terpasang di `/boot`, dan ketersediaan versi kernel baru.
    - Simulator Upgrade Dry-Run (`apt-get upgrade -s`) dan runner upgrade individual maupun massal dengan log streaming real-time pada console terminal.
    - Menyediakan antarmuka Glassmorphism responsif 3 Tab di `templates/packages.html`: Paket Upgradable, Kernel & Reboot Status, dan Terminal Eksekusi APT.
    - Mengisolasi 100% logika frontend interaktif ke `static/packages.js`.
14. **Pembangunan Modul Alerting & Notification Engine (`/alerts`):**
    - Menambahkan menu baru "Alert Engine" pada Grid APPS Eka Dashboard (ikon bell, gradient pink/yellow).
    - Membangun backend handler universal di `app.py` (`/alerts`, `/api/alerts/config`, `/api/alerts/test`, `/api/alerts/history`, `/api/alerts/system_check`, `/api/alerts/wa_status`) dengan arsitektur multi-channel modular.
    - Pemilih saluran universal (*Universal Channel Selector*): Telegram Bot, WhatsApp API Bridge, Pengiriman Ganda (Telegram & WA), serta Generic Webhook (Discord / Slack).
    - Mesin pemantau ambang batas otomatis (*Incident Alert Rules*): CPU Usage (>90%), RAM Usage (>85%), Storage Usage (>90%), degradasi S.M.A.R.T. disk, dan permintaan reboot kernel.
    - Menyediakan antarmuka Glassmorphism responsif 3 Tab di `templates/alerts.html`: Saluran & Konfigurasi, Aturan Ambang Batas, dan Log Riwayat Pengiriman.
    - Mengisolasi 100% logika frontend interaktif ke `static/alerts.js`.
15. **Perombakan Total Disaster Recovery & Offsite Backup Engine (`/backup`) & Integrasi Widget Sejajar:**
    - Menambahkan **Backup & Recovery Widget Card** pada baris utama telemetri dashboard (`.widgets-area`), diletakkan sejajar berdampingan dengan kartu CPU, RAM, Storage, Network, Energy, dan Web Shield.
    - Membangun backend disaster recovery universal di `app.py`: snapshot multi-komponen (`manifest.json`), inspektur arsip interaktif (`GET /api/backup/inspect/<id>`), integrasi Rclone cloud offsite, serta penjadwalan otomatis cron.
    - Antarmuka Glassmorphism 4 Tab di `templates/backup.html` dan kontroler modular di `static/backup.js` tanpa inline JavaScript.
16. **Modernisasi Public Wallboard NOC (`/`) & Hardware RAPL Power Engine:**
    - Merombak tampilan monitoring publik menjadi NOC Wallboard berarsitektur Glassmorphism dengan ambient wallpaper, 6 kartu telemetri infrastruktur (`.fleet-grid` via `/api/monitoring/telemetry`), serta pemisahan penuh ke `static/monitoring.css` dan `static/monitoring.js`.
    - Mengganti kalkulator daya legacy dengan `HardwarePowerReader` yang memindai register fisik Intel/AMD RAPL (`/sys/class/powercap`) secara dinamis dengan fallback universal lintas arsitektur (x86/ARM).
17. **Sanitasi Universal & Anti-Hardcode (Portabilitas Publik Penuh):**
    - Seluruh deteksi user host, default gateway, service template (`syncthing@*`, `wg-quick@*`), direktori penyimpanan mobile backup, entrypoint kontainer, placeholder UI, dan suite unit test dibuat 100% dinamis tanpa menyematkan data spesifik server pribadi.
18. **Universalisasi Arsitektural 5 Tahap (Multi-Distro, Native/Docker, Kalibrasi Energi & Modularisasi Opt-In — 163/163 Unit Tests PASS):**
    - **Tahap 1 (Eksekutor Host & Terminal Bersih):** Menghapus wrapper pribadi `kiro-cli` dari `Dockerfile`, mengubah Web Terminal ke interactive non-login shell (`bash -i`) agar bebas banner `/etc/profile.d/*` host, serta menyatukan seluruh eksekutor perintah host melalui `_run_host_cmd` yang otomatis beradaptasi antara Docker `nsenter` dan Native Linux/VPS.
    - **Tahap 2 (Agnostik Distro Linux):** Modul `/packages` & installer Rclone mendukung 6 package manager (`apt`, `dnf`, `yum`, `pacman`, `apk`, `zypper`) beserta deteksi distro/reboot/kernel lintas OS; `install.sh` ditulis ulang menjadi lintas distro dan non-destruktif (`--port`, `--dir`, `--reset-admin`, `--shift-casaos`).
    - **Tahap 3 (Agnostik Firewall, Log SSH & Web Server):** `/firewall` mendukung auto-deteksi multi-backend (`ufw` -> `firewalld` -> `nftables` -> `iptables`); log SSH (`/logs` & `/api/web_monitor/security`) mendukung `/var/log/auth.log`, `/var/log/secure`, `/var/log/messages`, dan fallback `journalctl`; `/websites` mendeteksi `nginx`/`apache2`/`httpd`/`caddy`, memindai `sites-enabled`/`conf.d`/`http.d`, dan menangani status `not_installed` secara anggun.
    - **Tahap 4 (Kalibrasi Energi, Mata Uang & Sensor Daya Universal):** Menambahkan konfigurasi `energy` pada `app_settings.json` (9 preset mata uang global + Custom, tarif/kWh, locale, desimal, base Watt overhead, efisiensi PSU, idle fallback, prioritas sensor) beserta endpoint `POST /api/energy/reset`; memperluas `HardwarePowerReader` dengan sensor `/sys/class/power_supply/*` (Battery/UPS dengan filter periferal `scope=Device`); mengekstrak 100% inline JS `templates/settings.html` ke `static/settings.js`; Dashboard & Wallboard merender biaya dan sumber daya 100% dinamis tanpa hardcode `Rp`/`1444.70`.
    - **Tahap 5 (Modularisasi Opt-In & Graceful Empty State):** Menambahkan registry 10 modul opsional (`GET /api/modules/status`), toggle tampil/sembunyi modul & opsi `auto_hide_uninstalled` di Settings dan `/api/dashboard/apps`, dukungan LXD & Incus (`/snap/bin` aware) dengan graceful empty state di `static/lxd.js` (0 inline JS), pemindahan sisa inline script `templates/index.html` ke `static/script.js`, serta unifikasi `_run_host_cmd` pada SMB/Tailscale/WireGuard/ZeroTier/WA Gateway yang selalu mengembalikan HTTP 200 `installed: False` tanpa error 500 saat tidak terpasang.
19. **Perombakan Total App Store Universal (78 Aplikasi, Smart Container Matcher, Named Volumes, Modal Manage & Zero Inline JS — 170/170 Unit Tests PASS):**
    - Memperluas katalog `data/app_catalog.json` dari 30 menjadi **78 aplikasi self-hosted terkurasi** lintas 12 kategori (`AI & LLM`, `Database`, `Media`, `Files`, `Network`, `Monitoring`, `Developer`, `Home Automation`, `Privacy`, `Dashboards`, `Downloader`, `Automation` — termasuk `n8n`, `Immich`, `PocketBase`, `OnlyOffice Docs`, `Obsidian Web`, `RustDesk Server`, dan `CouchDB`) dengan 0 konflik port default, 0 path `/host/root/...`, dan injeksi timezone dinamis `{{AUTO_TZ}}` dari Settings.
    - Menambahkan **Smart Universal 3-Tier Container Matcher** (`_match_store_container_record`, `_normalize_image_repo`, `_extract_container_record`) di `app.py` agar kontainer Docker Compose / custom name / custom patched image (mis. `n8n-container`, `pgadmin4-web`, `asios-qdrant`, `cloudflared-obsidian`, `immich_server`) terdeteksi akurat di `/api/store/installed`, `/api/store/manage`, dan `/api/store/logs/<app_id>` sambil mengecualikan kontainer sidecar/helper (`runner`, `worker`, `exporter`, `hbbr`).
    - Memperbaiki bug volume mount `install_worker` (mendukung Docker Named Volumes & normalisasi aman host path), memperbaiki merge environment variables, menambahkan dukungan `cap_add`/`devices`/`command`, dan menghapus duplikasi route `POST /api/store/manage` serta dead code `install_app()`.
    - Deduplikasi port IPv4/IPv6, resolusi akurat Web UI port (`open_port` — AdGuard Home `8053`, n8n `5678`, pgAdmin `5050`, Database non-UI `None`), fallback ikon lokal `static/icon.svg`, serta ekstraksi 100% JS `templates/store.html` ke `static/store.js` lengkap dengan modal **Manage App** (Start/Stop/Restart/Live Logs/Uninstall + konfirmasi khusus kontainer eksternal/Compose).
20. **Audit Kebersihan Repositori, Penghapusan Berkas Mati & Perbaikan `.gitignore` (170/170 Unit Tests PASS):**
    - Menghapus seluruh berkas legacy/mati yang tidak terpakai (`app_server.py`, `templates/activation.html`, `templates/web_monitor.html`, `templates/manage_apps.html`, `templates/Web_eka_freehosting.code-workspace`, `static/style.css.bak`, `trigger_debug.py`, `trigger_install.py`, `convert_md_to_pdf.py`, `setup_wg.sh`, `package-lock.json`, crash log JVM, arsip ZIP lama, artefak sistem lisensi lama, serta workflow `.github/workflows/build-check.yml` yang mencurigakan).
    - Memperbaiki `.gitignore` agar menggunakan `data/*` + `!data/app_catalog.json` sehingga katalog 78 aplikasi ikut terdistribusi di repositori publik sementara seluruh konfigurasi runtime, database, dan kredensial di `data/` tetap terabaikan.
    - Penyempurnaan UI anti-slop & penyelarasan penuh tema Dashboard `/store`: menghapus kapsul status melayang `.status-badge` + dot `fa-circle` (judul aplikasi tampil penuh), mengganti seluruh pil `999px` menjadi tab kategori tegas & teks metrik polos, menerapkan formula `.wallpaper` fixed (`100vw x 100vh`, `z-index: 0`, `brightness(0.6)`) serta token kaca transparan Dashboard (`--glass-bg: rgba(30, 30, 40, 0.6)`, `blur(20px)`, `--glass-border`, `--radius-lg`), dan menambahkan penutup modal via tombol `Escape` dan klik backdrop.
    - Interaktivitas Widget Energy (`/dashboard`, `static/script.js?v=13`): menghubungkan klik kartu Energy (`#energy-widget-card`) ke overlay detail `openDetail('power')` berisi telemetri daya real-time (auto-refresh 3 detik), tabel proyeksi kWh & biaya (per jam, harian, mingguan, bulanan, tahunan), rincian parameter sensor/kalibrasi, tombol pintas ke `/settings#energy-calibration-section`, tombol reset counter kWh (`POST /api/energy/reset`), dan tutup via `Escape` (**171/171 Unit Tests PASS**).

---

## ⚖️ Hak Cipta & Kepemilikan

© **2026 Eka Harefa**. Seluruh hak cipta dilindungi undang-undang.

Seluruh kode sumber (*source code*), struktur arsitektur, aset desain antarmuka, dan algoritma logika sistem di dalam repositori ini adalah karya cipta dan milik eksklusif dari **Eka Harefa** (`recode-project`).

**KETENTUAN PENGGUNAAN:**
* Dilarang keras menyalin, menduplikasi, mempublikasikan ulang (*re-upload*), atau memperjualbelikan kode proyek ini tanpa izin tertulis resmi dari pemilik hak cipta.
* Modifikasi untuk kebutuhan personal diizinkan selama tidak menghilangkan atribusi hak cipta resmi **Eka Harefa**.
* Segala bentuk pelanggaran hak kekayaan intelektual akan ditindaklanjuti sesuai dengan hukum perlindungan hak cipta yang berlaku.
