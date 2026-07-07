import io
import pandas as pd
import streamlit as st
import pydeck as pdk

from db_utils import load_pts_full

# =========================
# 1. KONFIGURASI HALAMAN
# =========================
# st.set_page_config(
#    page_title="Peta Lokasi PTS",
#    page_icon="🎓",
#    layout="wide"
# )

st.title("🎓 Peta Persebaran Perguruan Tinggi Swasta")
st.markdown("Aplikasi ini menampilkan lokasi PTS yang diambil langsung dari **Database**.")

# =========================
# 2. LOAD DATA
# =========================
with st.spinner("Mengambil data dari Database..."):
    df_pts = load_pts_full()

# =========================
# 3. VISUALISASI UTAMA
# =========================
if not df_pts.empty:
    st.success(f"✅ Data berhasil dimuat: {len(df_pts)} kampus ditemukan.")

    # --- KONFIGURASI PETA ---
    view_state = pdk.ViewState(
        latitude=-7.30,
        longitude=110.00,
        zoom=6.8,
        pitch=0
    )

    # Layer 1: Titik (Scatter) - Merah
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_pts,
        get_position='[lon, lat]',
        get_color=[255, 0, 0, 200],
        get_radius=1000,
        radius_min_pixels=3,
        radius_max_pixels=10,
        pickable=True,
        auto_highlight=True
    )

    # Layer 2: Teks Nama - Biru
    text_layer = pdk.Layer(
        "TextLayer",
        data=df_pts,
        get_position='[lon, lat]',
        get_text="nama",
        get_size=12,
        get_color=[0, 0, 100],
        get_angle=0,
        text_anchor="middle",
        alignment_baseline="bottom",
        billboard=True
    )

    # Tooltip (Pop-up saat mouse hover)
    tooltip = {
        "html": """
            <b>{nama}</b><br/>
            <small>{alamat}</small><br/>
            {kota}, {propinsi}<br/>
            <i>{website}</i>
        """,
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "fontSize": "12px",
            "padding": "10px",
            "borderRadius": "5px",
            "border": "1px solid #ccc"
        }
    }

    # Render Peta
    st.pydeck_chart(pdk.Deck(
        map_style=None,
        initial_view_state=view_state,
        layers=[scatter_layer, text_layer],
        tooltip=tooltip
    ))

    # --- BAGIAN TABEL DAN DOWNLOAD ---
    with st.expander("Lihat Data Tabel", expanded=False):

        cols_display = [
            'id', 'kode_pts', 'nama', 'status_pt', 'singkatan',
            'alamat', 'kota', 'propinsi', 'kode_pos',
            'lat_raw', 'lon_raw', 'no_telp', 'no_fax',
            'email', 'website'
        ]

        column_aliases = {
            'id': 'No',
            'kode_pts': 'Kode PTS',
            'nama': 'Nama PTS',
            'status_pt': 'Status Keaktifan',
            'singkatan': 'Singkatan',
            'alamat': 'Alamat',
            'kota': 'Kota/Kab',
            'propinsi': 'Propinsi',
            'kode_pos': 'Kode Pos',
            'lat_raw': 'Latitude',
            'lon_raw': 'Longitude',
            'no_telp': 'No Telp',
            'no_fax': 'No Fax',
            'email': 'Email',
            'website': 'Website'
        }

        df_view = df_pts[cols_display].rename(columns=column_aliases)
        st.dataframe(df_view, hide_index=True)

        st.write("---")
        st.write("📥 **Unduh Data**")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_view.to_excel(writer, index=False, sheet_name='Data PTS')
            workbook = writer.book
            worksheet = writer.sheets['Data PTS']
            format_wrap = workbook.add_format({'text_wrap': True, 'valign': 'top'})
            worksheet.set_column('A:O', 20, format_wrap)

        st.download_button(
            label="📄 Download File Excel (.xlsx)",
            data=buffer,
            file_name="data_pts_lengkap.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.warning("Data tidak ditemukan atau tabel kosong.")
