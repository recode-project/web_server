<div align="center">

# Eka Dashboard
### Universal Self-Hosted Linux Server & Bare-Metal Control Center

![Version](https://img.shields.io/badge/version-1.4.0-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Multi--Distro-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-78_App_Store-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![LXD](https://img.shields.io/badge/LXD%20%2F%20Incus-Containers-FF6B6B?style=for-the-badge&logo=canonical&logoColor=white)
![Tests](https://img.shields.io/badge/Unit_Tests-140%2F140_Passing-10B981?style=for-the-badge)
![License](https://img.shields.io/badge/Copyright-Eka%20Harefa-orange?style=for-the-badge)

<p align="center">
  <b>Eka Dashboard</b> adalah pusat kendali server Linux serbaguna berbasis web untuk homelab, mini PC, SBC/ARM, VPS cloud, maupun server bare-metal produksi. Dirancang 100% portabel dan agnostik distro (Debian/Ubuntu, Fedora/RHEL, Arch, Alpine, openSUSE), menyatukan telemetri perangkat keras &amp; daya listrik RAPL, App Store 78 aplikasi Docker, orkestrasi LXD/Incus, firewall multi-backend, manajemen paket OS, DNS AdBlocker, backup offsite, hingga Web Terminal PTY dalam satu antarmuka Glassmorphism yang ringan.
</p>

---

[Ringkasan](#-sekilas-pandang) • [Fitur Utama](#-fitur-utama) • [Dukungan Distro](#-dukungan-lingkungan--multi-distro) • [Arsitektur & Port](#-arsitektur--port-mapping) • [Instalasi](#-panduan-instalasi-cepat) • [Panduan DNS](#-panduan-dns-adblocker) • [Troubleshooting](#-troubleshooting) • [Hak Cipta](#-hak-cipta--kepemilikan)

---

</div>

## 📌 Sekilas Pandang

**Eka Dashboard** dibangun untuk menggantikan banyak panel terpisah dengan satu control plane ringan berbasis **Python Flask + Socket.IO + Vanilla Modular JS (Zero Inline JS)**. Seluruh deteksi sistem dilakukan secara dinamis saat runtime (tanpa hardcode IP, user, maupun perangkat), mendukung mode **Docker (`nsenter`)** maupun **Native Linux/VPS**, serta menyediakan kontrol visibilitas **Optional Modules Opt-In** agar fitur yang belum terpasang tetap rapi tanpa error.

| Aspek | Kemampuan Utama |
| :--- | :--- |
| **Portabilitas OS** | Multi-distro (`apt`, `dnf`, `yum`, `pacman`, `apk`, `zypper`) & multi-arsitektur (`x86_64`, `ARM64`) |
| **Mode Deployment** | Kontainer Docker terisolasi (`nsenter` ke kernel host) atau instalasi Native Linux / VPS |
| **App Store** | 78 aplikasi self-hosted terkurasi lintas 12 kategori + Smart 3-Tier Container Matcher untuk Docker Compose |
| **Telemetri & Daya** | CPU/RAM/Disk/Network real-time, Public NOC Wallboard, Hardware RAPL & Battery/UPS Power Engine + kalibrasi tarif global |
| **Arsitektur Frontend** | Modern Cybernetic Glassmorphism (`DESIGN_SYSTEM.md`), 100% separasi berkas `static/*.js`, responsif desktop & mobile |
| **Keandalan** | Dilengkapi 140 unit test otomatis (`unittest`), audit log, RBAC (`owner`/`admin`/`operator`/`readonly`) |

---

## 🎨 Design System & Arsitektur Tema

Seluruh modul dan tampilan antarmuka Eka Dashboard dibakukan di bawah panduan desain terpusat pada berkas [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

Prinsip inti sistem desain ini meliputi:
* **Signature Dynamic Wallpaper:** Animasi 4-stop gradient (`#ee7752`, `#e73c7e`, `#23a6d5`, `#23d5ab`) 15 detik berakselerasi GPU (`position: fixed; z-index: 0; pointer-events: none`).
* **Frosted Glass Surfaces:** Kartu, panel navigasi, dan modal memakai token kaca transparan seragam (`--glass-bg: rgba(30, 30, 40, 0.6)`, `backdrop-filter: blur(20px)`, `--glass-border`) dengan auto-scroll aktif penuh.
* **Separasi Kode 100% (Zero Inline JS):** Seluruh logika frontend diisolasi ke berkas eksternal modular `static/*.js` tanpa inline JavaScript pada HTML.

---

## ✨ Fitur Utama

### 1. 📊 Live Telemetry, NOC Wallboard & Hardware Energy Engine (`/dashboard`, `/`, `/metrics`)
* **Telemetri Perangkat Keras:** Monitoring beban CPU multi-core, temperatur, penggunaan RAM, kapasitas disk, bandwidth jaringan live, serta **Public NOC Wallboard (`/`)** 6-kartu untuk pemantauan status armada server.
* **Hardware Power & Energy Engine:** Membaca daya aktual dari register fisik **Intel/AMD RAPL** (`/sys/class/powercap`) dan sensor **Battery/UPS** (`/sys/class/power_supply`) dengan fallback lintas arsitektur.
* **Interactive Energy Detail & Kalibrasi Global:** Klik kartu **Energy** membuka proyeksi kWh & biaya (per jam, harian, mingguan, bulanan, tahunan), rincian parameter sensor, preset 9 mata uang global + tarif/kWh kustom di `/settings`, serta reset counter kWh.

### 2. 🛒 Self-Hosted App Store & Smart Container Matcher (`/store`)
* **78 Aplikasi Terkurasi (12 Kategori):** AI & LLM (`Ollama`, `Open WebUI`, `n8n`, `Flowise`, `Qdrant`, `LibreChat`), Database (`PostgreSQL`, `MariaDB`, `Redis`, `MongoDB`, `pgAdmin`, `MinIO`, `CouchDB`), Media (`Jellyfin`, `Plex`, `Immich`, `Navidrome`, `PhotoPrism`), Files (`Nextcloud`, `OnlyOffice`, `Obsidian Web`, `Syncthing`, `Stirling PDF`), Network (`AdGuard Home`, `Nginx Proxy Manager`, `Tailscale`, `WireGuard Easy`, `Cloudflared`, `RustDesk Server`), Monitoring (`Grafana`, `Prometheus`, `Uptime Kuma`, `Dozzle`, `Beszel`), Developer (`Portainer`, `Dockge`, `Gitea`, `Code-Server`, `PocketBase`), Home Automation, Privacy, Dashboards, Downloader, dan Automation.
* **Smart 3-Tier Container Matcher:** Mendeteksi otomatis kontainer yang dipasang lewat App Store maupun Docker Compose / nama kustom (mis. `n8n-container`, `pgadmin4-web`, `immich_server`) sambil mengecualikan kontainer sidecar (`runner`, `worker`, `exporter`).
* **Lifecycle Manager & Live Logs:** Instalasi 1-klik dengan Docker Named Volumes + timezone dinamis (`{{AUTO_TZ}}`), dukungan **Custom Docker App**, serta **Manage Modal** (Start, Stop, Restart, Open UI, live 150-baris Container Logs, dan Uninstall berproteksi kontainer eksternal).

### 3. 📦 LXD / Incus Orchestrator & Docker Panel (`/lxd`, `/panel_docker`)
* **Manajemen Kontainer LXD & Incus:** Dukungan multi-project (`--all-projects`), deteksi biner otomatis (`lxc`/`incus` termasuk `/snap/bin`), status IP LAN & Tailscale, kuota RAM/CPU/storage, port forwarding, 1-click Tailscale/WireGuard, serta Web Terminal root terisolasi.
* **Docker Container Panel:** Inspeksi kontainer, port, volume, environment variables, dan kontrol siklus hidup kontainer Docker host.

### 4. 🛡️ AdBlocker DNS Suite & Web Reverse Proxy Shield (`/adblocker`, `/websites`)
* **AdGuard Home DNS Suite:** Master toggle proteksi, SafeBrowsing, SafeSearch, Parental Control, grafik query 24 jam, analitik 3 kolom (Top Blocked, Top Queried, Top Clients + alias perangkat), Live Query Log, dan Custom Filter Editor.
* **Web Server & Security Shield:** Deteksi multi-web-server (`nginx`, `apache2`, `httpd`, `caddy`), manajemen vhost, uji sintaks & reload service host, monitor masa berlaku SSL otomatis multi-domain, arsip backup web ZIP, serta deteksi serangan scanner/exploit/SSH brute-force dengan tombol Ban IP `iptables`.

### 5. 🔥 Firewall Multi-Backend, Services, Logs & Package Manager (`/firewall`, `/services`, `/logs`, `/packages`)
* **Central Firewall Manager:** Auto-deteksi lintas distro (`ufw` -> `firewalld` -> `nftables` -> `iptables`), manajemen aturan bernomor, preset cepat SSH rate-limit, kebijakan default traffic, dan inspeksi raw ruleset.
* **Services & System Daemons:** Kontrol penuh systemd (`start`, `stop`, `restart`, `enable`, `disable`, `mask`), inspeksi PID/memori cgroup, dan viewer log `journalctl`.
* **System Logs & SSH Audit:** Explorer `journalctl` multi-filter, audit log autentikasi SSH lintas distro (`/var/log/auth.log`, `/var/log/secure`, `/var/log/messages`, `journalctl`), dan ring buffer kernel (`dmesg`) deteksi OOM/disk error.
* **Package & OS Update Manager:** Mendukung 6 package manager (`apt`, `dnf`, `yum`, `pacman`, `apk`, `zypper`), klasifikasi security vs regular updates, deteksi kernel & reboot required, serta dry-run simulator.

### 6. 💾 Drive Health S.M.A.R.T., Backup Offsite, Alerting & Task Scheduler (`/smart`, `/backup`, `/alerts`, `/scheduler`)
* **Drive Health & S.M.A.R.T. Inspector:** Telemetri NVMe & SATA (suhu, wear level, TBW, bad sectors, Power-On Hours), runner Short/Long Self-Test, dan monitor Software RAID (`mdadm`) & ZFS Pool.
* **Disaster Recovery & Offsite Backup:** Snapshot multi-komponen (`manifest.json`), inspektur arsip interaktif, sinkronisasi cloud **Rclone**, dan penjadwalan otomatis.
* **Alerting Engine:** Notifikasi ambang batas (CPU, RAM, Storage, S.M.A.R.T., Reboot) via Telegram Bot, WhatsApp Gateway, maupun Generic Webhook (Discord/Slack).
* **Task Scheduler:** Visual manager Crontab & Systemd Timers lengkap dengan konsol dry-run tester.

### 7. 💻 Web Terminal PTY, File Manager, VPN Mesh & SMB Sharing (`/terminal`, `/files`, `/vpn`, `/sharing`)
* **Web Terminal PTY:** Konsol interaktif non-login (`bash -i`) bebas banner host, multi-tab, auto-resize sinkron `TIOCSWINSZ`, dan quick commands lintas distro.
* **File Explorer & SMB Sharing:** Navigasi disk fisik host (`lsblk`) + manajemen Samba share dengan tautan UNC/SMB akurat (IP LAN & Tailscale) dan monitor sesi aktif (`smbstatus`).
* **VPN Mesh & Network Manager:** Integrasi Tailscale Mesh (+ P2P Ping), WireGuard Hub (generator QR & `.conf`), ZeroTier, port scanner (`ss`), diagnostik Ping/DNS, serta routing table.
* **Optional Modules Opt-In (`/settings`):** Modul opsional dapat diaktifkan/disembunyikan secara fleksibel termasuk mode `Auto-Hide Uninstalled`.

---

## 🌍 Dukungan Lingkungan & Multi-Distro

| Komponen | Backend yang Didukung Otomatis |
| :--- | :--- |
| **Package Manager** | `apt` (Debian/Ubuntu), `dnf` / `yum` (Fedora/RHEL/Rocky/Alma), `pacman` (Arch/Garuda/Manjaro), `apk` (Alpine), `zypper` (openSUSE) |
| **Firewall** | `ufw`, `firewalld`, `nftables`, `iptables` |
| **Web Server** | `nginx`, `apache2`, `httpd`, `caddy` |
| **Container Engine** | Docker Engine + LXD / Incus |
| **Mode Eksekusi Host** | Docker Container (`nsenter` ke PID 1 host) atau Native Linux / VPS tanpa Docker |

---

## 🏗️ Arsitektur & Port Mapping

Eka Dashboard dapat dijalankan dalam kontainer Docker mandiri yang terhubung aman ke daemon host, maupun langsung sebagai service Native Linux:

| Layanan / Protokol | Port Host | Port Kontainer | Deskripsi |
| :--- | :--- | :--- | :--- |
| **Eka Dashboard Web UI** | `80` (dapat dikustomisasi) | `5000` (TCP) | Antarmuka panel web utama (dapat dialihkan via `--port` atau reverse proxy) |
| **AdGuard DNS Server** *(opsional)* | `53` (TCP/UDP) | `53` (TCP/UDP) | Resolver DNS lokal untuk perangkat jaringan |
| **AdGuard Home Web UI** *(opsional)* | `8053` (HTTP) | `80` (TCP) | Antarmuka web konsol native AdGuard Home |
| **LXD / Incus Socket** *(opsional)* | Local Unix Socket | `/var/snap/lxd/common/lxd/unix.socket` | Manajemen kontainer virtualisasi |
| **Docker Socket** *(opsional)* | Local Unix Socket | `/var/run/docker.sock` | Manajemen kontainer & App Store 78 aplikasi |

---

## 🚀 Panduan Instalasi Cepat

### Prasyarat Sistem
* Sistem Operasi: Linux (`Ubuntu`, `Debian`, `Fedora`, `Rocky/Alma/RHEL`, `Arch/Garuda`, `openSUSE`, atau `Alpine`).
* Docker Engine (v20.10+) & Docker Compose Plugin (v2.0+) untuk mode kontainer, **atau** Python 3.9+ untuk mode Native Linux.

### Cara 1: Installer Universal Interaktif (`install.sh` — Disarankan)
Skrip `install.sh` bersifat lintas distro dan non-destruktif (mendukung `--port`, `--dir`, `--reset-admin`, `--shift-casaos`):
```bash
git clone https://github.com/recode-project/web_server.git eka_dashboard
cd eka_dashboard
chmod +x install.sh
sudo ./install.sh --port 80
```

### Cara 2: Docker Compose Langsung
```bash
# 1. Kloning repositori resmi
git clone https://github.com/recode-project/web_server.git eka_dashboard
cd eka_dashboard

# 2. Bangun dan jalankan kontainer
docker compose up --build -d

# 3. Periksa status kontainer
docker compose ps
```

Setelah berjalan, buka browser dan akses dashboard melalui:
```text
http://<IP_SERVER_ANDA>/
```
Pada kunjungan pertama, halaman **Setup Admin** akan memandu pembuatan akun administrator pertama secara otomatis.

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
    - Interaktivitas Widget Energy (`/dashboard`, `static/script.js?v=13`): menghubungkan klik kartu Energy (`#energy-widget-card`) ke overlay detail `openDetail('power')` berisi telemetri daya real-time (auto-refresh 3 detik), tabel proyeksi kWh & biaya (per jam, harian, mingguan, bulanan, tahunan), rincian parameter sensor/kalibrasi, tombol pintas ke `/settings#energy-calibration-section`, tombol reset counter kWh (`POST /api/energy/reset`), dan tutup via `Escape`.
    - Penghapusan penuh modul **Recode AI** (`SYSTEM_APPS`, `OPTIONAL_MODULES_CATALOG`, `PERMISSIONS`, route `/recode`, `/api/recode/*`, Socket.IO `recode_*`, `templates/recode.html`, dan `tests/test_recode_agent.py` — **140/140 Unit Tests PASS**).

---

## ⚖️ Hak Cipta & Kepemilikan

© **2026 Eka Harefa**. Seluruh hak cipta dilindungi undang-undang.

Seluruh kode sumber (*source code*), struktur arsitektur, aset desain antarmuka, dan algoritma logika sistem di dalam repositori ini adalah karya cipta dan milik eksklusif dari **Eka Harefa** (`recode-project`).

**KETENTUAN PENGGUNAAN:**
* Dilarang keras menyalin, menduplikasi, mempublikasikan ulang (*re-upload*), atau memperjualbelikan kode proyek ini tanpa izin tertulis resmi dari pemilik hak cipta.
* Modifikasi untuk kebutuhan personal diizinkan selama tidak menghilangkan atribusi hak cipta resmi **Eka Harefa**.
* Segala bentuk pelanggaran hak kekayaan intelektual akan ditindaklanjuti sesuai dengan hukum perlindungan hak cipta yang berlaku.
