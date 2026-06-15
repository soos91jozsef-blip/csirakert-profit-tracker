import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Oldal beállítása
st.set_page_config(page_title="Csírakert Pénzügy", layout="centered")

# --- 1. API és Google kapcsolatok ---
@st.cache_data(ttl=21600) # ttl=21600 mp (6 óra) -> így kb. naponta 4-szer frissít
def get_exchange_rate():
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/RSD/HUF"
        response = requests.get(url).json()
        if response['result'] == 'success':
            return response['conversion_rate']
    except:
        pass
    return 3.0 # Biztonsági alapértelmezett, ha az API nem elérhető

@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds_with_scope = creds.with_scopes(scope)
    return gspread.authorize(creds_with_scope)

def load_data(sheet_name):
    client = get_gspread_client()
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
    data = sheet.get_all_records()
    return pd.DataFrame(data), sheet

# --- 2. Felhasználói felület ---
st.title("🌱 Csírakert Pénzügy")

# Árfolyam kijelzése
arfolyam = get_exchange_rate()
st.caption(f"Aktuális árfolyam: 1 RSD = {arfolyam:.2f} HUF")

mode = st.radio("Mód:", ["Adatrögzítés", "Kategóriák kezelése"], horizontal=True)

if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    with st.form("adatbevitel_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Dátum", datetime.now())
            megnev = st.text_input("Megnevezés/Eszköz")
        with col2:
            ft = st.number_input("Összeg (Ft)", min_value=0.0, step=10.0)
            dinar = st.number_input("Összeg (Dinar)", min_value=0.0, step=10.0)
        
        try:
            kat_df, _ = load_data("Kategoriak")
            kat_lista = kat_df['Nev'].tolist()
        except:
            kat_lista = ["Magok", "Eszközök", "Szállítás", "Egyéb"]
            
        kategoria = None
        if menu == "Költség":
            kategoria = st.selectbox("Kategória", kat_lista)
        
        submit = st.form_submit_button("Mentés a táblázatba")
    
    if submit:
        try:
            if menu == "Költség":
                _, sheet = load_data("Penzugy_Koltsegek")
                sheet.append_row([str(date), megnev, kategoria, ft, dinar])
            else:
                _, sheet = load_data("Penzugy_Bevetelek")
                sheet.append_row([str(date), megnev, ft, dinar])
            st.success("Sikeresen elmentve!")
            st.rerun()
        except Exception as e:
            st.error(f"Hiba történt: {e}")

    st.divider()
    st.header("📊 Kimutatás")
    try:
        df_k, _ = load_data("Penzugy_Koltsegek")
        df_b, _ = load_data("Penzugy_Bevetelek")
        
        def calc_total(df):
            return df['Összeg_Ft'].sum() + (df['Összeg_Dinar'].sum() * arfolyam)
        
        total_bev = calc_total(df_b)
        total_kolt = calc_total(df_k)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Bevétel (Ft)", f"{total_bev:,.0f}")
        c2.metric("Költség (Ft)", f"{total_kolt:,.0f}")
        c3.metric("Profit (Ft)", f"{total_bev - total_kolt:,.0f}")
    except:
        st.info("Még nincs elég adat a kimutatáshoz.")

else:
    st.subheader("Kategóriák kezelése")
    with st.expander("Új kategória hozzáadása"):
        new_kat = st.text_input("Új kategória neve:")
        if st.button("Hozzáadás"):
            if new_kat:
                _, sheet = load_data("Kategoriak")
                sheet.append_row([new_kat])
                st.success(f"'{new_kat}' hozzáadva!")
                st.rerun()

    st.divider()
    st.subheader("Kategória törlése")
    try:
        kat_df, sheet = load_data("Kategoriak")
        kat_lista = kat_df['Nev'].tolist()
        torlendo = st.selectbox("Válaszd ki a törlendő kategóriát:", kat_lista)
        if st.button("Törlés véglegesítése"):
            cell = sheet.find(torlendo)
            sheet.delete_rows(cell.row)
            st.warning(f"'{torlendo}' törölve!")
            st.rerun()
    except:
        st.error("Nincs kategória a listában.")
