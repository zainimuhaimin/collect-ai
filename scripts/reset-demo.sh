#!/usr/bin/env bash
# scripts/reset-demo.sh — Reset CollectAI ke kondisi kosong untuk demo/testing
# dari awal. Dijalankan dari mana saja, path dihitung relatif ke lokasi script
# ini sendiri.
#
# Menghapus:
#   1. SEMUA data di database lewat TRUNCATE ... RESTART IDENTITY CASCADE
#      (struktur tabel dari schema.sql TIDAK disentuh — hanya isinya).
#      Tabel `users` (login/identity) DIKECUALIKAN secara default supaya
#      kredensial dev tetap bisa dipakai setelah reset — pakai --include-users
#      kalau ingin ikut menghapusnya juga (lalu wajib re-seed manual).
#   2. Artifact model ML: app/machine-learning/models/*.json dan *.pkl
#      (termasuk models/archive/ — dicari rekursif).
#   3. app/machine-learning/logs/scoring_log.csv
#
# TIDAK menjalankan generator data maupun training ulang — itu langkah
# terpisah setelah reset (lihat README.md root, "3. Seed data & model pertama").
#
# Pakai:
#   ./scripts/reset-demo.sh                  # dengan konfirmasi interaktif
#   ./scripts/reset-demo.sh --yes            # lewati konfirmasi (untuk CI/otomatis)
#   ./scripts/reset-demo.sh --include-users  # ikut TRUNCATE tabel `users` juga

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SKIP_CONFIRM=false
INCLUDE_USERS=false
for arg in "$@"; do
  case "$arg" in
    --yes) SKIP_CONFIRM=true ;;
    --include-users) INCLUDE_USERS=true ;;
    *)
      echo "Argumen tidak dikenal: $arg" >&2
      echo "Pakai: $0 [--yes] [--include-users]" >&2
      exit 1
      ;;
  esac
done

# Kredensial DB — sama seperti backend/ML/faker: baca PG* dari .env root.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=collect_ai}"
export PGHOST PGPORT PGUSER PGDATABASE
# PGPASSWORD (kalau ada di .env) sudah ke-export lewat `source` di atas —
# psql membacanya otomatis dari environment, tidak perlu diteruskan manual.

# Urutan tidak penting — TRUNCATE ... CASCADE menangani FK apa pun yang ada.
# Daftar ini HARUS mencakup seluruh tabel di schema.sql (root) selain `users`.
TABLES=(
  customer_master contract_snapshot payment_history lkp_interaction
  ai_intelligence_output customer_behavioral_standing scoring_labels
  shadow_scores model_monitoring_log
  restructuring_group_map restructuring_recommendation_output
  restructuring_history restructuring_approval_log
  product_conversion_mapping asset_appraisal
  model_governance_config model_governance_audit_log
  ai_reasoning_output
)
if [ "$INCLUDE_USERS" = true ]; then
  TABLES+=(users)
fi
TABLE_LIST=$(IFS=,; echo "${TABLES[*]}")

MODELS_DIR="$ROOT_DIR/app/machine-learning/models"
SCORING_LOG="$ROOT_DIR/app/machine-learning/logs/scoring_log.csv"

# Hitung dulu file .json/.pkl yang BENAR-BENAR ada SEBELUM menampilkan
# ringkasan konfirmasi — supaya yang ditampilkan ke user adalah daftar file
# nyata, bukan sekadar pola glob. List yang sama ini dipakai lagi saat
# eksekusi (bukan find ulang) supaya tidak ada file baru yang muncul di
# antara waktu konfirmasi dan penghapusan yang tidak sempat ditampilkan.
MODEL_FILES=""
if [ -d "$MODELS_DIR" ]; then
  MODEL_FILES=$(find "$MODELS_DIR" -type f \( -name "*.json" -o -name "*.pkl" \) -print | sort)
fi

echo "=== CollectAI — Reset Demo ==="
echo
echo "Database : ${PGHOST}:${PGPORT}/${PGDATABASE} (user: ${PGUSER})"
echo "Tabel yang akan di-TRUNCATE (${#TABLES[@]}):"
printf '  - %s\n' "${TABLES[@]}"
if [ "$INCLUDE_USERS" = false ]; then
  echo "  (tabel 'users' TIDAK ikut — pakai --include-users kalau ingin ikut ditruncate)"
fi
echo
echo "File model (.json/.pkl) yang akan dihapus:"
if [ -n "$MODEL_FILES" ]; then
  echo "$MODEL_FILES" | sed 's/^/  - /'
else
  echo "  (tidak ada — $MODELS_DIR kosong atau belum ada)"
fi
echo "  - $SCORING_LOG"
echo

if [ "$SKIP_CONFIRM" = false ]; then
  read -r -p "Lanjutkan? Tindakan ini TIDAK BISA dibatalkan. Ketik 'yes' untuk lanjut: " CONFIRM
  if [ "$CONFIRM" != "yes" ]; then
    echo "Dibatalkan — tidak ada yang diubah."
    exit 1
  fi
fi

echo
echo "[1/3] Truncate database..."
psql -v ON_ERROR_STOP=1 -c "TRUNCATE ${TABLE_LIST} RESTART IDENTITY CASCADE;"
echo "      Selesai — ${#TABLES[@]} tabel dikosongkan."

echo "[2/3] Hapus artifact model ML (.json, .pkl)..."
if [ -n "$MODEL_FILES" ]; then
  echo "$MODEL_FILES" | while IFS= read -r f; do
    rm -f -- "$f"
    echo "      - dihapus: $f"
  done
else
  echo "      Tidak ada file .json/.pkl untuk dihapus."
fi
echo "      Selesai."

echo "[3/3] Hapus scoring_log.csv..."
if [ -f "$SCORING_LOG" ]; then
  rm -v "$SCORING_LOG"
else
  echo "      $SCORING_LOG tidak ada, dilewati."
fi
echo "      Selesai."

echo
echo "=== Reset selesai. ==="
echo "Langkah berikutnya (lihat README.md root, bagian 'Seed data & model pertama'):"
echo "  cd faker && python generate-faker-realistic.py --reset && cd .."
echo "  # lalu latih model: klik Sync di UI, atau jalankan pipelines/train_*.py + daily_scoring.py"