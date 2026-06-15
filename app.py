import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Csírakert - Profit Tracker", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    # Közvetlen hozzáférés az ID alapján
    sheet = client.open_by_key("1ekoKF2c9EZF0SvBRjsLb9vycud5djMXSBbPrfnha2Hw")
    col_sheet = sheet.worksheet("Penzugy_Koltsegek")
    rev_sheet = sheet.worksheet("Penzugy_Bevetelek")
except Exception as e:
    st.error(f"Hiba történt a kapcsolódásnál: {e}")
    st.stop()

def load_data(worksheet):
    try:
        data = worksheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=["Dátum", "Összeg"])
    except Exception as e:
        st.error(f"Hiba az adatok betöltésekor: {e}")
        return pd.DataFrame()

df_costs = load_data(col_sheet)
df_revenues = load_data(rev_sheet)

st.title("🌱 Csírakert - Profit és Költség Tracker")

# Sidebar
option = st.sidebar.radio("Mit rögzítesz?", ["📉 Új Költség", "📈 Új Bevétel"])
current_date = datetime.now().strftime("%Y-%m-%d")

if option == "📉 Új Költség":
    cat = st.sidebar.text_input("Kategória:")
    val = st.sidebar.number_input("Összeg:", min_value=0.0)
    if st.sidebar.button("Mentés"):
        col_sheet.append_row([current_date, cat, val, ""])
        st.rerun()
else:
    val = st.sidebar.number_input("Bevétel összege:", min_value=0.0)
    if st.sidebar.button("Mentés"):
        rev_sheet.append_row([current_date, val, ""])
        st.rerun()

# Összegzés
col1, col2 = st.columns(2)
costs_sum = df_costs['Összeg'].sum() if 'Összeg' in df_costs.columns else 0
revenues_sum = df_revenues['Összeg'].sum() if 'Összeg' in df_revenues.columns else 0

col1.metric("Összes Költség", f"{costs_sum:,.2f} Ft")
col2.metric("Összes Bevétel", f"{revenues_sum:,.2f} Ft")
