import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime

# ==============================================================================
# OLDAL KONFIGURÁCIÓJA
# ==============================================================================
st.set_page_config(page_title="Csírakert Pénzügy", layout="wide")

# ==============================================================================
# FUNKCIÓK
# ==============================================================================

@st.cache_data(ttl=21600)
def get_exchange_rates():
    """Árfolyamok lekérése API-ból. HUF-hoz viszonyítva."""
    try:
        api_key = st.secrets["api"]["exchange_rate_key"]
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/HUF"
        response = requests.get(url).json()
        rates = response['conversion_rates']
        # Visszaadjuk az átváltási arányokat
        # 1 Dinár = X Forint
        # 1 Euró = Y Forint
        return 1 / rates['RSD'], 1 / rates['EUR']
    except:
        # Ha nincs internet/API, használunk egy fix becslést
        return 3.0, 400.0

@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    return gspread.authorize(creds.with_scopes(scope))

def load_data(sheet_name):
    """Adatok betöltése a Google Sheets-ből."""
    client = get_gspread_client()
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sheet = client.open_by_url(spreadsheet_url).worksheet(sheet_name)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # Biztonsági oszlopok létrehozása, ha üres a tábla
    expected_cols = {
        "Penzugy_Koltsegek": ['Dátum', 'Megnevezés', 'Kategória', 'Összeg_Ft', 'Összeg_Dinar'],
        "Penzugy_Bevetelek": ['Dátum', 'Megnevezés', 'Összeg_Ft', 'Összeg_Dinar'],
        "Kategoriak": ['Nev']
    }
    if df.empty and sheet_name in expected_cols:
        return pd.DataFrame(columns=expected_cols[sheet_name]), sheet
    return df, sheet

# ==============================================================================
# FELHASZNÁLÓI FELÜLET
# ==============================================================================

st.title("🌱 Csírakert Pénzügy")
rsd_ar, eur_ar = get_exchange_rates()

mode = st.radio("Mód:", ["Adatrögzítés", "Rekord törlése", "Kategóriák kezelése"], horizontal=True)

# 1. MÓD: ADATRÖGZÍTÉS
if mode == "Adatrögzítés":
    menu = st.radio("Mit rögzítesz?", ["Költség", "Bevétel"], horizontal=True)
    with st.form("adat", clear_on_submit=True):
        c1, c2 = st.columns(2)
        megnev = c1.text_input("Megnevezés/Eszköz")
        date = c1.date_input("Dátum", datetime.now())
        ft = c2.number_input("Összeg (Ft)", min_value=0.0)
        dinar = c2.number_input("Összeg (Dinár)", min_value=0.0)
        
        kat_df, _ = load_data("Kategoriak")
        kategoria = st.selectbox("Kategória", kat_df['Nev'].tolist()) if (menu == "Költség" and not kat_df.empty) else None
        
        if st.form_submit_button("Mentés"):
            sheet_name = "Penzugy_Koltsegek" if menu == "Költség" else "Penzugy_Bevetelek"
            _, sheet = load_data(sheet_name)
            row = [str(date), megnev, kategoria, ft, dinar] if menu == "Költség" else [str(date), megnev, ft, dinar]
            sheet.append_row(row)
            st.cache_data.clear() 
            st.rerun()

    st.markdown("---")
    st.header("📊 Kimutatás (Összesített)")
    
    # Adatok betöltése
    df_k, _ = load_data("Penzugy_Koltsegek")
    df_b, _ = load_data("Penzugy_Bevetelek")
    
    # Számítások (HUF alapú közös nevezővel)
    if not df_k.empty:
        df_k['Total_Ft'] = df_k['Összeg_Ft'] + (df_k['Összeg_Dinar'] * rsd_ar)
        total_kolt_ft = df_k['Total_Ft'].sum()
    else:
        total_kolt_ft = 0
        
    if not df_b.empty:
        df_b['Total_Ft'] = df_b['Összeg_Ft'] + (df_b['Összeg_Dinar'] * rsd_ar)
        total_bev_ft = df_b['Total_Ft'].sum()
    else:
        total_bev_ft = 0
        
    profit_ft = total_bev_ft - total_kolt_ft
    haszon_szazalek = (profit_ft / total_bev_ft * 100) if total_bev_ft > 0 else 0
    
    # Összesítő tábla: itt látszik a 3 pénznem
    data_summary = {
        "Mutató": ["Bevétel", "Költség", "Haszon (Ft)", "Haszon (%)"],
        "Összeg (HUF)": [f"{total_bev_ft:,.0f} Ft", f"{total_kolt_ft:,.0f} Ft", f"{profit_ft:,.0f} Ft", f"{haszon_szazalek:.1f} %"],
        "Összeg (RSD)": [f"{total_bev_ft/rsd_ar:,.0f} RSD", f"{total_kolt_ft/rsd_ar:,.0f} RSD", f"{profit_ft/rsd_ar:,.0f} RSD", "-"],
        "Összeg (EUR)": [f"{total_bev_ft/eur_ar:,.2f} EUR", f"{total_kolt_ft/eur_ar:,.2f} EUR", f"{profit_ft/eur_ar:,.2f} EUR", "-"]
    }
    st.table(pd.DataFrame(data_summary))

    # Részletes lebontás
    st.header("📋 Részletes költség-eszköz lebontás")
    if not df_k.empty:
        reszletes = df_k.groupby(['Kategória', 'Megnevezés']).agg({
            'Összeg_Ft': 'sum', 
            'Összeg_Dinar': 'sum'
        }).reset_index()
        
        # Oszlop létrehozása a színezéshez
        reszletes['Összesen (Ft)'] = reszletes['Összeg_Ft'] + (reszletes['Összeg_Dinar'] * rsd_ar)
        
        # Színezett tábla (ehhez kell a matplotlib a requirements.txt-ben!)
        st.dataframe(
            reszletes.style.format({
                'Összeg_Ft': '{:,.0f}', 
                'Összeg_Dinar': '{:,.0f}',
                'Összesen (Ft)': '{:,.0f}'
            }).background_gradient(subset=['Összesen (Ft)'], cmap='Greens'),
            use_container_width=True
        )
    else:
        st.info("Még nincs rögzített költség.")

# 2. MÓD: REKORD TÖRLÉSE
elif mode == "Rekord törlése":
    st.header("🗑️ Hibás rekord törlése")
    sheet_sel = st.radio("Melyik táblából törölnél?", ["Penzugy_Koltsegek", "Penzugy_Bevetelek"])
    df, sheet = load_data(sheet_sel)
    
    if not df.empty:
        st.dataframe(df)
        row_idx = st.selectbox("Válaszd ki a törlendő sor sorszámát:", range(len(df)))
        if st.button("Kijelölt sor végleges törlése"):
            sheet.delete_rows(row_idx + 2)
            st.cache_data.clear()
            st.rerun()

# 3. MÓD: KATEGÓRIÁK KEZELÉSE
else:
    st.header("Kategóriák kezelése")
    kat_df, sheet = load_data("Kategoriak")
    
    if not kat_df.empty:
        st.write("Jelenlegi kategóriák:", kat_df['Nev'].tolist())
        
    new_kat = st.text_input("Új kategória neve:")
    if st.button("Hozzáadás"):
        if new_kat:
            sheet.append_row([new_kat])
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    if not kat_df.empty:
        torlendo = st.selectbox("Kategória törlése:", kat_df['Nev'].tolist())
        if st.button("Kategória törlése véglegesítése"):
            cell = sheet.find(torlendo)
            sheet.delete_rows(cell.row)
            st.cache_data.clear()
            st.rerun()
