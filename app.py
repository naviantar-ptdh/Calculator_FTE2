# app.py (v2)
"""
FTE Calculator v2 — PT Dharma Henwa
Perubahan utama dari v1:
 - Data unit TIDAK diinput manual — otomatis di-lookup dari sheet "Sheet9" berdasarkan Site.
 - Jarak (km) otomatis di-lookup dari BACKEND (seksi "Jarak"), tidak ada input manual.
 - Site & Competency Factor + tombol "Hitung FTE" dipindah ke sidebar.
 - Hasil berupa SUMMARY saja: Mechanic dikelompokkan per Category (BACKEND "Clasification":
   Digger/Hauler/Auxilary Track/Auxilary Wheel/Support & Facility/dst — kategori kosong disembunyikan),
   Welder & Electrician langsung TOTAL keseluruhan (tidak per kategori).
 - Tambahan perhitungan Foreman + Supervisor (50% round) per kategori Operational, dan FTE Planner
   (posisi non-mekanik), berdasarkan sheet "Hasil Staff".
 - Tombol "Tampilkan Detail" untuk melihat rincian per-unit (seperti v1) + rincian Foreman/SPV/Planner.
 - Tabel unit read-only secara default; mode edit (sesi ini saja, tidak tersimpan ke Google Sheets)
   dibuka dengan password kecil di pojok kanan atas.
"""
import base64
import math
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

from calculator import (
    CalculationError,
    compute_site_summary,
    compute_staff_fte,
)
from config import MONTH_COLS, UNIT_EDIT_PASSWORD
from data_loader import (
    BackendDataError,
    UnitRow,
    load_backend_data,
    load_staff_data,
    load_unit_data,
)

st.set_page_config(
    page_title="FTE Calculator v2",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGE_SIZE = 10


# -----------------------------------------------------------------
# Asset loading (logo & placeholder gambar1.png) — sama pola dgn v1
# -----------------------------------------------------------------
def _load_data_uri(candidates) -> str | None:
    here = Path(__file__).resolve().parent
    for candidate in candidates:
        p = here / candidate
        if p.is_file():
            try:
                b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                ext = p.suffix.lower().lstrip(".") or "png"
                mime = "jpeg" if ext in ("jpg", "jpeg") else ext
                return f"data:image/{mime};base64,{b64}"
            except Exception:
                pass
    return None


_LOGO_DATA_URI = _load_data_uri(["logo_putih.png", "assets/logo_putih.png", "static/logo_putih.png"])
_LOGO_FALLBACK_URL = "https://raw.githubusercontent.com/naviantar-ptdh/202605-centralized/main/logo_putih.png"
LOGO_SRC = _LOGO_DATA_URI or _LOGO_FALLBACK_URL

# Placeholder untuk area hasil sebelum tombol "Hitung FTE" ditekan.
# TODO(user): taruh file "gambar1.png" di folder yang sama dengan app.py untuk mengganti placeholder ini.
_PLACEHOLDER_DATA_URI = _load_data_uri(["gambar1.png", "assets/gambar1.png", "static/gambar1.png"])

CSS = """
<style>
.nav { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
.nav img { height:28px; }
.section-label { font-weight:700; color:#6b7280; margin-top:18px; margin-bottom:6px; font-size:12px; text-transform:uppercase; }
.result-card { background:#fff; padding:12px; border-radius:8px; border:1px solid #eee; margin-bottom:12px; }
.placeholder-box {
    border: 2px dashed #d1d5db; border-radius: 12px; padding: 48px 24px;
    text-align: center; color: #9ca3af; margin-top: 12px;
}
.edit-lock-wrap { display:flex; justify-content:flex-end; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    f'<div class="nav"><img src="{LOGO_SRC}" alt="logo" onerror="this.style.display=\'none\'"/>'
    f'<div><strong>FTE Calculator v2</strong><div style="font-size:12px;color:#6b7280">PT Dharma Henwa</div></div></div>',
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------
# Cached loaders
# -----------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="Mengambil data referensi dari BACKEND...")
def get_backend():
    return load_backend_data()


@st.cache_data(ttl=600, show_spinner="Mengambil data Unit per Site...")
def get_units():
    return load_unit_data()


@st.cache_data(ttl=600, show_spinner="Mengambil data Hasil Staff...")
def get_staff():
    return load_staff_data()


# -----------------------------------------------------------------
# Formatting helpers
# -----------------------------------------------------------------
def fmt(x) -> str:
    if x is None:
        return "-"
    return f"{x:,.0f}".replace(",", ".")


def units_to_df(rows: List[UnitRow]) -> pd.DataFrame:
    return pd.DataFrame([
        {"Category": r.category, "Jenis Unit": r.jenis_unit, "Jumlah Unit": r.jumlah_unit, "PA": r.pa}
        for r in rows
    ])


def df_to_units(df: pd.DataFrame) -> List[UnitRow]:
    rows = []
    for _, r in df.iterrows():
        try:
            rows.append(UnitRow(
                category=str(r["Category"]),
                jenis_unit=str(r["Jenis Unit"]),
                jumlah_unit=float(r["Jumlah Unit"]),
                pa=float(r["PA"]),
            ))
        except Exception:
            continue
    return rows


def render_mechanic_by_category(mechanic_by_category: dict):
    if not mechanic_by_category:
        st.info("Tidak ada data Mechanic untuk Site ini.")
        return
    rows = []
    for cat, v in mechanic_by_category.items():
        rows.append({"Kategori": cat, "M1": fmt(v["M1"]), "M2": fmt(v["M2"]), "M3": fmt(v["M3"]), "Total": fmt(v["Tot"])})
    st.dataframe(pd.DataFrame(rows).set_index("Kategori"), width="stretch")


def render_role_total(label: str, total: dict):
    st.markdown(f"**{label}**")
    rows = [{
        "M1": fmt(total["M1"]),
        "M2": fmt(total["M2"]),
        "M3": "-",
        "Total": fmt(total["Tot"]),
    }]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_operational(operational: List[dict]):
    if not operational:
        st.info("Data Foreman/Supervisor belum tersedia untuk Site ini (data 'Hasil Staff' belum lengkap).")
        return
    rows = [{
        "Posisi": r["posisi"],
        "Jumlah Mekanik (M1)": fmt(r["jumlah_mekanik"]),
        "Foreman": fmt(r["foreman"]),
        "Supervisor": fmt(r["supervisor"]),
    } for r in operational]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_planner(planner: List[dict]):
    if not planner:
        st.info("Data FTE Planner belum tersedia untuk Site ini.")
        return
    rows = [{"Posisi": r["posisi"], "FTE": fmt(r["fte"])} for r in planner]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_detail(summary: dict, staff_res: dict):
    st.markdown('<div class="section-label">Detail Per-Unit (belum dibulatkan)</div>', unsafe_allow_html=True)
    rows = []
    for d in summary["detail_rows"]:
        raw = d["raw"]
        rows.append({
            "Category": d["category"],
            "Jenis Unit": d["jenis_unit"],
            "Jumlah Unit": d["jumlah_unit"],
            "PA": d["pa"],
            "Mech M1": round(raw["Mechanic"]["M1"], 3),
            "Mech M2": round(raw["Mechanic"]["M2"], 3),
            "Mech M3": round(raw["Mechanic"]["M3"], 3),
            "Weld M1": round(raw["Welder"]["M1"], 3),
            "Weld M2": round(raw["Welder"]["M2"], 3),
            "Elec M1": round(raw["Electric"]["M1"], 3),
            "Elec M2": round(raw["Electric"]["M2"], 3),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Tidak ada baris unit yang berhasil dihitung.")

    if summary["skipped_units"]:
        with st.expander(f"⚠️ {len(summary['skipped_units'])} baris unit dilewati (Sub Category tidak dikenali BACKEND)"):
            sk_df = pd.DataFrame(summary["skipped_units"], columns=["Category", "Jenis Unit", "Alasan"])
            st.dataframe(sk_df, width="stretch", hide_index=True)

    st.markdown('<div class="section-label">Detail Foreman / Supervisor</div>', unsafe_allow_html=True)
    render_operational(staff_res["operational"])
    st.markdown('<div class="section-label">Detail Planner</div>', unsafe_allow_html=True)
    render_planner(staff_res["planner"])


def render_placeholder():
    if _PLACEHOLDER_DATA_URI:
        st.image(_PLACEHOLDER_DATA_URI, width="stretch")
    else:
        st.markdown(
            '<div class="placeholder-box">🧮<br><br>Pilih <b>Site</b> &amp; <b>Competency Factor</b> di sidebar, '
            'lalu klik <b>Hitung FTE</b> untuk melihat hasil.<br>'
            '<span style="font-size:12px">(letakkan file gambar1.png di folder app ini untuk mengganti placeholder ini)</span></div>',
            unsafe_allow_html=True,
        )


def main():
    # ---------------- Sidebar ----------------
    with st.sidebar:
        st.header("⚙️ General Parameters")

    try:
        backend = get_backend()
    except BackendDataError as exc:
        st.error("Gagal memuat data BACKEND: " + str(exc))
        return

    sites = backend.sites or []

    with st.sidebar:
        site = st.selectbox("Site", options=sites if sites else ["-"])
        competency_factor = st.slider("Competency Factor Mechanic", min_value=0.1, max_value=1.0, value=0.6, step=0.01)
        st.caption("Jarak & data unit di-lookup otomatis berdasarkan Site yang dipilih.")
        compute_clicked = st.button("🧮 Hitung FTE", type="primary", width="stretch")
        st.markdown("---")
        if st.button("🔄 Clear Cache & Reload Semua Data"):
            get_backend.clear()
            get_units.clear()
            get_staff.clear()
            st.rerun()
        with st.expander("🔍 Debug: Nilai BACKEND yang terbaca"):
            st.write("**Proporsi RACI**", backend.raci)
            st.write("**Split Ratio Mechanic [M1,M2,M3]**", backend.split_mechanic)
            st.write("**Split Ratio Welder [M1,M2]**", backend.split_welder)
            st.write("**Split Ratio Electrician [M1,M2]**", backend.split_electrician)
            st.write("**Ratio Shift per Site**", backend.ratio_shift)
            st.write("**Lost Time per Site**", backend.lost_time)
            st.write("**Jarak per Site (v2)**", backend.jarak)
            st.write("**Urutan Kategori Clasification (v2)**", backend.classification_order)

    # ---------------- Reset state saat Site berubah ----------------
    if st.session_state.get("current_site") != site:
        try:
            units_all = get_units()
        except BackendDataError as exc:
            st.error("Gagal memuat data Unit (Sheet9): " + str(exc))
            return
        st.session_state.current_site = site
        rows = units_all.get(site, [])
        st.session_state.working_units_df = units_to_df(rows)
        st.session_state.page_num = 0
        st.session_state.calc_result = None
        st.session_state.edit_unlocked = False

    # Guard defensif: kalau karena alasan apa pun working_units_df belum ada
    # (mis. rerun aneh / cache lama), jangan crash — tampilkan pesan & hentikan.
    if "working_units_df" not in st.session_state:
        st.warning("Data unit belum termuat. Silakan pilih Site lagi atau klik 'Clear Cache & Reload Semua Data'.")
        return

    # ---------------- Header unit + kunci password kecil ----------------
    col_title, col_lock = st.columns([6, 1])
    with col_title:
        st.markdown('<div class="section-label">Data Unit (otomatis, dari Sheet9)</div>', unsafe_allow_html=True)
    with col_lock:
        st.markdown('<div class="edit-lock-wrap">', unsafe_allow_html=True)
        with st.popover("🔒 Edit"):
            if st.session_state.get("edit_unlocked"):
                st.success("Mode edit aktif untuk sesi ini.")
                st.caption("Perubahan TIDAK tersimpan ke spreadsheet & akan kembali normal jika halaman di-refresh.")
                if st.button("Kunci kembali"):
                    st.session_state.edit_unlocked = False
                    st.rerun()
                if st.button("Reset ke data asli"):
                    units_all = get_units()
                    st.session_state.working_units_df = units_to_df(units_all.get(site, []))
                    st.rerun()
            else:
                pwd = st.text_input("Password edit", type="password", key="edit_pwd_input")
                if st.button("Buka"):
                    if pwd == UNIT_EDIT_PASSWORD:
                        st.session_state.edit_unlocked = True
                        st.rerun()
                    else:
                        st.error("Password salah.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- Tabel unit (paginated) ----------------
    df = st.session_state.working_units_df
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / PAGE_SIZE))
    st.session_state.page_num = min(st.session_state.get("page_num", 0), total_pages - 1)
    start = st.session_state.page_num * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = df.iloc[start:end].reset_index(drop=True)

    st.caption(f"Site **{site}** — {total_rows} baris unit. Halaman {st.session_state.page_num + 1} dari {total_pages}.")

    if st.session_state.get("edit_unlocked"):
        edited_page = st.data_editor(
            page_df,
            num_rows="fixed",
            width="stretch",
            key=f"editor_{site}_{st.session_state.page_num}",
            column_config={
                "Jumlah Unit": st.column_config.NumberColumn("Jumlah Unit", min_value=0, step=1),
                "PA": st.column_config.NumberColumn("PA", min_value=1, max_value=100, step=1),
            },
        )
        df.iloc[start:end] = edited_page.values
        st.session_state.working_units_df = df
    else:
        st.dataframe(page_df, width="stretch", hide_index=True)

    nav1, nav2, nav3 = st.columns([1, 1, 6])
    with nav1:
        if st.button("⬅️ Sebelumnya", disabled=st.session_state.page_num <= 0):
            st.session_state.page_num -= 1
            st.rerun()
    with nav2:
        if st.button("Berikutnya ➡️", disabled=st.session_state.page_num >= total_pages - 1):
            st.session_state.page_num += 1
            st.rerun()

    # ---------------- Hitung ----------------
    if compute_clicked:
        try:
            unit_rows = df_to_units(st.session_state.working_units_df)
            summary = compute_site_summary(site, unit_rows, backend, competency_factor)
            staff_rows = get_staff()
            staff_res = compute_staff_fte(
                site,
                summary["mechanic_by_category"],
                summary["welder_total"],
                summary["electric_total"],
                staff_rows,
            )
            st.session_state.calc_result = {"summary": summary, "staff": staff_res}
        except CalculationError as exc:
            st.error(f"Gagal menghitung: {exc}")
            st.session_state.calc_result = None
        except BackendDataError as exc:
            st.error(f"Gagal memuat data Hasil Staff: {exc}")
            st.session_state.calc_result = None

    # ---------------- Hasil ----------------
    st.markdown('<div class="section-label">Summary</div>', unsafe_allow_html=True)
    result = st.session_state.get("calc_result")
    if not result:
        render_placeholder()
        return

    summary = result["summary"]
    staff_res = result["staff"]

    st.caption(f"Jarak (auto-lookup): {summary['jarak_km']:.2f} km — Competency Factor: {competency_factor:.2f}")

    st.markdown("**Mechanic per Kategori**")
    render_mechanic_by_category(summary["mechanic_by_category"])

    c1, c2 = st.columns(2)
    with c1:
        render_role_total("Welder (Total)", summary["welder_total"])
    with c2:
        render_role_total("Electrician (Total)", summary["electric_total"])

    st.markdown('<div class="section-label">Foreman &amp; Supervisor</div>', unsafe_allow_html=True)
    render_operational(staff_res["operational"])

    st.markdown('<div class="section-label">FTE Planner</div>', unsafe_allow_html=True)
    render_planner(staff_res["planner"])

    st.markdown("---")
    show_detail = st.toggle("Tampilkan Detail", value=st.session_state.get("show_detail", False))
    st.session_state.show_detail = show_detail
    if show_detail:
        render_detail(summary, staff_res)


if __name__ == "__main__":
    main()
