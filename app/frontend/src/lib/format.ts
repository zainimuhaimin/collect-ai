// Small shared display-formatting helpers for domains that receive raw numbers from
// the backend (unlike Customer/Contract/Dashboard, which follow this app's
// "pre-formatted string" convention — see docs/api/README.md). The restructuring
// domain mirrors `app/backend/schemas/restructuring.py` closely, which sends raw
// floats (e.g. `recommended_new_rate: 0.1376`), so the frontend formats them here.

export function formatRupiah(amount: number): string {
  return `Rp ${Math.round(amount).toLocaleString('id-ID')}`;
}

// `rate` is a decimal fraction per annum (0.1376 = 13.76% p.a.), matching the backend
// contract's `recommended_new_rate`/`interest_rate` shape.
export function formatPercentFromDecimal(rate: number, fractionDigits = 2): string {
  return `${(rate * 100).toFixed(fractionDigits)}%`;
}

export function formatPercent(value: number, fractionDigits = 2): string {
  return `${value.toFixed(fractionDigits)}%`;
}

const MONTH_NAMES_ID = [
  'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

// Parses the leading "YYYY-MM-DD" (and optional "THH:MM"/" HH:MM") digits
// directly out of the string — deliberately NOT `new Date(value)`, which
// interprets date-only strings as UTC midnight and can silently shift the
// displayed date by a day depending on the viewer's local timezone. Any
// trailing offset/fractional seconds (e.g. "+07:00", ".462805") are ignored;
// the wall-clock digits the backend sent are shown as-is.
function parseIsoParts(value: string) {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!match) return null;
  const [, y, m, d, hh, mm] = match;
  return { y: Number(y), m: Number(m), d: Number(d), hh: hh ? Number(hh) : null, mm: mm ? Number(mm) : null };
}

// Date-only fields (due_date, maturity_date, scoring_date, generated_date, ...) — "29 Juli 2026".
export function formatDateHuman(value: string | null | undefined): string {
  if (!value) return '—';
  const parts = parseIsoParts(value);
  if (!parts) return value;
  return `${String(parts.d).padStart(2, '0')} ${MONTH_NAMES_ID[parts.m - 1]} ${parts.y}`;
}

// Full timestamps (operational log, sync started/finished/last-scored, ...) — "29 Juli 2026 pukul 16:26".
export function formatDateTimeHuman(value: string | null | undefined): string {
  if (!value) return '—';
  const parts = parseIsoParts(value);
  if (!parts) return value;
  const datePart = formatDateHuman(value);
  if (parts.hh === null || parts.mm === null) return datePart;
  return `${datePart} pukul ${String(parts.hh).padStart(2, '0')}:${String(parts.mm).padStart(2, '0')}`;
}
