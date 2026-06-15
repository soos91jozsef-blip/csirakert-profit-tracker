import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Oldal beállítása
st.set_page_config(page_title="Csírakert Pénzügy", layout="centered")

# --- API és Google kapcsolatok ---
@st.cache_data(ttl=21600) # Frissítés kb. 6 óránként
def get_exchange_rates():
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/HUF"
        response = requests.get(url).json()
        if response['result'] == 'success':
            rates = response['conversion_rates']
            rsd_to_huf = 1 / rates['RSD']
            eur_to_huf = 1 / rates['EUR']
            return rsd_to_huf, eur_to_huf
    except:
        pass
    return 3.0, 400.0 # Biztonsági alapértelmezett értékek

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

# --- Felhasználói felület ---
st.title("🌱 Csírakert Pénzügy")

rsd_ar, eur_ar = get_exchange_rates()
st.caption(f"Aktuális árfolyamok: 1 RSD ≈ {rsd_ar:.2f} Ft | 1 EUR ≈ {eur_ar:.2f} Ft")

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

    # Kimutatás 3 pénznemben
    st.divider()
    st.header("📊 Kimutatás")
    try:
        df_k, _ = load_data("Penzugy_Koltsegek")
        df_b, _ = load_data("Penzugy_Bevetelek")
        
        total_bev_ft = df_b['Összeg_Ft'].sum() + (df_b['Összeg_Dinar'].sum() * rsd_ar)
        total_kolt_ft = df_k['Összeg_Ft'].sum() + (df_k['Összeg_Dinar'].sum() * rsd_ar)
        profit_ft = total_bev_ft - total_kolt_ft
        
        st.subheader("Pénzügyi összegzés")
        data = {
            "Pénznem": ["Forint (HUF)", "Dinár (RSD)", "Euró (EUR)"],
            "Bevétel": [
                f"{total_bev_ft:,.0f} Ft", 
                f"{total_bev_ft / rsd_ar:,.0f} RSD", 
                f"{total_bev_ft / eur_ar:,.2f} EUR"
            ],
            "Költség": [
                f"{total_kolt_ft:,.0f} Ft", 
                f"{total_kolt_ft / rsd_ar:,.0f} RSD", 
                f"{total_kolt_ft / eur_ar:,.2f} EUR"
            ],
            "Haszon": [
                f"{profit_ft:,.0f} Ft", 
                f"{profit_ft / rsd_ar:,.0f} RSD", 
                f"{profit_ft / eur_ar:,.2f} EUR"
            ]
        }
        st.table(pd.DataFrame(data))
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
