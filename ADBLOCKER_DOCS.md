# Dokumentasi Modul AdBlocker DNS Suite (Eka Dashboard)

## 1. Tujuan Modul
Modul AdBlocker DNS mengintegrasikan AdGuard Home secara native ke dalam Eka Dashboard. Modul ini memungkinkan administrator jaringan memonitor metrik query DNS, mengatur proteksi ancaman/iklan, melihat domain dan klien teraktif, menamai perangkat di jaringan, serta mengelola aturan filter kustom tanpa harus membuka dashboard terpisah.

---

## 2. Fitur & Komponen Antarmuka
1. **Master DNS Protection Bar:**
   - Toggle switch untuk mengaktifkan/menonaktifkan proteksi DNS AdGuard Home secara real-time.
   - Indikator status `PROTECTED` atau `DISABLED`.
2. **Quick Security Toggles:**
   - SafeBrowsing (pemblokiran domain malware & phishing).
   - SafeSearch (pemaksaan pencarian aman di Google, Bing, YouTube).
   - Parental Control (pemblokiran situs dewasa/pornografi).
3. **KPI Metrics Cards:**
   - Total DNS Queries (24 Jam).
   - Blocked Ads & Threats.
   - Blocked Ratio (%) dengan visual progress bar.
   - Average Processing Latency (ms).
4. **Grafik Aktivitas Query DNS 24 Jam:**
   - Time-series chart interaktif berbasis HTML5 Canvas (dual-line: Total vs Blocked) tanpa dependency library pihak ketiga.
5. **Rekomendasi IP DNS Server (Router / Perangkat):**
   - Menampilkan IP LAN murni (contoh: `<IP_LAN_SERVER>`) dan IP Tailscale/VPN (`<IP_VPN_SERVER>`) dengan label port 53 terpisah.
   - Tombol satu klik untuk menyalin alamat IP murni ke clipboard agar kompatibel dengan input DNS router.
6. **Grid Analitik 3 Kolom:**
   - **Top Blocked Domains:** Daftar 10 domain paling sering diblokir beserta total blokir.
   - **Top Queried Domains:** Daftar 10 domain paling sering diminta beserta total query.
   - **Klien Teratas (Top Active Clients):**
     - Ikon perangkat pintar otomatis (mobile, laptop/PC, server, router, smart TV).
     - Nama/alias perangkat tebal dengan tombol pensil untuk ganti nama secara instan.
     - Alamat IP klien dan badge `Kustom` jika sudah dinamai.
     - Total query, persentase rasio terhadap seluruh query DNS, dan horizontal progress bar dinamis (hijau, kuning, biru).
7. **Modal Beri Nama Perangkat (Client Rename):**
   - Mengubah nama klien langsung via API AdGuard Home (`/control/clients/add` atau `/control/clients/update`).
8. **Live DNS Query Log:**
   - Log query real-time dengan status (Blocked/Processed), domain, IP klien, dan waktu pemrosesan.
9. **Custom Filtering Rules Editor:**
   - Textarea pengeditan aturan filter kustom sintaks Adblock Plus / AdGuard / Hosts format.
10. **Pengaturan Koneksi & 1-Click Docker Installer:**
    - Modal konfigurasi host, port, username, password, dan TLS.
    - Modal otomatisasi instalasi kontainer Docker AdGuard Home jika daemon belum terpasang di server.

---

## 3. Rute & Endpoint API Backend
- `GET /adblocker`: Render template halaman `templates/adblocker.html`.
- `GET /api/adblocker/status`: Mengembalikan status proteksi, metrik 24h, IP LAN/Tailscale, dan daftar klien terformat (`top_clients_formatted`).
- `POST /api/adblocker/toggle`: Toggle proteksi DNS ON/OFF (`{"enabled": bool}`).
- `POST /api/adblocker/feature/<feature_name>`: Toggle fitur `safebrowsing`, `safesearch`, atau `parental`.
- `POST /api/adblocker/client/rename`: Memberi nama/alias perangkat klien (`{"ip": "...", "name": "..."}`).
- `GET /api/adblocker/rules`: Mengambil daftar user rules kustom.
- `POST /api/adblocker/rules`: Menyimpan daftar user rules kustom.
- `GET /api/adblocker/querylog?limit=X`: Mengambil entri log query DNS terbaru.
- `GET /api/adblocker/config`: Mengambil konfigurasi host/port koneksi AdGuard.
- `POST /api/adblocker/config`: Memperbarui dan menguji kredensial koneksi AdGuard.
- `POST /api/adblocker/install`: Menjalankan kontainer Docker AdGuard Home secara otomatis.

---

## 4. Konfigurasi Port & Koneksi Standar
- **Port Eka Dashboard:** `80` (Internal Docker: `5000`)
- **Port AdGuard Home Host:** `8053` (Web UI Console) & `53` (DNS TCP/UDP)
- **Akun Login Dashboard:** Dibuat mandiri melalui Setup Wizard pada instalasi pertama (`data/security_config.json`)
- **Kredensial AdGuard Home:**
  - Host: `host.docker.internal` (atau `127.0.0.1` / IP LAN server)
  - Port Web UI: `8053`
  - Username & Password: Diatur oleh pengguna pada modal Pengaturan Koneksi (`data/adguard_config.json`)

---

## 5. Catatan Kemajuan Terakhir (Changelog)
- **Layout 3 Kolom Responsif:** Mengubah `.analytics-grid` menjadi 3 kolom sejajar di layar desktop (`minmax(320px, 1fr)`), menyatukan Top Blocked, Top Queried, dan Klien Teratas tanpa ruang kosong.
- **Nama Perangkat & Tombol Rename:** Menambahkan resolusi nama perangkat (rDNS/gateway/server/klien kustom) dan modal edit nama perangkat langsung ke AdGuard API.
- **Visual Progress Bar & Ikon:** Menampilkan ikon perangkat dan progress bar persentase dinamis pada setiap baris klien teratas persis antarmuka native AdGuard Home.
- **Perbaikan Navigasi & Web Console:** Tombol "Dashboard" mengarah ke `/dashboard`, dan tombol "Web Console" mengarah langsung ke port `8053`.
- **IP Chip Murni:** Menghilangkan `:53` dari teks dan fungsi clipboard IP DNS agar tidak merusak format saat disalin ke konfigurasi router.
- **Pemisahan File:** Seluruh logika JavaScript ditulis terpisah pada `static/adblocker.js` tanpa inline script di `templates/adblocker.html`.

