"""Write path bersama (TASK-P3): PostgreSQL COPY sebagai pengganti
`to_sql(method='multi', chunksize=1000)`. INSERT batch kecil terlalu lambat
untuk puluhan juta baris — prasyarat semua rung besar di ladder P4/P6.

Dipakai oleh pipelines/daily_scoring.py dan src/cbs_builder.py — diekstrak ke
sini (bukan didup di kedua tempat) karena keduanya butuh helper yang sama
persis.
"""
from __future__ import annotations

import io

import pandas as pd


def _collapse_whole_number_floats(df: pd.DataFrame) -> pd.DataFrame:
    """Kolom float yang SEMUA nilainya bilangan bulat ditulis tanpa ".0"
    (mis. "37" bukan "37.0"). Perlu karena parser tipe integer PostgreSQL
    (BIGINT dst.) menolak literal seperti "37.0" via COPY walau to_sql lama
    lolos (psycopg2 mengirim parameter lewat cast numeric->bigint yang lebih
    permisif daripada parser literal teks COPY). Nilai numeriknya TIDAK
    berubah sama sekali — "37" dan "37.0" identik secara numerik — jadi ini
    aman untuk kolom integer MAUPUN kolom fractional yang isinya kebetulan
    bulat semua (mis. delay_trend=0.0 di semua baris batch ini)."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype.kind == "f":
            non_null = out[col].dropna()
            if len(non_null) > 0 and (non_null == non_null.round()).all():
                out[col] = out[col].astype("Int64")
    return out


def copy_dataframe(conn, table_name: str, df: pd.DataFrame):
    """Tulis dataframe ke tabel via COPY kalau `conn` PostgreSQL, fallback ke
    `to_sql` kalau bukan (mis. SQLite di test) — COPY adalah fitur
    khusus-dialek, bukan bagian standar DB-API. `conn` adalah Connection
    dari `engine.begin()` (COPY ikut transaksi yang sama); `df.columns`
    HARUS persis nama kolom tabel tujuan."""
    if len(df) == 0:
        return
    if conn.dialect.name != "postgresql":
        df.to_sql(table_name, conn, if_exists="append", index=False)
        return

    df = _collapse_whole_number_floats(df)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cursor = conn.connection.cursor()
    columns = ", ".join(df.columns)
    cursor.copy_expert(
        f"COPY {table_name} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '')", buf
    )
