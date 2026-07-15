"""
Konfigurasi global untuk FTE Calculator.
"""

# ID Google Spreadsheet (BACKEND) - sumber data referensi
SPREADSHEET_ID = "1YRvXt0AE-dVBVwRvLtsb57Qz8DYd9YbVQlVbRD31C7I"
BACKEND_SHEET_NAME = "BACKEND"
UNIT_SHEET_NAME = "Sheet9"           # data input Unit per site (v2, auto-lookup)
STAFF_SHEET_NAME = "Hasil Staff"     # data FTE Staff (Foreman/SPV/Planner) per site (v2)

# Password sederhana untuk membuka mode edit tabel unit (edit hanya sesi ini, tidak
# tersimpan ke Google Sheets, dan akan kembali normal jika halaman di-refresh).
UNIT_EDIT_PASSWORD = "DHRising"

# Endpoint export CSV publik (spreadsheet harus di-share minimal "Anyone with link - Viewer")
def gsheet_csv_url(sheet_name: str, spreadsheet_id: str = SPREADSHEET_ID) -> str:
    from urllib.parse import quote
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    )

# Konstanta rumus (sesuai sheet "Final Calculation")
BASE_MECHANIC_HOURS = 12       # basis jam kerja mekanik/hari sebelum dikurangi Lost Time & travel
HOURS_PER_DAY = 24             # basis 24 jam untuk breakdown hours
TRAVEL_DIVISOR = 40            # pembagi Jarak (KM) -> jam perjalanan (D4/40)

# Cost rate per FTE (Rp) - ditetapkan eksplisit oleh user, bukan dari BACKEND
COST_RATE = {
    "M1": 10_000_000,
    "M2": 8_500_000,
    "M3": 6_500_000,
}

ROLES = ["Mechanic", "Electric", "Welder"]
MONTH_COLS = ["M1", "M2", "M3"]

# Cache TTL untuk data BACKEND (detik)
CACHE_TTL_SECONDS = 600
