import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Oldal beállítása - széles nézet a jobb elrendezéshez
st.set_page_config(page_title="Csírakert Pénzügy", layout="wide")

# --- 1. API és Google kapcsolatok ---
@st.cache_data(ttl=21600)
def get_exchange_rates():
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/HUF"
        response = requests.get(url).json()
        if response['result'] == 'success':
            rates = response['conversion_rates']
            return 1 / rates['RSD'], 1 / rates['EUR']
    except:
        return 3.0, 400.0

@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    return gspread.authorize(creds.with_scopes(scope))

def load_data(sheet_name):
    client = get_gspread_client()
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
    return pd.DataFrame(sheet.get_all_records()), sheet

# --- 2. Felhasználói felület ---
st.title("🌱 Csírakert Pénzügy")
rsd_ar, eur_ar = get_exchange_rates()
st.markdown("---")

mode = st.radio("Mód:", ["Adatrögzítés", "Kategóriák kezelése"], horizontal=True)

if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    with st.form("adatbevitel_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        date = c1.date_input("Dátum", datetime.now())
        megnev = c1.text_input("Megnevezés/Eszköz")
        ft = c2.number_input("Összeg (Ft)", min_value=0.0, step=10.0)
        dinar = c2.number_input("Összeg (Dinar)", min_value=0.0, step=10.0)
        
        kat_df, _ = load_data("Kategoriak")
        kategoria = st.selectbox("Kategória", kat_df['Nev'].tolist()) if menu == "Költség" else None
        
        if st.form_submit_button("Mentés a táblázatba"):
            _, sheet = load_data("Penzugy_Koltsegek" if menu == "Költség" else "Penzugy_Bevetelek")
            row = [str(date), megnev, kategoria, ft, dinar] if menu == "Költség" else [str(date), megnev, ft, dinar]
            sheet.append_row(row)
            st.rerun()

    st.markdown("---")
    st.header("📊 Kimutatás")
    
    try:
        df_k, _ = load_data("Penzugy_Koltsegek")
        df_b, _ = load_data("Penzugy_Bevetelek")
        
        df_k['Total_Ft'] = df_k['Összeg_Ft'] + (df_k['Összeg_Dinar'] * rsd_ar)
        total_bev_ft = df_b['Összeg_Ft'].sum() + (df_b['Összeg_Dinar'].sum() * rsd_ar)
        total_kolt_ft = df_k['Total_Ft'].sum()
        profit_ft = total_bev_ft - total_kolt_ft
        haszon_szazalek = (profit_ft / total_bev_ft * 100) if total_bev_ft > 0 else 0
        
        # Jól elrendezett oszlopok
        c1, c2, c3 = st.columns(3)
        c1.metric("Összbevétel", f"{total_bev_ft:,.0f} Ft")
        c2.metric("Összköltség", f"{total_kolt_ft:,.0f} Ft")
        c3.metric("Haszon", f"{profit_ft:,.0f} Ft", f"{haszon_szazalek:.1f}%")
        
        st.markdown("### 📈 Pénznemek")
        data = {
            "Pénznem": ["Forint (HUF)", "Dinár (RSD)", "Euró (EUR)"],
            "Bevétel": [f"{total_bev_ft:,.0f} Ft", f"{total_bev_ft/rsd_ar:,.0f} RSD", f"{total_bev_ft/eur_ar:,.2f} EUR"],
            "Költség": [f"{total_kolt_ft:,.0f} Ft", f"{total_kolt_ft/rsd_ar:,.0f} RSD", f"{total_kolt_ft/eur_ar:,.2f} EUR"],
            "Haszon": [f"{profit_ft:,.0f} Ft", f"{profit_ft/rsd_ar:,.0f} RSD", f"{profit_ft/eur_ar:,.2f} EUR"]
        }
        st.table(pd.DataFrame(data))
        
        st.markdown("### 📋 Részletes kiadások kategóriánként")
        # Csoportosítunk kategória ÉS megnevezés szerint, hogy ne keveredjen
        group_df = df_k.groupby(['Kategória', 'Megnevezés'])['Total_Ft'].sum().reset_index()
        
        for kat in group_df['Kategória'].unique():
            st.markdown(f"#### 📁 {kat}")
            sub_df = group_df[group_df['Kategória'] == kat]
            # Itt egy szép táblázatot adunk az eszközöknek
            st.table(sub_df[['Megnevezés', 'Total_Ft']].rename(columns={'Total_Ft': 'Összesen (Ft)'}))
            
    except:
        st.info("Még nincs elég adat a kimutatáshoz.")

else:
    st.header("Kategóriák kezelése")
    # ... (kategória hozzáadás/törlés kódja marad) ...
    kat_df, sheet = load_data("Kategoriak")
    new_kat = st.text_input("Új kategória:")
    if st.button("Hozzáadás"):
        sheet.append_row([new_kat])
        st.rerun()
