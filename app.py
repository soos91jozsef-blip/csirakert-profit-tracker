import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Csírakert - Profit Tracker", layout="wide")

# --- GOOGLE TÁBLÁZAT BEKÖTÉSE ---
# Biztonságos hitelesítés (Streamlit Secrets-ből fogja olvasni a felhőben, helyileg pedig a beépített módon)
@st.cache_resource
def get_sheets_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # A Streamlit secrets-ből olvassuk be a hitelesítési adatokat
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    # Pontosan a ti táblázatotok neve
    sheet = client.open("Csírakert_Adatbazis")
    col_sheet = sheet.worksheet("Penzugy_Koltsegek")
    rev_sheet = sheet.worksheet("Penzugy_Bevetelek")
except Exception as e:
    st.error("Nem sikerült kapcsolódni a Google Táblázathoz. Ellenőrizd a beállításokat!")
    st.stop()

# --- ADATOK BETÖLTÉSE ---
def load_data(worksheet):
    data = worksheet.get_all_records()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)

df_costs = load_data(col_sheet)
df_revenues = load_data(rev_sheet)

# --- ALAPÉRTELMEZETT KATEGÓRIÁK ---
# Ezeket kérted, és bármikor bővítheti a feleséged
default_categories = [
    "Magok ára",
    "0.7L-es csíráztató tartályok",
    "3.25L-es csíráztató tartályok",
    "Üvegek ára",
    "500cc-s dobozkák",
    "Matricák ára",
    "Centrifuga ára",
    "Egyéb eszközök"
]

# Ha már vannak egyedi kategóriák a táblázatban, adjuk hozzá azokat is a listához
if not df_costs.empty and "Kategória" in df_costs.columns:
    existing_categories = df_costs["Kategória"].dropna().unique().tolist()
    all_categories = sorted(list(set(default_categories + existing_categories)))
else:
    all_categories = default_categories

# --- CÍMSOR ---
st.title("🌱 Csírakert - Profit és Költség Tracker")
st.markdown("---")

# --- OLDALSÁV: ADATBEVITEL ---
st.sidebar.header("📊 Adatok Rögzítése")

# Űrlap választó
option = st.sidebar.radio("Mit szeretnél rögzíteni?", ["📉 Új Költség", "📈 Új Bevétel"])

current_date = datetime.now().strftime("%Y-%m-%d")

if option == "📉 Új Költség":
    st.sidebar.subheader("Költség hozzáadása")
    
    # Kategória választása vagy új hozzáadása
    cat_type = st.sidebar.radio("Kategória típusa:", ["Meglévő", "➕ Teljesen új kategória"])
    
    if cat_type == "Meglévő":
        category = st.sidebar.selectbox("Költség kategória:", all_categories)
    else:
        category = st.sidebar.text_input("Új kategória neve (pl. Föld, Öntözés):")
        
    cost_amount = st.sidebar.number_input("Összeg (RSD / HUF):", min_value=0.0, step=10.0, format="%.2f")
    cost_notes = st.sidebar.text_input("Megjegyzés (Költséghez):", placeholder="pl. Bolt neve, tétel darabszáma")
    
    if st.sidebar.button("Költség Mentése a Táblázatba"):
        if category and cost_amount > 0:
            # Új sor beszúrása a Google Táblázatba: Dátum, Kategória, Összeg, Megjegyzés
            col_sheet.append_row([current_date, category, cost_amount, cost_notes])
            st.sidebar.success(f"🎉 '{category}' sikeresen elmentve!")
            st.rerun()
        else:
            st.sidebar.error("Kérlek adj meg érvényes kategóriát és összeget!")

else:
    st.sidebar.subheader("Bevétel rögzítése")
    rev_amount = st.sidebar.number_input("Bevétel összege (RSD / HUF):", min_value=0.0, step=100.0, format="%.2f")
    rev_notes = st.sidebar.text_input("Megjegyzés (Bevételhez):", placeholder="pl. Heti piac, Éttermi kiszállítás")
    
    if st.sidebar.button("Bevétel Mentése a Táblázatba"):
        if rev_amount > 0:
            # Új sor beszúrása a Google Táblázatba: Dátum, Összeg, Megjegyzés
            rev_sheet.append_row([current_date, rev_amount, rev_notes])
            st.sidebar.success(f"💰 {rev_amount} értékű bevétel rögzítve!")
            st.rerun()
        else:
            st.sidebar.error("Az összegnek nagyobbnak kell lennie mint 0!")


# --- FŐOLDAL: ÖSSZEGZÉS (A 3 OSZLOP) ---

# Számítások a táblázat adatai alapján
total_costs = df_costs["Összeg"].sum() if not df_costs.empty else 0.0
total_revenues = df_revenues["Összeg"].sum() if not df_revenues.empty else 0.0
net_profit = total_revenues - total_costs

col1, col2, col3 = st.columns(3)

with col1:
    st.error("📉 Összes Kiadás")
    st.metric(label="Költségek", value=f"{total_costs:,.2f}")

with col2:
    st.success("📈 Összes Bevétel")
    st.metric(label="Bevételek", value=f"{total_revenues:,.2f}")

with col3:
    if net_profit >= 0:
        st.info("💰 Tiszta Haszon")
    else:
        st.warning("⚠️ Jelenlegi veszteség")
    st.metric(label="Tiszta Profit", value=f"{net_profit:,.2f}")

st.markdown("---")

# --- RÉSZLETES TÁBLÁZATOK ---
tab1, tab2 = st.tabs(["📋 Költségek Lebontása", "💵 Bevételek Listája"])

with tab1:
    st.subheader("Rögzített kiadások")
    if not df_costs.empty:
        st.dataframe(df_costs.sort_index(ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Még nincs rögzített költség a táblázatban.")

with tab2:
    st.subheader("Rögzített bevételek")
    if not df_revenues.empty:
        st.dataframe(df_revenues.sort_index(ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Még nincs rögzített bevétel a táblázatban.")