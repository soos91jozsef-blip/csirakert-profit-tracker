import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Oldal beállítása
st.set_page_config(page_title="Csírakert Pénzügy", layout="wide")

# --- Funkciók ---
@st.cache_data(ttl=21600)
def get_exchange_rates():
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/HUF"
        rates = requests.get(url).json()['conversion_rates']
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

# --- Felület ---
st.title("🌱 Csírakert Pénzügy")
st.markdown("---")
rsd_ar, eur_ar = get_exchange_rates()

mode = st.radio("Mód:", ["Adatrögzítés", "Kategóriák kezelése"], horizontal=True)

if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    with st.form("adat", clear_on_submit=True):
        c1, c2 = st.columns(2)
        megnev = c1.text_input("Megnevezés/Eszköz")
        date = c1.date_input("Dátum", datetime.now())
        ft = c2.number_input("Összeg (Ft)", min_value=0.0)
        dinar = c2.number_input("Összeg (Dinár)", min_value=0.0)
        
        kat_df, _ = load_data("Kategoriak")
        kategoria = st.selectbox("Kategória", kat_df['Nev'].tolist()) if menu == "Költség" else None
        
        if st.form_submit_button("Mentés"):
            sheet_name = "Penzugy_Koltsegek" if menu == "Költség" else "Penzugy_Bevetelek"
            _, sheet = load_data(sheet_name)
            row = [str(date), megnev, kategoria, ft, dinar] if menu == "Költség" else [str(date), megnev, ft, dinar]
            sheet.append_row(row)
            st.rerun()

    st.markdown("---")
    st.header("📊 Kimutatás")
    
    df_k, _ = load_data("Penzugy_Koltsegek")
    df_b, _ = load_data("Penzugy_Bevetelek")
    
    # Számítások
    df_k['Total_Ft'] = df_k['Összeg_Ft'] + (df_k['Összeg_Dinar'] * rsd_ar)
    total_bev = df_b['Összeg_Ft'].sum() + (df_b['Összeg_Dinar'].sum() * rsd_ar)
    total_kolt = df_k['Total_Ft'].sum()
    profit = total_bev - total_kolt
    
    # Kiemelt adatok (Metrikák)
    k1, k2, k3 = st.columns(3)
    k1.metric("Bevétel", f"{total_bev:,.0f} Ft")
    k2.metric("Költség", f"{total_kolt:,.0f} Ft")
    k3.metric("Haszon", f"{profit:,.0f} Ft", f"{(profit/total_bev*100 if total_bev>0 else 0):.1f}%")

    st.markdown("### 📋 Részletes kiadások")
    
    # Csoportosítás kategóriánként, hogy a "Magok" alá ne kerüljenek az "Üvegek"
    for kat in df_k['Kategória'].unique():
        st.markdown(f"#### 📁 {kat}")
        
        cat_df = df_k[df_k['Kategória'] == kat]
        # Összegezzük megnevezésenként, hogy az azonos eszközök összeadódjanak
        reszletes = cat_df.groupby('Megnevezés')['Total_Ft'].sum().reset_index()
        
        # Normális táblázat, nem ocsmány lista
        st.table(reszletes.rename(columns={'Total_Ft': 'Összesen (Ft)'}))
        st.write("") 

else:
    st.header("Kategóriák kezelése")
    kat_df, sheet = load_data("Kategoriak")
    new_kat = st.text_input("Új kategória:")
    if st.button("Hozzáadás"):
        sheet.append_row([new_kat])
        st.rerun()
