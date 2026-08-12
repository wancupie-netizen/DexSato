# DexSato Railway Migration — KIV

**Status:** Ditangguhkan (KIV)  
**Tarikh audit:** 12 Ogos 2026  
**Repositori yang diaudit:** `wancupie-netizen/DexSato` — branch `main`  
**Keputusan:** Kekalkan operasi pada PC buat masa sekarang.

## 1. Tujuan dokumen

Dokumen ini menyimpan hasil audit kesiapsiagaan DexSato untuk dipindahkan daripada Windows PC ke Railway. Ia disediakan supaya migrasi boleh disambung kemudian tanpa perlu mengulangi penilaian asas.

Dokumen ini bukan arahan untuk memulakan migrasi sekarang.

## 2. Keputusan semasa

Railway sesuai secara teknikal untuk DexSato, tetapi migrasi belum efisien pada peringkat semasa kerana:

- belum ada pengguna atau pelawat aktif;
- operasi PC semasa sudah stabil;
- migrasi tidak menambah mutu decision engine;
- kerja utama melibatkan penyimpanan state, scheduler, health monitoring dan operasi cloud;
- masa pembangunan lebih bernilai jika digunakan untuk meningkatkan mutu engine dan output pasaran.

Oleh itu, operasi semasa dikekalkan:

- dashboard FastAPI berjalan pada Windows PC;
- Windows Task Scheduler menjalankan scan pada 08:00, 14:00 dan 20:00 MYT;
- Cloudflare Tunnel menerbitkan `https://app.dexsato.com`;
- Cloudflare Access melindungi dashboard;
- Supabase menyimpan market dan intelligence events;
- fail snapshot dan rekod automation terbaru kekal pada PC.

## 3. Mengapa kod semasa belum boleh terus dideploy

### 3.1 Web server terikat kepada localhost

FastAPI kini menggunakan `127.0.0.1:8000`. Railway memerlukan aplikasi mendengar pada `0.0.0.0` dan menggunakan port yang diberikan melalui environment variable `PORT`.

### 3.2 Snapshot masih menggunakan fail tempatan

Snapshot canonical disimpan pada:

```text
output/snapshots/latest_snapshot.json
```

Filesystem deployment Railway tidak boleh dianggap kekal selepas redeploy atau pemindahan host.

### 3.3 Rekod run terakhir juga menggunakan fail tempatan

Status automation terakhir disimpan pada:

```text
output/automation/latest_run.json
```

Servis web dan servis cron Railway tidak patut bergantung pada fail tempatan untuk berkongsi state.

### 3.4 Health monitoring bergantung pada Windows

Dashboard memeriksa Windows Scheduled Tasks melalui `schtasks.exe`. Railway menggunakan Linux, maka status scheduler akan menjadi `UNSUPPORTED` jika kod semasa digunakan tanpa abstraction baharu.

### 3.5 Konfigurasi deployment belum tersedia

Repositori belum mempunyai konfigurasi khusus Railway seperti runtime pin, start command canonical atau Railway config-as-code. Dependency dalam `requirements.txt` juga belum dipin kepada versi tertentu.

## 4. Seni bina sasaran apabila migrasi dimulakan

Gunakan dua servis Railway daripada repositori yang sama:

### A. `dexsato-web`

- Menjalankan dashboard FastAPI.
- Membaca snapshot dan system status daripada Supabase.
- Menggunakan health endpoint `/health`.
- Tidak menjalankan market scan ketika halaman dibuka.

### B. `dexsato-cron`

- Menjalankan `python founder_scheduler.py`.
- Melakukan satu scan lengkap dan kemudian keluar.
- Berjalan tiga kali sehari menggunakan UTC:

```cron
0 0,6,12 * * *
```

Jadual tersebut bersamaan:

| UTC | MYT |
|---:|---:|
| 00:00 | 08:00 |
| 06:00 | 14:00 |
| 12:00 | 20:00 |

### C. Supabase sebagai shared state

Supabase menjadi sumber canonical untuk:

- latest market snapshot;
- automation run history;
- status Telegram terakhir;
- waktu scan terakhir;
- meaningful changes;
- health/freshness data;
- market, intelligence, outcome, learning dan knowledge events sedia ada.

Railway Volume tidak dicadangkan sebagai penyelesaian utama kerana web dan cron perlu berkongsi state secara selamat.

## 5. Skop kerja migrasi

Anggaran keseluruhan ialah 6 kelompok kerja, sekitar 12–20 fail kod, konfigurasi, migration dan ujian.

### Fasa 1 — Deployment readiness

- Sokong `HOST=0.0.0.0` dan environment variable `PORT`.
- Tentukan dan pin versi Python yang disokong.
- Pin dependency production.
- Tetapkan start command web dan cron.
- Tambah konfigurasi Railway yang boleh diaudit.

### Fasa 2 — Shared state repository

- Reka schema Supabase untuk snapshot dan automation runs.
- Tambah repository interface yang tidak bergantung pada filesystem.
- Kekalkan file repository untuk operasi PC semasa jika masih diperlukan.
- Pastikan penulisan snapshot bersifat atomic/idempotent.
- Pastikan dashboard hanya membaca snapshot lengkap yang terakhir berjaya.

### Fasa 3 — Platform-neutral health monitoring

- Pisahkan Windows Task Scheduler adapter daripada core health logic.
- Tambah Railway/cloud health adapter.
- Tentukan scheduler health berdasarkan last successful run dan expected scan window.
- Paparkan status provider, Telegram dan snapshot secara berasingan.

### Fasa 4 — Cron safety

- Tambah database lock supaya hanya satu scan boleh aktif.
- Gunakan `run_id` unik untuk setiap scan.
- Elakkan Telegram berganda.
- Tetapkan had masa keseluruhan run.
- Pastikan semua proses dan connection ditutup sebelum cron tamat.

### Fasa 5 — Network resilience

- Kekalkan timeout pada setiap external API request.
- Tambah retry terhad dengan exponential backoff.
- Bezakan provider timeout, rate limit dan payload invalid.
- Jangan menggantikan snapshot terakhir yang sihat dengan hasil kritikal yang tidak lengkap.

### Fasa 6 — Security dan operasi

- Jadikan repositori private sebelum production cloud deployment.
- Simpan Supabase, Telegram dan Twelve Data credentials sebagai Railway sealed variables.
- Audit Supabase RLS dan hak akses setiap table.
- Lindungi atau matikan `POST /telegram/send` dalam production.
- Pastikan Railway-generated domain tidak memintas Cloudflare Access.
- Sediakan logs, alerts, spending limit, rollback dan backup.

## 6. Risiko dan mitigasi

| Risiko | Kesan | Mitigasi wajib |
|---|---|---|
| Web dan cron menggunakan fail berbeza | Dashboard stale atau kosong | Gunakan Supabase sebagai shared state |
| PC dan Railway scan serentak | Telegram dan data berganda | Database lock dan controlled cutover |
| Cron tergantung | Run berikutnya dilangkau | Timeout, bounded retry dan hard runtime limit |
| Domain Railway terbuka | Cloudflare Access boleh dipintas | Tutup direct public domain atau tambah application auth |
| Endpoint Telegram boleh dicetuskan orang luar | Spam Telegram | Auth atau disable endpoint production |
| Dependency berubah semasa build | Deployment tidak konsisten | Pin Python dan package versions |
| Secret bocor | Akses database/bot terdedah | Sealed variables dan secret rotation |
| Health logic masih Windows-only | Status palsu di dashboard | Platform-neutral health model |
| Provider API gagal | Snapshot separa/gagal | Retry policy dan preserve last-known-good snapshot |
| Migration schema lemah | Data exposure atau corruption | Migration review, RLS, tests dan rollback |

## 7. Strategi migrasi selamat

### Tahap 1 — Development environment

- Deploy kepada Railway tanpa menukar domain production.
- Gunakan Telegram test chat atau matikan delivery.
- Sahkan build, health endpoint dan Supabase connectivity.

### Tahap 2 — Shadow run

- Jalankan PC sebagai production canonical.
- Jalankan Railway selama 3–7 hari tanpa menghantar Telegram production.
- Bandingkan keputusan, masa scan, unavailable markets dan snapshot payload.

### Tahap 3 — Controlled cutover

- Ambil backup snapshot dan konfigurasi.
- Aktifkan Telegram pada Railway.
- Matikan Windows scan tasks.
- Alihkan `app.dexsato.com` kepada Railway melalui Cloudflare.
- Kekalkan PC sebagai rollback sementara, tetapi jangan jalankan scheduler serentak.

### Tahap 4 — Observation

- Pantau sekurang-kurangnya tujuh hari.
- Semak semua tiga scan harian.
- Semak Telegram, snapshot freshness, logs dan kos.
- Hanya tutup infrastruktur PC selepas Railway terbukti stabil.

## 8. Syarat untuk membuka semula migrasi

Migrasi patut dikeluarkan daripada KIV apabila sekurang-kurangnya satu keadaan berlaku:

- DexSato mula mempunyai founder testers atau pengguna luar;
- marketing mula membawa trafik ke dashboard;
- dashboard perlu tersedia 24/7;
- PC tidak lagi boleh dijadikan host yang konsisten;
- scan atau Telegram kerap terlepas kerana PC ditutup;
- keperluan operasi jauh dan monitoring cloud menjadi penting.

Sebelum pembangunan dimulakan, pastikan juga:

- output engine telah memuaskan;
- UI telah stabil;
- Telegram output telah stabil;
- schema Supabase semasa telah diaudit;
- semua ujian pada `main` lulus;
- backup dan rollback plan diluluskan;
- had kos Railway ditetapkan.

## 9. Anggaran pelaksanaan

- Pembangunan dan ujian: **4–7 hari kerja fokus**.
- Shadow observation: **3–7 hari**.
- Cutover: **satu sesi terkawal**, selepas semua acceptance checks lulus.

Anggaran ini perlu disemak semula berdasarkan keadaan repositori dan harga Railway pada tarikh migrasi sebenar.

## 10. Perkara yang tidak boleh diubah semasa migrasi

- Decision engine canonical.
- Interpretation engine canonical.
- Signal detector canonical.
- Observation builder canonical.
- Market rules yang telah diluluskan.
- Telegram meaningful-change policy tanpa permintaan produk berasingan.
- UI production tanpa skop perubahan UI yang jelas.

Migrasi ialah perubahan infrastructure dan persistence, bukan peluang untuk menulis semula core engine.

## 11. Definition of Done

Migrasi hanya dianggap selesai apabila:

- dashboard boleh diakses melalui `app.dexsato.com`;
- Cloudflare Access masih berfungsi;
- tiga scan harian berjalan mengikut MYT;
- snapshot tersimpan secara persisten;
- dashboard membaca snapshot yang sama yang dihasilkan cron;
- Telegram tidak berganda;
- satu provider failure tidak merosakkan last-known-good snapshot;
- health dashboard tidak bergantung pada Windows;
- secrets tidak wujud dalam Git atau logs;
- semua automated tests dan migration tests lulus;
- rollback ke PC telah diuji atau didokumentasikan;
- kos dan alert penggunaan telah ditetapkan.

## 12. Keutamaan semasa

Sehingga syarat migrasi dipenuhi, keutamaan DexSato ialah:

1. meningkatkan ketepatan dan mutu engine asas;
2. meningkatkan kualiti evidence dan keputusan;
3. mengurangkan false meaningful changes;
4. meningkatkan kebolehpercayaan external data providers;
5. mengumpul bukti prestasi dan feedback pengguna;
6. meneruskan marketing validation sebelum menambah kos dan kompleksiti cloud.

---

**Ringkasan keputusan:** Railway ialah sasaran hosting yang sesuai untuk DexSato, tetapi migrasi ditangguhkan kerana belum memberikan pulangan yang setimpal pada peringkat tanpa pengguna. PC kekal sebagai production Founder Version sehingga trigger migrasi dipenuhi.
