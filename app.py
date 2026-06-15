import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Csírakert - Profit Tracker", layout="wide")

@st.cache_resource
def get_sheets_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

try:
    client = get_sheets_client()
    sheet = client.open("Csírakert_Adatbazis")
    col_sheet = sheet.worksheet("Penzugy_Koltsegek")
    rev_sheet = sheet.worksheet("Penzugy_Bevetelek")
except Exception as e:
    st.error("Nem sikerült kapcsolódni a Google Táblázathoz. Ellenőrizd a beállításokat!")
    st.stop()

def load_data(worksheet):
    data = worksheet.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

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
col1.metric("Költségek", f"{df_costs['Összeg'].sum() if not df_costs.empty else 0:,.2f}")
col2.metric("Bevételek", f"{df_revenues['Összeg'].sum() if not df_revenues.empty else 0:,.2f}")
