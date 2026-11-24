# Panduan Instalasi Eka Dashboard

Selamat datang di panduan instalasi **Eka Dashboard**. Panduan ini akan membantu Anda memasang dan menjalankan dashboard pada server atau mesin target Anda (STB, Mini PC, VPS, atau Local Server) yang berbasis sistem operasi Linux.

---

## 1. Persiapan Sistem
Sebelum memulai instalasi, pastikan Anda telah menyiapkan hal-hal berikut:
1. **Perangkat Target**: PC/Laptop/Mini PC/STB dengan OS Linux (Ubuntu, Debian, Armbian, atau OpenWRT dengan fitur Docker).
2. **Akses Terminal/SSH**: Aplikasi seperti PuTTY, PowerShell, atau Terminal bawaan untuk mengakses server Anda.
3. **Koneksi Internet**: Diperlukan untuk mengunduh *dependencies* dan image Docker.

---

## 2. Proses Instalasi (Otomatis)

Dashboard ini dilengkapi dengan *script installer* otomatis (`install.sh`) yang akan mengonfigurasi Docker, memetakan port, dan menjalankan container secara praktis.

### Pilihan A: Instalasi via Git Clone (Rekomendasi)
Jika server Anda sudah terpasang `git`, Anda dapat langsung mengkloning repositori ini:

```bash
# 1. Update sistem dan install git
sudo apt-get update && sudo apt-get install -y git

# 2. Clone repositori Eka Dashboard
git clone https://github.com/recode-project/web_server.git eka_dashboard

# 3. Masuk ke direktori
cd eka_dashboard

# 4. Eksekusi Script Instalasi
sudo bash install.sh
```

### Pilihan B: Instalasi via File ZIP
Jika Anda memiliki file `.zip` (misalnya `eka_dashboard_retail.zip`):
1. **Upload** file `.zip` tersebut ke server Anda (menggunakan SCP, WinSCP, atau FTP).
   ```bash
   scp eka_dashboard_retail.zip root@IP_SERVER_ANDA:/root/
   ```
2. **Ekstrak dan Install** melalui SSH:
   ```bash
   # Install unzip jika belum ada
   sudo apt-get update && sudo apt-get install -y unzip
   
   # Ekstrak file
   unzip eka_dashboard_retail.zip -d eka_dashboard
   
   # Masuk ke folder & Install
   cd eka_dashboard
   sudo bash install.sh
   ```

---

## 3. Apa yang Dilakukan Script Installer?
Saat Anda menjalankan `sudo bash install.sh`, sistem akan melakukan beberapa hal:
- Mengecek dan memasang **Docker** (serta Docker Compose) secara otomatis jika belum ada.
- Memeriksa **Port 80**. Jika server Anda menggunakan *CasaOS* di port 80, port CasaOS akan dipindahkan otomatis ke `9999` untuk menghindari bentrok.
- Membangun dan menjalankan *container* Eka Dashboard secara otomatis.

Jika instalasi sukses, Anda akan melihat pesan seperti:
> **INSTALASI SUKSES!**  
> Silakan akses Dashboard Admin di: `http://<IP_SERVER_ANDA>`

---

## 4. Login Pertama (Setup Wizard)
1. **Akses Dashboard**: Buka *browser* pada perangkat apa saja yang terhubung di jaringan yang sama, lalu masukkan IP Server Anda (misal `http://192.168.1.10`).
2. **Setup Wizard**: Pada akses pertama, Anda akan diarahkan ke halaman Setup Wizard.
3. **Buat Password**: Masukkan dan buat **Password Admin** baru yang akan digunakan untuk mengelola dashboard Anda ke depannya.
4. **Login**: Setelah password berhasil dibuat, masuk (login) menggunakan sandi tersebut. Dashboard Anda kini sudah siap digunakan!

---

## 5. FAQ & Troubleshooting (Kendala & Solusi)

Berikut adalah 15 daftar kendala yang sering terjadi beserta solusinya:

**1. Server menggunakan CasaOS, apakah akan bermasalah?**
Tidak. Script installer otomatis mendeteksi CasaOS dan akan memindahkan port CasaOS dari `80` menjadi `9999`. Anda dapat mengakses CasaOS kembali di `http://IP-SERVER:9999`, sementara Eka Dashboard menggunakan port `80`.

**2. Bagaimana cara mengganti Port Eka Dashboard agar tidak menggunakan Port 80?**
1. Masuk ke direktori instalasi: `cd /root/eka_dashboard`
2. Buka file konfigurasi: `nano docker-compose.yml`
3. Ubah bagian `ports:` dari `- "80:5000"` menjadi `- "8080:5000"` (atau port lain).
4. Simpan perubahan (Ctrl+X, ketik Y, lalu Enter).
5. Terapkan: `sudo docker compose up -d`
6. Akses di: `http://IP-SERVER:8080`

**3. Saya lupa Password Admin, bagaimana cara me-resetnya?**
Hapus file konfigurasi keamanan lalu *restart container*:
```bash
cd /root/eka_dashboard
sudo rm data/security_config.json
sudo docker compose restart
```
Buka kembali dashboard, Anda akan diminta membuat *password* baru.

**4. Error "Permission denied" saat menjalankan script `install.sh`.**
Anda membutuhkan hak eksekusi. Ketik perintah `chmod +x install.sh` lalu jalankan kembali menggunakan `sudo bash install.sh`.

**5. Error "docker-compose: command not found".**
Pada versi Docker terbaru, gunakan perintah `docker compose` (menggunakan spasi, tanpa tanda hubung). Pastikan plugin Docker Compose sudah terpasang di sistem.

**6. Error "port is already allocated" saat proses instalasi (selain CasaOS).**
Artinya port 80 sedang dipakai oleh aplikasi lain (seperti Apache atau Nginx bawaan). Matikan aplikasi tersebut dengan `sudo systemctl stop apache2` atau `sudo systemctl stop nginx`, atau ganti port Eka Dashboard (lihat poin 2).

**7. Dashboard tidak bisa dibuka (timeout) dari PC / HP lain.**
Pastikan perangkat terhubung di jaringan (WiFi/LAN) yang sama dengan server. Pastikan juga IP Address yang dimasukkan benar. Jika menggunakan Ubuntu/Debian, pastikan *firewall* tidak memblokir port 80 dengan menjalankan `sudo ufw allow 80`.

**8. Error "unzip: command not found" saat mencoba mengekstrak file installer.**
Sistem Anda belum memiliki aplikasi unzip. Instal terlebih dahulu dengan mengetik `sudo apt-get update && sudo apt-get install -y unzip`.

**9. Tampilan Dashboard *blank* putih atau berantakan.**
Masalah ini umumnya disebabkan oleh *cache* browser yang nyangkut. Tekan tombol **Ctrl + F5** (di Windows) atau **Cmd + Shift + R** (di Mac) pada halaman dashboard untuk melakukan *Hard Reload*.

**10. Muncul pesan error "502 Bad Gateway".**
Artinya *container* web server sudah berjalan, namun aplikasi di dalamnya masih proses *booting* atau mengalami *crash*. Tunggu sekitar 10-15 detik dan *refresh* halaman. Jika masih error, cek log sistem.

**11. Bagaimana cara melihat pesan error lengkap (Log Sistem)?**
Masuk ke direktori instalasi (`cd /root/eka_dashboard`) dan ketik `sudo docker compose logs -f`. Di situ Anda bisa melihat aktivitas sistem atau peringatan error secara *real-time*. Tekan Ctrl+C untuk keluar.

**12. Bagaimana cara mematikan sementara (stop) Eka Dashboard?**
Masuk ke direktori instalasi, lalu eksekusi perintah `sudo docker compose down`. Untuk menyalakannya kembali, jalankan `sudo docker compose up -d`.

**13. Bagaimana cara memperbarui (Update) Eka Dashboard ke versi terbaru?**
Jika Anda menginstal menggunakan metode Git Clone, ketik perintah berikut di direktori instalasi:
```bash
git pull
sudo docker compose up -d --build
```
Sistem akan otomatis mengunduh kode terbaru dan melakukan *build* ulang tanpa menghilangkan data pengaturan.

**14. Dashboard berjalan sangat lambat atau sering macet.**
Hal ini bisa terjadi jika memori (RAM) server penuh. Gunakan perintah `htop` untuk mengecek status penggunaan CPU dan RAM. Jika RAM sangat minim (< 1GB), disarankan untuk menambahkan *Swap Memory* di Linux Anda minimal 1GB - 2GB.

**15. Error "permission denied while trying to connect to the Docker daemon socket".**
Anda tidak memiliki izin akses ke layanan Docker. Pastikan Anda menambahkan awalan `sudo` di setiap perintah docker, atau masukkan user Anda ke grup docker dengan perintah `sudo usermod -aG docker $USER` lalu relogin.
