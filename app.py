import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ... (a kapcsolat és betöltő függvények maradnak) ...
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

# UI
st.title("🌱 Csírakert Pénzügy")

# Új menüpont a kategória hozzáadáshoz
mode = st.radio("Mód:", ["Adatrögzítés", "Új kategória felvétele"], horizontal=True)

if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    with st.form("adatbevitel_form"):
        # ... (ugyanaz a form, ami eddig volt) ...
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Dátum", datetime.now())
            megnev = st.text_input("Megnevezés/Eszköz")
        with col2:
            ft = st.number_input("Összeg (Ft)", min_value=0.0, step=10.0)
            dinar = st.number_input("Összeg (Dinar)", min_value=0.0, step=10.0)
        
        # Dinamikus kategória betöltés
        try:
            kat_df, _ = load_data("Kategoriak")
            kat_lista = kat_df['Nev'].tolist()
        except:
            kat_lista = ["Magok", "Eszközök", "Szállítás", "Egyéb"]
            
        kategoria = None
        if menu == "Költség":
            kategoria = st.selectbox("Kategória", kat_lista)
        
        submit = st.form_submit_button("Mentés")
    
    if submit:
        # ... (mentési logika) ...
        pass

else:
    # Új kategória hozzáadása a felületről
    st.subheader("Új kategória felvétele")
    new_kat = st.text_input("Kategória neve:")
    if st.button("Hozzáadás"):
        if new_kat:
            _, sheet = load_data("Kategoriak")
            sheet.append_row([new_kat])
            st.success(f"'{new_kat}' hozzáadva!")
            st.rerun()
