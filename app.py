import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Oldal beállítások ---
st.set_page_config(page_title="Csírakert Pénzügy", layout="wide")

# --- Funkciók ---
@st.cache_data(ttl=21600)
def get_exchange_rates():
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/HUF"
        response = requests.get(url).json()
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

# --- UI Felület ---
st.title("🌱 Csírakert Pénzügy")
st.markdown("---")

# Árfolyamok lekérése
rsd_ar, eur_ar = get_exchange_rates()

mode = st.radio("Mód:", ["Adatrögzítés", "Kategóriák kezelése"], horizontal=True)

if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    
    with st.form("adatbevitel_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Dátum", datetime.now())
            megnev = st.text_input("Megnevezés/Eszköz")
        with col2:
            ft = st.number_input("Összeg (Ft)", min_value=0.0, step=10.0)
            dinar = st.number_input("Összeg (Dinár)", min_value=0.0, step=10.0)
        
        kat_df, _ = load_data("Kategoriak")
        kategoria = st.selectbox("Kategória", kat_df['Nev'].tolist()) if menu == "Költség" else None
        
        submit = st.form_submit_button("Mentés a táblázatba")
    
    if submit:
        sheet_name = "Penzugy_Koltsegek" if menu == "Költség" else "Penzugy_Bevetelek"
        _, sheet = load_data(sheet_name)
        row = [str(date), megnev, kategoria, ft, dinar] if menu == "Költség" else [str(date), megnev, ft, dinar]
        sheet.append_row(row)
        st.success("Sikeresen elmentve!")
        st.rerun()

    st.markdown("---")
    st.header("📊 Kimutatás")
    
    df_k, _ = load_data("Penzugy_Koltsegek")
    df_b, _ = load_data("Penzugy_Bevetelek")
    
    # --- Összesített tábla számítások ---
    df_k['Total_Ft'] = df_k['Összeg_Ft'] + (df_k['Összeg_Dinar'] * rsd_ar)
    total_bev_ft = df_b['Összeg_Ft'].sum() + (df_b['Összeg_Dinar'].sum() * rsd_ar)
    total_kolt_ft = df_k['Total_Ft'].sum()
    profit_ft = total_bev_ft - total_kolt_ft
    haszon_szazalek = (profit_ft / total_bev_ft * 100) if total_bev_ft > 0 else 0
    
    # Fő összefoglaló tábla
    data_summary = {
        "Pénznem": ["Forint (HUF)", "Dinár (RSD)", "Euró (EUR)"],
        "Bevétel": [f"{total_bev_ft:,.0f} Ft", f"{total_bev_ft/rsd_ar:,.0f} RSD", f"{total_bev_ft/eur_ar:,.2f} EUR"],
        "Költség": [f"{total_kolt_ft:,.0f} Ft", f"{total_kolt_ft/rsd_ar:,.0f} RSD", f"{total_kolt_ft/eur_ar:,.2f} EUR"],
        "Haszon": [f"{profit_ft:,.0f} Ft ({haszon_szazalek:.1f}%)", f"{profit_ft/rsd_ar:,.0f} RSD", f"{profit_ft/eur_ar:,.2f} EUR"]
    }
    st.table(pd.DataFrame(data_summary))

    # --- Részletes kiadások táblázatok ---
    st.header("📋 Részletes kiadások kategóriánként")
    
    for kat in df_k['Kategória'].unique():
        st.markdown(f"### 📁 Kategória: {kat}")
        
        cat_df = df_k[df_k['Kategória'] == kat].copy()
        
        # Csoportosítás megnevezésenként
        reszletes = cat_df.groupby('Megnevezés').agg({
            'Összeg_Ft': 'sum',
            'Összeg_Dinar': 'sum'
        }).reset_index()
        
        # Új oszlopok létrehozása a részletezéshez
        reszletes['Összesen (Ft)'] = reszletes['Összeg_Ft'] + (reszletes['Összeg_Dinar'] * rsd_ar)
        reszletes['Összesen (RSD)'] = reszletes['Összesen (Ft)'] / rsd_ar
        reszletes['Összesen (EUR)'] = reszletes['Összesen (Ft)'] / eur_ar
        
        # Megjelenítés: Megnevezés + 3 oszlop (Ft, RSD, EUR)
        st.table(reszletes[['Megnevezés', 'Összesen (Ft)', 'Összesen (RSD)', 'Összesen (EUR)']].style.format({
            'Összesen (Ft)': '{:,.0f}',
            'Összesen (RSD)': '{:,.0f}',
            'Összesen (EUR)': '{:,.2f}'
        }))
        st.markdown("<br>", unsafe_allow_html=True)

else:
    # --- Kategóriák kezelése ---
    st.header("Kategóriák kezelése")
    kat_df, sheet = load_data("Kategoriak")
    
    new_kat = st.text_input("Új kategória neve:")
    if st.button("Hozzáadás"):
        if new_kat:
            sheet.append_row([new_kat])
            st.rerun()
    
    st.markdown("---")
    st.subheader("Kategória törlése")
    torlendo = st.selectbox("Törlés:", kat_df['Nev'].tolist())
    if st.button("Kategória törlése véglegesítése"):
        cell = sheet.find(torlendo)
        sheet.delete_rows(cell.row)
        st.rerun()
