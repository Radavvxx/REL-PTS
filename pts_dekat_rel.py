import io
import pandas as pd
import streamlit as st
import requests
import geopandas as gpd
from shapely.geometry import LineString
import folium
from streamlit_folium import st_folium

from db_utils import load_pts_minimal

# =========================
# 1. KONFIGURASI HALAMAN
# =========================
# st.set_page_config(page_title="Analisis Jarak PTS ke Rel Kereta", layout="wide", page_icon="🚂")

st.title("🚂 Analisis Jarak Perguruan Tinggi ke Rel Kereta Api (Pulau Jawa)")
st.write(
    "Aplikasi ini menghitung jarak terdekat dari setiap Perguruan Tinggi Swasta (PTS) "
    "ke jalur rel kereta api di Pulau Jawa berdasarkan radius yang Anda tentukan. "
    "Data PTS diambil dari Database, data rel kereta diambil dari OpenStreetMap."
)

# =========================
# 2. FUNGSI AMBIL DATA REL KERETA (dengan fallback mirror)
# =========================
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

OVERPASS_QUERY = """
[out:json][timeout:60];
(
  way["railway"="rail"](-8.8, 105.0, -5.8, 115.0);
  way["railway"="narrow_gauge"](-8.8, 105.0, -5.8, 115.0);
);
out geom;
"""


@st.cache_data(ttl=60 * 60 * 24, show_spinner="Mengunduh data rel kereta api dari OpenStreetMap...")
def get_railway_data():
    """
    Mengambil data rel kereta dari Overpass API.
    Mencoba beberapa mirror server secara berurutan agar tidak mudah gagal.
    Jika semua mirror gagal, mengembalikan GeoDataFrame kosong (tidak crash).
    """
    headers = {"User-Agent": "LPMI-UNIBANG-App/1.0 (contact: lpmi@unibang.ac.id)"}
    last_error = None
    data = None

    for url in OVERPASS_MIRRORS:
        try:
            response = requests.post(
                url,
                data={"data": OVERPASS_QUERY},
                headers=headers,
                timeout=90,
            )
            response.raise_for_status()  # error kalau status bukan 200

            # Pastikan responsenya benar-benar JSON sebelum di-parse
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise ValueError(f"Response bukan JSON (Content-Type: {content_type})")

            data = response.json()
            break  # berhasil, tidak perlu coba mirror lain
        except Exception as e:
            last_error = e
            data = None
            continue

    if data is None:
        st.warning(
            f"⚠️ Tidak dapat mengambil data rel kereta dari server Overpass saat ini "
            f"(semua mirror gagal). Error terakhir: `{last_error}`. "
            "Peta tetap ditampilkan tanpa jalur rel kereta."
        )
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    lines = []
    for element in data.get("elements", []):
        if element.get("type") == "way" and "geometry" in element:
            coords = [(node["lon"], node["lat"]) for node in element["geometry"]]
            if len(coords) >= 2:
                lines.append(LineString(coords))

    return gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")


# =========================
# 3. PENGATURAN PENGGUNA
# =========================
with st.sidebar:
    st.header("⚙️ Pengaturan")
    st.info("Data dimuat otomatis dari Database.")
    radius_km = st.slider("Batas Jarak ke Rel (Kilometer)", min_value=0.5, max_value=10.0, value=3.0, step=0.5)
    radius_m = radius_km * 1000

# =========================
# 4. LOGIKA UTAMA & TAMPILAN
# =========================
with st.spinner("Mengambil data PTS dari Database..."):
    df = load_pts_minimal()

if df.empty:
    st.warning("⚠️ Data PTS tidak ditemukan di dalam Database atau tidak ada koordinat valid.")
    st.stop()

st.success(f"✅ Berhasil memuat {len(df)} titik PTS dari Database.")

railways_gdf = get_railway_data()

if railways_gdf.empty:
    st.info("ℹ️ Data rel kereta api sedang tidak tersedia, sehingga jarak tidak dapat dihitung saat ini. Coba muat ulang beberapa saat lagi.")
    st.stop()

st.info(f"🚂 Berhasil memuat {len(railways_gdf)} segmen rel kereta api dari OpenStreetMap.")

with st.spinner("Menghitung jarak spasial ke rel terdekat..."):
    pts_gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
        crs="EPSG:4326"
    )

    rail_3857 = railways_gdf.to_crs("EPSG:3857")
    pts_3857 = pts_gdf.to_crs("EPSG:3857")

    pts_gdf["Jarak_ke_Rel_Meter"] = pts_3857.geometry.apply(lambda x: rail_3857.distance(x).min())

    hasil_filter = pts_gdf[pts_gdf["Jarak_ke_Rel_Meter"] <= radius_m].copy()
    hasil_filter["Jarak_ke_Rel_Meter"] = hasil_filter["Jarak_ke_Rel_Meter"].round(2)

# --- TAMPILAN HASIL ---
st.subheader(f"📑 Hasil Analisis (Terdapat {len(hasil_filter)} PTS dalam radius {radius_km} km)")

kolom_tampil = ["Kode PTS", "Nama PTS", "Kota/Kab", "Jarak_ke_Rel_Meter", "Latitude", "Longitude"]
kolom_tampil = [col for col in kolom_tampil if col in hasil_filter.columns]

st.dataframe(hasil_filter[kolom_tampil].sort_values(by="Jarak_ke_Rel_Meter"), use_container_width=True)

# --- TOMBOL DOWNLOAD EXCEL ---
buffer = io.BytesIO()
df_download = hasil_filter.drop(columns=["geometry", "Latitude_raw", "Longitude_raw"], errors="ignore")
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_download.to_excel(writer, index=False, sheet_name="Data PTS Filter")

st.download_button(
    label="📥 Unduh Hasil Filter (Excel)",
    data=buffer.getvalue(),
    file_name=f"pts_dekat_rel_{radius_km}km.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --- PETA INTERAKTIF ---
st.subheader("🗺️ Peta Lokasi PTS dan Rel Kereta Api")

m = folium.Map(location=[-7.25, 110.0], zoom_start=7, tiles="CartoDB positron")

folium.GeoJson(
    railways_gdf,
    name="Jalur Kereta Api",
    style_function=lambda x: {"color": "red", "weight": 2, "opacity": 0.7}
).add_to(m)

for idx, row in hasil_filter.iterrows():
    popup_text = f"<b>{row.get('Nama PTS', 'Tidak diketahui')}</b><br>Jarak: {row['Jarak_ke_Rel_Meter']} m"
    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=5,
        popup=folium.Popup(popup_text, max_width=300),
        color="blue",
        fill=True,
        fill_color="blue",
        fill_opacity=0.7
    ).add_to(m)

st_folium(m, width=1200, height=600, returned_objects=[])
