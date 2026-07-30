# CollectAI Frontend

SPA untuk petugas collection dan supervisor: dashboard operasional, daftar &
detail customer/kontrak, antrean approval restrukturisasi, dan panel governance
model AI.

Konsumen dari [`app/backend/`](../backend/README.md). Frontend **tidak pernah**
menyentuh database secara langsung.

---

## Tech stack

| Kebutuhan | Pilihan | Versi |
|---|---|---|
| Framework | React | ^19.2.7 |
| Build / dev server | Vite | ^8.1.1 |
| Bahasa | TypeScript | ~6.0.2 |
| Routing | react-router-dom | ^7.18.1 |
| Data fetching & cache | @tanstack/react-query | ^5.101.3 |
| HTTP client | ky | ^2.0.2 |
| Validasi response | zod | ^4.4.3 |
| Styling | Tailwind CSS (token Material Design 3) | ^3.4.19 |
| Linter | oxlint (**bukan** ESLint) | ^1.71.0 |
| Mock API | msw | ^2.15.0 |

Yang **tidak** dipakai, supaya tidak dicari-cari: tidak ada library chart (grafik
dibuat manual dengan div + persentase tinggi), tidak ada paket icon (Material
Symbols di-load lewat `@import` Google Fonts di `src/index.css`), tidak ada
library form (dipakai custom hook), dan **belum ada test runner**.

---

## Quick start

```bash
npm install
npm run dev          # http://localhost:5173
```

Prasyarat: Node 20+ (Docker Compose memakai Node 24). Login dev: `admin` / `admin123`
— user itu diprovisioning dari sisi backend
(`cd app/backend && python -m scripts.seed_dev_user`).

### Script yang tersedia

| Script | Fungsi |
|---|---|
| `npm run dev` | Dev server Vite dengan HMR |
| `npm run build` | `tsc -b && vite build` — typecheck dulu, baru bundle |
| `npm run lint` | oxlint |
| `npm run preview` | Serve hasil build produksi secara lokal |

Belum ada `npm test`.

### Environment

`.env.development` (satu-satunya file env yang ada):

```
VITE_API_BASE_URL=/api
VITE_ENABLE_MSW=false
```

| Variabel | Dibaca di | Fungsi |
|---|---|---|
| `VITE_API_BASE_URL` | `src/api/client.ts` | Prefix ky. Default `/api` kalau tidak diset |
| `VITE_ENABLE_MSW` | `src/main.tsx` | `'true'` ⇒ nyalakan mock MSW, tidak menyentuh backend |
| `VITE_API_PROXY_TARGET` | `vite.config.ts` | Target proxy dev. Default `http://localhost:8000`. **Dibaca saat config dievaluasi (konteks Node), bukan di kode klien** |

**Proxy dev** memetakan `/api` → `{target}/api/v1` (lihat `rewrite` di
`vite.config.ts`), karena backend menyajikan API di bawah `/api/v1`. Jadi kode
aplikasi cukup memanggil `customers/CUST-00029` tanpa peduli prefix versi.

---

## Struktur `src/`

```text
src/
├── api/                    # infrastruktur HTTP + React Query
│   ├── client.ts           #   instance ky tunggal + apiRequest<T>()
│   ├── apiError.ts         #   ApiError berkategori + pesan untuk user
│   ├── caseTransform.ts    #   snakeToCamelDeep()
│   ├── queryClient.ts      #   default staleTime/retry
│   └── queryKeys.ts        #   namespace key React Query (satu objek frozen)
├── auth/                   # sesi & guard route
│   ├── tokenStorage.ts     #   localStorage key `collectai.auth.token`
│   ├── useAuthToken.ts     #   sinkronisasi state auth lintas tab/event
│   ├── RequireAuth.tsx     #   guard: ada token? render : redirect /login
│   └── RootRedirect.tsx    #   "/" → /dashboard atau /login
├── components/             # 24 komponen presentasional bersama
│   └── skeletons/          #   8 skeleton loading per halaman
├── config/
│   └── staticContent.ts    #   item nav (5 menu), badge compliance, copy login
├── domains/                # ← inti organisasi kode, lihat di bawah
│   ├── auth/  dashboard/  customer/  contract/
│   ├── restructuring/  ai-intelligence/
│   └── shared/riskSegment.ts   # enum 4 risk segment + tone chip-nya
├── hooks/                  # 6 hook lintas domain (debounce, pagination, dst)
├── layouts/
│   ├── AppLayout.tsx       #   shell: Sidebar + TopBar + satu <main> scrollable
│   └── sidebarStorage.ts   #   persist state collapsed
├── lib/format.ts           # formatRupiah, formatPercent, nama bulan Indonesia
├── mocks/                  # MSW: browser.ts + handlers/ + fixtures/
├── pages/                  # 10 halaman
├── App.tsx                 # definisi route
├── main.tsx                # bootstrap: prepareApp() → QueryClientProvider
└── index.css               # font, @tailwind, reset
```

### Konvensi `domains/`

Setiap domain bisnis memakai trio yang sama — ini pola paling penting untuk
dipahami sebelum menambah fitur:

```text
domains/customer/
├── customer.schema.ts        # skema Zod + type hasil inferensinya
├── customer.api.ts           # fungsi pemanggil endpoint
├── useCustomerListQuery.ts   # satu file per hook React Query
├── useCustomerDetailQuery.ts
└── ...
```

Halaman **hanya** meng-import hook, tidak pernah memanggil `apiClient` langsung.
Type tidak ditulis tangan — semuanya diturunkan dari skema Zod, jadi bentuk
runtime dan compile-time tidak bisa berbeda.

---

## Lapisan API

Semua request melewati satu instance ky di `src/api/client.ts`:

| Perilaku | Nilai |
|---|---|
| Prefix | `VITE_API_BASE_URL ?? '/api'` |
| Timeout | **10 detik** (global, tidak ada override per-route) |
| Retry | Maksimal 2 kali tambahan, **hanya untuk GET**, pada status 408/429/500/502/503/504 |
| Header auth | Hook `beforeRequest` menyisipkan `Authorization: Bearer <token>` kalau token ada |
| Penanganan 401 | Hook `afterResponse` menghapus token lalu men-dispatch event global `auth:unauthorized`; `useAuthToken` mendengarkannya sehingga `RequireAuth` langsung redirect ke `/login`. Logout memakai event yang sama secara sengaja |

Setiap pemanggilan dibungkus `apiRequest<T>(promise, schema, mapper?)`:

1. Await request; exception apa pun dinormalisasi lewat `toApiError()`.
2. Parse JSON.
3. Jalankan `mapper` kalau ada — semua domain **kecuali auth** meneruskan
   `snakeToCamelDeep`, karena backend mengirim `snake_case`.
4. `schema.safeParse()`. Gagal ⇒ throw `ApiError` berkategori `'validation'`.

Konsekuensi penting: **kalau bentuk response backend berubah, frontend
menampilkan error yang jelas, bukan merender data sampah.** Kalau Anda melihat
*"server returned data in an unexpected format"*, bandingkan response asli di tab
Network dengan `src/domains/<modul>/<modul>.schema.ts`.

Default React Query (`src/api/queryClient.ts`): query `staleTime: 30_000`,
`refetchOnWindowFocus: false`, `retry: 1`; mutation `retry: 0`.

> Perlu diketahui saat menambah endpoint yang lambat: timeout 10 detik itu
> **global**. Endpoint yang butuh lebih lama (misal pemanggilan LLM) wajib
> memberi override `timeout` per-request, atau memakai pola `202` + polling.

---

## Routing

`BrowserRouter` dengan `<Routes>` datar di `src/App.tsx`. Tidak ada lazy
loading, tidak ada route catch-all/404.

| Path | Halaman | Guard |
|---|---|---|
| `/login` | `LoginPage` | — |
| `/access` | `RecoveryAccessPage` (redirect ke `/login`) | — |
| `/` | `RootRedirect` | Ada token ⇒ `/dashboard`, else `/login` |
| `/dashboard` | `DashboardPage` | `RequireAuth` |
| `/customers` | `CustomerListPage` | `RequireAuth` |
| `/customers/:id` | `CustomerDetailPage` | `RequireAuth` |
| `/contracts` | `ContractListPage` | `RequireAuth` |
| `/contracts/:contractNo` | `ContractDetailPage` | `RequireAuth` |
| `/restructuring-approval` | `RestructuringApprovalPage` | `RequireAuth` |
| `/restructuring-approval/:id` | `RestructuringGroupDetailPage` | `RequireAuth` |
| `/ai-intelligence` | `AiIntelligencePage` | `RequireAuth` |

State auth **hanya** berarti "ada token di localStorage" — tidak ada parsing masa
berlaku token di sisi klien; kedaluwarsa dideteksi saat backend menjawab `401`.

**Belum ada RBAC.** Kelima menu terlihat oleh setiap user yang login, termasuk
Restructuring Approval dan AI Intelligence. Ini penundaan yang disengaja dan
dicatat di `src/config/staticContent.ts`.

---

## Styling & tema

Tailwind v3 dengan **token bernama Material Design 3** di `theme.extend`
(`tailwind.config.js`):

- **~55 token warna** memakai nama peran M3: `primary`, `primary-container`,
  `on-primary-container`, `surface-container-low|high|highest`, `on-surface`,
  `on-surface-variant`, `outline`, `outline-variant`, `inverse-surface`, dst.
  Plus tambahan semantik non-M3: `success`, `warning` beserta varian
  container-nya. Palet: navy primer (`#000f22`) di atas netral terang.
- **Skala tipografi M3** sebagai token `fontSize`: `display-lg`, `headline-lg`,
  `title-md`, `body-lg`, `label-md`, dst — masing-masing sudah membawa
  lineHeight/letterSpacing/fontWeight.
- Token spacing (`gutter-desktop`, `margin-mobile`), `maxWidth.container: 1440px`.

Artinya: **jangan pakai warna Tailwind mentah** seperti `bg-gray-100` atau
`text-slate-700` di kode baru. Pakai token peran (`bg-surface-container`,
`text-on-surface-variant`) supaya konsisten dengan seluruh aplikasi.

Ikon dirender sebagai ligature Material Symbols
(`<span className="material-symbols-outlined">grid_view</span>`); nama ikonnya
terkumpul di `src/config/staticContent.ts`.

### Status dark mode

`darkMode: 'class'` sudah dikonfigurasi dan markup-nya **sudah ditulis** —
~373 utility `dark:` tersebar di 30 file. Tapi **tidak ada kode yang pernah
menambahkan class `dark`**: tidak ada toggle tema, tidak ada penyimpanan
preferensi, tidak ada pembacaan `prefers-color-scheme`. Jadi style dark saat ini
tidak bisa dicapai kecuali class-nya diset manual di devtools.

Untuk menyelesaikannya, yang dibutuhkan hanya toggle + persistensi (polanya sudah
ada di `src/layouts/sidebarStorage.ts`) — style-nya sendiri sudah siap.

---

## Mode mock (MSW)

Frontend bisa jalan **tanpa backend**:

```bash
VITE_ENABLE_MSW=true npm run dev
```

- Handler ada di `src/mocks/handlers/` (customer, dashboard, contract,
  restructuring, ai-intelligence), fixture di `src/mocks/fixtures/`.
- Beberapa fixture bersifat *stateful* — misal `advanceSyncFixture()` memajukan
  status job Sync tiap kali di-poll, sehingga alur loading bisa diuji.
- `auth.handlers.ts` **sengaja tidak dimasukkan** ke agregat handler: auth sudah
  diimplementasikan backend sungguhan, dan `onUnhandledRequest: 'bypass'`
  membuat `/auth/*` diteruskan lewat proxy Vite ke backend.

Docker Compose menyalakan MSW secara default (`VITE_ENABLE_MSW: "true"`). Set
`false` kalau ingin data sungguhan.

---

## Dokumentasi kontrak API

[`docs/api/`](docs/api/README.md) berisi dokumentasi setiap endpoint HTTP yang
dipanggil frontend — bentuk request/response, kode status, dan tempat kode-nya
berada. Berguna ketika mengubah kontrak di kedua sisi.

Untuk dokumentasi endpoint yang bisa dieksekusi langsung, jalankan backend lalu
buka http://localhost:8000/docs (Swagger UI, ada tombol "Try it out").

---

## Menambah halaman/fitur baru

1. **Skema dulu.** Tulis bentuk response di
   `src/domains/<domain>/<domain>.schema.ts` sebagai skema Zod. Type diturunkan
   dari situ, jangan ditulis tangan.
2. **Fungsi API.** Tambah di `<domain>.api.ts`, bungkus dengan `apiRequest`,
   teruskan `snakeToCamelDeep` sebagai mapper.
3. **Query key.** Daftarkan di `src/api/queryKeys.ts` — jangan menuliskan array
   key inline di komponen.
4. **Hook.** Satu file per hook: `use<Sesuatu>Query.ts` / `use<Sesuatu>Mutation.ts`.
5. **Halaman.** Import hook-nya saja. Sediakan skeleton di
   `src/components/skeletons/` untuk state loading.
6. **Route + nav.** Tambah `<Route>` di `App.tsx` (bungkus `RequireAuth` kalau
   perlu login) dan item nav di `src/config/staticContent.ts`.
7. `npm run lint && npm run build` sebelum commit.

## Batasan yang diketahui

1. **Belum ada test runner** — hanya oxlint. Tidak ada vitest/jest maupun file test.
2. **Dark mode belum bisa diaktifkan** (lihat di atas).
3. **Belum ada RBAC** — semua menu untuk semua user yang login.
4. **Tidak ada route 404**; path yang tidak dikenal merender halaman kosong.
5. **Body error backend tidak dibaca** — frontend hanya melihat status HTTP.
   Backend boleh mengirim `{"message": "..."}`, tapi belum ditampilkan.
6. **Timeout 10 detik bersifat global** dan tidak di-override di mana pun.
7. `@tanstack/react-query-devtools` sudah ter-install tapi **belum di-import**
   di mana pun.
