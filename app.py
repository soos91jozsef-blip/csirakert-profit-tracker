import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# Oldal konfigurációja
st.set_page_config(page_title="Csírakert Pénzügy", layout="wide")

# --- Funkciók ---

# 1. Árfolyamok lekérése API-ból
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

# 2. Google Sheets kapcsolat létrehozása
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    return gspread.authorize(creds.with_scopes(scope))

# 3. Adatok betöltése biztonsági ellenőrzésekkel
def load_data(sheet_name):
    client = get_gspread_client()
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    
    # Munkalap megnyitása
    sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
    
    # Adatok lekérése
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Definiáljuk az oszlopokat, ha a tábla üres lenne
    expected_cols = {
        "Penzugy_Koltsegek": ['Dátum', 'Megnevezés', 'Kategória', 'Összeg_Ft', 'Összeg_Dinar'],
        "Penzugy_Bevetelek": ['Dátum', 'Megnevezés', 'Összeg_Ft', 'Összeg_Dinar'],
        "Kategoriak": ['Nev']
    }
    
    # Ha üres a tábla, adjunk vissza egy üres DataFrame-et a megfelelő oszlopnevekkel
    if df.empty and sheet_name in expected_cols:
        return pd.DataFrame(columns=expected_cols[sheet_name]), sheet
    
    return df, sheet

# --- Felhasználói felület ---

st.title("🌱 Csírakert Pénzügy")

# Árfolyamok lekérése
rsd_ar, eur_ar = get_exchange_rates()

# Mód választó
mode = st.radio("Válaszd ki az üzemmódot:", ["Adatrögzítés", "Rekord törlése", "Kategóriák kezelése"], horizontal=True)

# 1. MÓD: ADATRÖGZÍTÉS
if mode == "Adatrögzítés":
    menu = st.radio("Mit szeretnél rögzíteni?", ["Költség", "Bevétel"], horizontal=True)
    
    with st.form("adat", clear_on_submit=True):
        c1, c2 = st.columns(2)
        megnev = c1.text_input("Megnevezés/Eszköz")
        date = c1.date_input("Dátum", datetime.now())
        ft = c2.number_input("Összeg (Ft)", min_value=0.0)
        dinar = c2.number_input("Összeg (Dinár)", min_value=0.0)
        
        kat_df, _ = load_data("Kategoriak")
        
        # Kategória választó (csak költségnél)
        kategoria = None
        if menu == "Költség":
            if not kat_df.empty:
                kategoria = st.selectbox("Kategória", kat_df['Nev'].tolist())
            else:
                st.warning("Nincsenek kategóriák. Előbb rögzíts egyet a 'Kategóriák kezelése' menüben!")
        
        # Mentés gomb
        if st.form_submit_button("Adatok mentése a táblázatba"):
            sheet_name = "Penzugy_Koltsegek" if menu == "Költség" else "Penzugy_Bevetelek"
            _, sheet = load_data(sheet_name)
            
            # Sor összeállítása
            row = [str(date), megnev, kategoria, ft, dinar] if menu == "Költség" else [str(date), megnev, ft, dinar]
            sheet.append_row(row)
            
            # FRISSÍTÉS: Cache ürítése, hogy azonnal lásd a változást
            st.cache_data.clear()
            st.success("Adat sikeresen elmentve!")
            st.rerun()

    # Kimutatás rész
    st.markdown("---")
    st.header("📊 Kimutatás")
    
    df_k, _ = load_data("Penzugy_Koltsegek")
    df_b, _ = load_data("Penzugy_Bevetelek")
    
    # Számítások
    total_kolt_ft = 0
    if not df_k.empty:
        df_k['Total_Ft'] = df_k['Összeg_Ft'] + (df_k['Összeg_Dinar'] * rsd_ar)
        total_kolt_ft = df_k['Total_Ft'].sum()
        
    total_bev_ft = (df_b['Összeg_Ft'].sum() + (df_b['Összeg_Dinar'].sum() * rsd_ar)) if not df_b.empty else 0
    profit_ft = total_bev_ft - total_kolt_ft
    
    # Összesítés megjelenítése
    data_summary = {
        "Pénznem": ["Forint (HUF)", "Dinár (RSD)", "Euró (EUR)"],
        "Bevétel": [f"{total_bev_ft:,.0f} Ft", f"{total_bev_ft/rsd_ar:,.0f} RSD", f"{total_bev_ft/eur_ar:,.2f} EUR"],
        "Költség": [f"{total_kolt_ft:,.0f} Ft", f"{total_kolt_ft/rsd_ar:,.0f} RSD", f"{total_kolt_ft/eur_ar:,.2f} EUR"],
        "Haszon": [f"{profit_ft:,.0f} Ft", f"{profit_ft/rsd_ar:,.0f} RSD", f"{profit_ft/eur_ar:,.2f} EUR"]
    }
    st.table(pd.DataFrame(data_summary))

# 2. MÓD: REKORD TÖRLÉSE
elif mode == "Rekord törlése":
    st.header("🗑️ Hibás rekord törlése")
    sheet_sel = st.radio("Melyik táblából szeretnél törölni?", ["Penzugy_Koltsegek", "Penzugy_Bevetelek"])
    df, sheet = load_data(sheet_sel)
    
    if not df.empty:
        st.dataframe(df)
        row_idx = st.selectbox("Válaszd ki a törlendő sor sorszámát:", range(len(df)))
        
        if st.button("Kijelölt sor végleges törlése"):
            sheet.delete_rows(row_idx + 2) # +2, mert gspread 1-alapú és van fejléc
            st.cache_data.clear() # FRISSÍTÉS
            st.success("Sor törölve.")
            st.rerun()
    else:
        st.info("A táblázat jelenleg üres.")

# 3. MÓD: KATEGÓRIÁK KEZELÉSE
else:
    st.header("Kategóriák kezelése")
    kat_df, sheet = load_data("Kategoriak")
    
    if not kat_df.empty:
        st.subheader("Jelenlegi kategóriák:")
        st.write(kat_df['Nev'].tolist())
        
    # Új hozzáadása
    new_kat = st.text_input("Új kategória neve:")
    if st.button("Kategória hozzáadása"):
        if new_kat:
            sheet.append_row([new_kat])
            st.cache_data.clear() # FRISSÍTÉS
            st.rerun()
    
    # Törlés
    st.markdown("---")
    if not kat_df.empty:
        torlendo = st.selectbox("Melyik kategóriát törölnéd?", kat_df['Nev'].tolist())
        if st.button("Kategória törlése véglegesítése"):
            cell = sheet.find(torlendo)
            if cell:
                sheet.delete_rows(cell.row)
                st.cache_data.clear() # FRISSÍTÉS
                st.success("Kategória törölve.")
                st.rerun()
