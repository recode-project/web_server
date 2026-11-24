# 🎨 Eka Dashboard — Master Design System & Theme Architecture

Dokumen ini adalah **pedoman resmi baku (*design system authority*)** antarmuka Eka Dashboard. Seluruh pengembang dan AI Agent yang menambahkan, memodifikasi, atau memelihara halaman web di dalam Eka Dashboard **WAJIB** mematuhi aturan dan formula di bawah ini guna mencegah regresi visual, hilangnya wallpaper animasi, kerusakan tombol, atau masalah scrolling.

---

## 1. Filosofi Desain & Karakter Visual

Eka Dashboard mengusung konsep **Modern Cybernetic Glassmorphism**:
1. **Dynamic Ambient Wallpaper:** Latar belakang selalu bergerak halus dengan animasi gradien warna-warni (*signature look*) di bawah filter kecerahan redup agar teks tetap terbaca tajam (*high-contrast*).
2. **Frosted Glass Surfaces:** Kartu, tabel, panel navigasi, dan modal menggunakan efek kaca transparan (*backdrop-filter blur*) dengan batas garis halus (*subtle border*).
3. **High-Contrast Readability:** Teks utama putih murni (`#ffffff`), teks sekunder abu-abu redup (`#94a3b8`), dan warna aksen fungsional yang terang untuk status sistem.
4. **Separasi Logika Penuh:** DILARANG KERAS menyematkan inline JavaScript `<script>...</script>` pada file template HTML. Seluruh event, fetch API, dan manipulasi DOM wajib ditempatkan di berkas eksternal `static/<module>.js`.

---

## 2. Aturan Mutlak: Stacking Context, Wallpaper & Scrolling

> [!CAUTION]
> **Penyebab Utama Bug Layar Hitam & Halaman Terkunci:**
> Jika `body` diberi warna solid pekat (misal `background: #0f0c29 !important;`) dan `.wallpaper` memiliki `z-index: -1`, mesin render peramban akan merender elemen wallpaper **di belakang kanvas opaque `body`**, sehingga wallpaper animasi tertutup total dan layar menjadi hitam pekat.
> Selain itu, jika `body` diberi `height: 100vh; overflow: hidden;`, halaman tidak dapat digulir ke bawah (*scroll locked*).

### Formula Baku Stacking Context & Scroll (Wajib di Setiap Halaman):

```html
<style>
    /* 1. Kanvas Dasar: html memegang warna fallback, body wajib transparan */
    html {
        background: #0f0c29 !important; /* Mencegah kedipan putih saat navigasi */
    }
    body {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-main, #ffffff) !important;
        background: transparent !important; /* WAJIB TRANSPARAN agar wallpaper terlihat */
        height: auto !important;
        min-height: 100vh !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;       /* WAJIB AUTO agar konten panjang bisa di-scroll */
        position: relative !important;
        user-select: auto !important;
    }

    /* 2. Signature Animated Gradient Wallpaper */
    .wallpaper {
        position: fixed !important;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
        z-index: 0 !important;             /* Berada tepat di atas kanvas html, di bawah konten */
        filter: brightness(0.55);          /* Kecerahan standar agar kontras teks optimal */
        pointer-events: none !important;   /* WAJIB agar tidak mencegat klik/interaksi mouse */
        transform: translateZ(0);          /* Akselerasi hardware GPU */
    }

    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* 3. Kontainer Utama Konten */
    .main-content, .page-wrap {
        position: relative !important;
        z-index: 1 !important;             /* Berada di atas wallpaper */
        max-width: 1400px;
        margin: 0 auto;
        padding: 24px 24px 100px 24px;     /* Buffer bawah 100px agar form bawah tidak terpotong */
    }
</style>
```

---

## 3. Sistem Palet Warna & Variabel Desain

Gunakan token CSS variabel baku berikut:

| Token / Variabel | Nilai Baku | Kegunaan |
| :--- | :--- | :--- |
| `--glass-bg` | `rgba(15, 23, 42, 0.65)` | Latar belakang kartu kaca primer (Slate 900 translucent) |
| `--glass-card` | `rgba(30, 41, 59, 0.55)` | Latar belakang kartu sekunder / nested container |
| `--glass-border` | `rgba(255, 255, 255, 0.08)` | Garis tepi halus standar kaca |
| `--glass-highlight`| `rgba(255, 255, 255, 0.16)` | Garis tepi saat hover kartu |
| `--text-main` | `#ffffff` | Judul, label penting, dan angka telemetri |
| `--text-muted` | `#94a3b8` | Subtitle, helper text, dan header tabel |
| `--text-dim` | `#64748b` | Timestamp redup dan metadata pendukung |
| `--status-danger` | `#ef4444` (`#ff6b6b`) | CPU tinggi, kegagalan sistem, tombol hapus/batal |
| `--status-success`| `#10b981` (`#4ecdc4`) | Service running, S.M.A.R.T. passed, tombol simpan |
| `--status-warning`| `#f59e0b` (`#ffe66d`) | Disk >85%, pending reboot, tombol perhatian |
| `--status-info` | `#38bdf8` (`#4facfe`) | Jaringan, VPN, package updates, tombol navigasi |
| `--status-purple` | `#a855f7` | Daemon otomatis, integrasi webhook, task background |

---

## 4. Komponen Antarmuka Standar (UI Component Library)

### A. Top Navigation Bar (`.top-bar-scheduler` / `.page-header`)
Header setiap halaman modul wajib memuat tombol Home, judul modul dengan ikon aksen, subtitle deskriptif, dan kelompok tombol aksi cepat di sisi kanan:

```html
<div class="top-bar-scheduler">
    <div class="left-group" style="display: flex; align-items: center; gap: 16px;">
        <a href="/dashboard" class="btn-home" title="Kembali ke Dashboard">
            <i class="fa-solid fa-home"></i>
        </a>
        <div class="title-group">
            <div class="main-title" style="display: flex; align-items: center; gap: 10px; font-size: 20px; font-weight: 700; color: #fff;">
                <i class="fa-solid fa-bell" style="color: #fa709a;"></i>
                <span>Nama Modul</span>
            </div>
            <div class="sub-title" style="font-size: 13px; color: #94a3b8; margin-top: 2px;">
                Deskripsi ringkas fungsi modul server
            </div>
        </div>
    </div>
    <div class="actions" style="display: flex; align-items: center; gap: 12px;">
        <button id="btn-secondary-action" class="btn btn-secondary">
            <i class="fa-solid fa-arrows-rotate"></i> Refresh
        </button>
        <button id="btn-primary-action" class="btn btn-primary">
            <i class="fa-solid fa-floppy-disk"></i> Simpan
        </button>
    </div>
</div>
```

### B. Glassmorphic Button System (Telah Dibakukan di `static/style.css`)
Seluruh tombol wajib menggunakan kelas `.btn` agar tidak kembali ke tampilan tombol bawaan HTML browser:

```css
/* Kelas Tombol Baku */
.btn {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 12px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn:hover {
    background: rgba(255, 255, 255, 0.18);
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.3);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25);
}

/* Varian Tombol */
.btn-secondary { background: rgba(255, 255, 255, 0.08); color: #e2e8f0; }
.btn-primary   { background: linear-gradient(135deg, #10b981, #059669); color: #fff; }
.btn-danger    { background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff; }
.btn-warning   { background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; }
```

### C. 4-Column Stat Summary Cards
Digunakan untuk menampilkan ringkasan telemetri penting di bagian atas halaman:

```html
<div class="stats-grid-4" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px;">
    <div class="stat-card-glass" style="background: rgba(15, 23, 42, 0.65); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; display: flex; align-items: center; justify-content: space-between;">
        <div class="stat-info">
            <div class="stat-label" style="font-size: 11px; text-transform: uppercase; font-weight: 600; color: #94a3b8; letter-spacing: 0.5px;">Label Metrik</div>
            <div class="stat-val" style="font-size: 26px; font-weight: 700; color: #fff; margin: 4px 0;">Nilai Metrik</div>
            <div class="stat-sub" style="font-size: 12px; color: #64748b;">Sub-keterangan dinamis</div>
        </div>
        <div class="stat-icon" style="width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; background: rgba(56, 189, 248, 0.15); color: #38bdf8;">
            <i class="fa-solid fa-chart-line"></i>
        </div>
    </div>
</div>
```

### D. Tab Navigation Navigation Bar
Untuk modul dengan banyak sub-fungsi (contoh: 3-4 Tab):

```html
<div class="tab-bar" style="display: flex; gap: 8px; margin-bottom: 24px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 12px;">
    <button class="tab-btn active" data-tab="tab-content-1">
        <i class="fa-solid fa-list-check"></i> Tab Utama
    </button>
    <button class="tab-btn" data-tab="tab-content-2">
        <i class="fa-solid fa-clock-rotate-left"></i> Riwayat & Log
    </button>
</div>
```

### E. Monospace Terminal / Console Log Box
Untuk menampilkan live output command CLI, kernel log, atau streaming APT/S.M.A.R.T.:

```css
.terminal-box {
    background: #090d16;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
    color: #10b981;
    height: 480px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    line-height: 1.6;
}
```

---

## 5. Daftar Periksa Kepatuhan (Multi-Agent Compliance Checklist)

Sebelum menyelesaikan pekerjaan atau merilis modul baru, periksa 8 poin wajib ini:

- [ ] **1. Wallpaper Aktif:** Apakah `.wallpaper` menggunakan formula `fixed`, `z-index: 0`, dan `pointer-events: none`?
- [ ] **2. Body Transparan:** Apakah `body` diset `background: transparent !important;` sehingga wallpaper tidak tertutup latar hitam?
- [ ] **3. Scrolling Berfungsi:** Apakah `html, body` memiliki `height: auto !important; min-height: 100vh !important; overflow-y: auto !important;` dan dapat digulir bebas hingga ujung bawah?
- [ ] **4. Bottom Padding Buffer:** Apakah `.main-content` memiliki padding bawah minimal `100px` (`padding-bottom: 100px;`)?
- [ ] **5. Tombol Glassmorphic:** Apakah seluruh tombol menggunakan kelas `.btn`, `.btn-secondary`, atau `.btn-primary` dan terhindar dari tampilan tombol mentah HTML?
- [ ] **6. Isolasi JavaScript:** Apakah seluruh logika JavaScript terpisah 100% di berkas `static/<module>.js` tanpa satu pun script inline?
- [ ] **7. Dynamic Host Discovery:** Apakah seluruh data dideteksi dinamis via kernel/API tanpa hardcode IP personal atau kredensial?
- [ ] **8. Flask Template Auto-Reload:** Pastikan perubahan template langsung terbaca di server produksi melalui konfigurasi reload dan restart kontainer.

