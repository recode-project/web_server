# Eka Dashboard

⚠️ **PERHATIAN (DISCLAIMER):**
**Proyek ini masih dalam tahap pengembangan aktif (Under Development / Beta).**
Beberapa fitur mungkin masih dalam pengerjaan, terdapat *bug*, atau belum sepenuhnya stabil. Kami menyertakan peringatan ini agar pengguna tidak merasa kecewa jika menemukan ketidaksempurnaan selama menggunakan dashboard ini. Pembaruan akan terus dilakukan untuk menyempurnakan performa dan fungsionalitasnya.

---

## Deskripsi
Eka Dashboard adalah sistem panel web terpadu untuk memanajemen layanan server, analitik website, keamanan, dan pengaturan jaringan (seperti Nginx, Docker, dan **LXD Container**) dengan antarmuka yang dinamis, modern, dan informatif.

### ✨ Pembaruan Terbaru (Update)
*   **LXD Manager & Resource Limits**: Kelola container LXD kamu langsung dari Dashboard. Mulai dari buat container, Start, Stop, Delete, akses Terminal web-based, hingga konfigurasi limit RAM, CPU, dan Storage per-container!
*   **Website Threat Detection**: Pantau IP yang mencoba memindai celah keamanan (brute-force/scanning) dari log Nginx, dan lakukan pemblokiran IP (Firewall) langsung dari UI Website Shield.

## 🚀 Cara Instalasi & Pembaruan
Aplikasi ini dijalankan menggunakan **Docker Compose** dan dikonfigurasi untuk berjalan di **Port 80**. Pastikan port 80 di server kamu kosong.

**Bagi Pengguna Baru (Install Baru):**
```bash
git clone https://github.com/USERNAME/eka_dashboard.git
cd eka_dashboard
docker compose up --build -d
```

**Bagi Pengguna Lama (Cara Update):**
Untuk mendapatkan fitur terbaru seperti *LXD Manager*, kamu **wajib** melakukan pull dan build ulang agar container memperbarui API backend-nya.
```bash
cd eka_dashboard
git pull origin main
docker compose down
docker compose up --build -d
```

---

## Hak Kepemilikan (Copyright & Ownership)
© 2026 **Eka Harefa**. Hak cipta dilindungi undang-undang.

Seluruh baris kode (source code), desain antarmuka, aset, dan logika sistem di dalam repositori ini adalah milik eksklusif dari **Eka Harefa**. 

**DILARANG KERAS:**
1. Menyalin, menduplikasi, atau mencuri kode dari proyek ini (Code Theft).
2. Memodifikasi dan mendistribusikan ulang (re-distribute) atas nama pihak lain.
3. Menggunakan proyek ini untuk kepentingan komersial pribadi tanpa izin resmi dan tertulis dari pihak Eka Harefa.

Tindakan penyalahgunaan, pembajakan, atau penggunaan tanpa izin akan ditindak secara tegas sesuai dengan hukum perlindungan Hak Cipta yang berlaku.
