import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from typing import Callable


def build_query_runner() -> Callable[[str], pd.DataFrame]:
    """
    Membuat fungsi runner query ke database.
    Prioritas 1: st.connection (Streamlit native)
    Prioritas 2: sqlalchemy engine (fallback jika st.connection gagal/tidak dikonfigurasi)
    """
    # Cara 1: Coba Native Streamlit Connection
    try:
        conn = st.connection("postgresql", type="sql")

        def _run_query_streamlit(sql: str) -> pd.DataFrame:
            return conn.query(sql)

        # Test koneksi ringan
        _ = _run_query_streamlit("SELECT 1 as ok;")
        return _run_query_streamlit
    except Exception:
        pass

    # Cara 2: Fallback menggunakan SQLAlchemy Engine
    db_url = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL", ""))
    if not db_url:
        st.error(
            "❌ Koneksi DB tidak dikonfigurasi. Pastikan 'connections.postgresql' "
            "ada di secrets.toml atau environment variable 'DATABASE_URL' diset."
        )
        st.stop()

    engine = create_engine(db_url, pool_pre_ping=True)

    def _run_query_engine(sql: str) -> pd.DataFrame:
        with engine.connect() as con:
            return pd.read_sql(text(sql), con)

    return _run_query_engine


def _clean_coord(series: pd.Series) -> pd.Series:
    """Ubah koma jadi titik lalu konversi ke numeric."""
    cleaned = series.astype(str).str.replace(',', '.', regex=False)
    return pd.to_numeric(cleaned, errors='coerce')


@st.cache_data(ttl=300)
def load_pts_full() -> pd.DataFrame:
    """Data lengkap profil_pts, dipakai oleh sebaran_pts.py"""
    run_query = build_query_runner()
    try:
        query = """
            SELECT
                id, kode_pts, nama, status_pt, singkatan, alamat,
                kota_kab, provinsi, kode_pos, latitude, longitude,
                no_telp, no_fax, email, website, created_at
            FROM public.profil_pts
        """
        df = run_query(query)
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            'kota_kab': 'kota',
            'provinsi': 'propinsi',
            'latitude': 'lat_raw',
            'longitude': 'lon_raw'
        })

        text_cols = [
            'kode_pts', 'nama', 'status_pt', 'singkatan', 'alamat',
            'kota', 'propinsi', 'kode_pos', 'no_telp', 'no_fax',
            'email', 'website'
        ]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("-").astype(str)

        df['lat'] = _clean_coord(df['lat_raw'])
        df['lon'] = _clean_coord(df['lon_raw'])
        df = df.dropna(subset=['lat', 'lon'])
        return df

    except Exception as e:
        st.error(f"Error saat mengambil data dari database: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_pts_minimal() -> pd.DataFrame:
    """Data ringkas profil_pts, dipakai oleh pts_dekat_rel.py"""
    run_query = build_query_runner()
    try:
        query = """
            SELECT
                kode_pts, nama, kota_kab, latitude, longitude
            FROM public.profil_pts
        """
        df = run_query(query)
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={
            'kode_pts': 'Kode PTS',
            'nama': 'Nama PTS',
            'kota_kab': 'Kota/Kab',
            'latitude': 'Latitude_raw',
            'longitude': 'Longitude_raw'
        })

        df['Latitude'] = _clean_coord(df['Latitude_raw'])
        df['Longitude'] = _clean_coord(df['Longitude_raw'])
        df = df.dropna(subset=['Latitude', 'Longitude'])
        return df

    except Exception as e:
        st.error(f"Error saat mengambil data dari database: {e}")
        return pd.DataFrame()
