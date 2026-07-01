import streamlit as str_web
import pandas as pd
from io import BytesIO
import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, JsCode

from core.data_loader import FOLDER_DANYCH

MAGAZYNY_CENTRALNE = ['CZM', 'HZA', 'HSN']

def generuj_excel_rejestru(lista_transakcji):
    df_rejestr = pd.DataFrame(lista_transakcji)
    kolumny_excela = ['Indeks', 'Skąd', 'Dokąd']
    if not df_rejestr.empty and 'Dni na filii' in df_rejestr.columns:
        kolumny_excela.append('Dni na filii')
        
    if df_rejestr.empty:
        df_rejestr = pd.DataFrame(columns=kolumny_excela)
    else:
        df_rejestr = df_rejestr[kolumny_excela]
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_rejestr.to_excel(writer, index=False, sheet_name="Historia MM")
        workbook = writer.book
        worksheet = writer.sheets["Historia MM"]
        
        from openpyxl.styles import Font, Alignment
        from openpyxl.utils import get_column_letter
        
        for cell in worksheet[1]:
            cell.font = Font(name="Segoe UI", size=11, bold=True)
            cell.alignment = Alignment(horizontal="center")
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            worksheet.column_dimensions[col_letter].width = max(max_len + 4, 15)
            
    return output.getvalue()

def stylizuj_matryce_logistycznie(data):
    style_df = pd.DataFrame('', index=data.index, columns=data.columns)
    indeks_startowy = str(str_web.session_state.get('klikniety_indeks_startowy', '')).strip()
    cel = str(str_web.session_state.get('klikniety_cel', '')).strip()
    zrodla = [str(x).strip() for x in str_web.session_state.get('klikniete_zrodla', [])]
    
    for idx, row in data.iterrows():
        sku = str(idx[1]).strip() 
        is_selected_sku = (sku == indeks_startowy)
        
        czm_stan = 0
        czm_minmax = 0
        if ("CZM", "Stan") in data.columns:
            try: czm_stan = float(row[("CZM", "Stan")])
            except: pass
        if ("CZM", "MIN MAX") in data.columns:
            try: czm_minmax = float(row[("CZM", "MIN MAX")])
            except: pass
        wolny_zapas_czm = max(0, czm_stan - czm_minmax)

        for col in data.columns:
            if not isinstance(col, tuple) or len(col) != 2: continue
            filia = str(col[0]).strip()
            typ = str(col[1]).strip()
            css_style = 'text-align: center;'
            
            f_stan = 0
            f_sprzedaz = 0
            f_minmax = 0
            try: f_stan = float(row[(filia, "Stan")])
            except: pass
            try: f_sprzedaz = float(row[(filia, "Sprzedaż")])
            except: pass
            try: f_minmax = float(row[(filia, "MIN MAX")])
            except: pass

            klucz_niebieski = f"{sku}_{filia}"
            if klucz_niebieski in str_web.session_state['wykonane_mm_rozmiary']:
                css_style += ' background-color: #D6EAF8; color: #1B4F72; font-weight: bold; border: 1px solid #85C1E9;'
            else:
                if filia not in MAGAZYNY_CENTRALNE:
                    if typ == "Stan" and f_stan > 0 and f_sprzedaz == 0:
                        css_style += ' background-color: #FADBD8; color: #78281F; font-weight: bold;'
                    elif typ == "Sprzedaż" and f_stan == 0 and f_sprzedaz > 0 and (wolny_zapas_czm == 0 or f_minmax == 0):
                        css_style += ' background-color: #D4EFDF; color: #196F3D; font-weight: bold;'

            if is_selected_sku:
                if filia == cel and typ == "Sprzedaż":
                    css_style += ' border: 2px solid #2ECC71; font-weight: bold;'
                elif filia in zrodla and typ == "Stan":
                    css_style += ' border: 2px solid #E74C3C; font-weight: bold;'
                    
            style_df.at[idx, col] = css_style
    return style_df

def wyswietl_ekran_glowny(wyciagnij_rdzen_po_przecinku, convert_df):
    df_stany = str_web.session_state['df_stany']
    df_sprzedaz_surowa = str_web.session_state['df_sprzedaz_surowa']
    df_minmax = str_web.session_state['df_minmax']

    lista_producentów = sorted(df_stany['Producent'].dropna().unique().tolist())
    lista_statusów = sorted(df_stany['Status_produktu'].dropna().unique().tolist())
    lista_wszystkich_sklepow = sorted([f for f in df_stany['Filia'].unique() if f not in MAGAZYNY_CENTRALNE])

    # --- PRZYCISK WEJŚCIA DO WERYFIKATORA ---
    str_web.sidebar.header("🛠️ Narzędzia Logistyczne")
    if str_web.sidebar.button("📈 Zweryfikuj Przesunięcia", width="stretch"):
        str_web.session_state['aktywny_ekran'] = "weryfikator"
        str_web.rerun()

    str_web.sidebar.markdown("<hr>", unsafe_allow_html=True)

    str_web.sidebar.header("⚙️ Filtry BI")

    zakres_options = [30, 60, 90, 120]
    zakres_dni = str_web.sidebar.selectbox("Okres wsteczny analizy sprzedaży", 
        options=zakres_options, 
        format_func=lambda x: f"Ostatnie {x} dni",
        key='f_zakres_dni'
    )

    str_web.sidebar.markdown("<hr>", unsafe_allow_html=True)
    dni_karencji = str_web.sidebar.slider(
        "⛔ Blokada ostatnich dostaw", 
        min_value=0, 
        max_value=90, 
        value=14,
        help="Blokuje generowanie rekomendacji przesunięć dla sklepów, które otrzymały dany towar w określonym przedziale dni."
    )

    cena_min = str_web.sidebar.slider("Minimalna cena detaliczna netto (PLN)", 50, 2000, step=50, key='f_cena_min')
    marza_min = str_web.sidebar.slider(
        "Minimalna marża netto na sztuce (PLN)", 
        -100, 1000, step=20, 
        key='f_marza_min',
        help="Odrzuci relokacje towarów, których wyliczona marża jest niższa niż ta wartość."
    )
    popyt_min = str_web.sidebar.slider("Minimalny popyt wymagany w sklepie docelowym (szt.)", 1, 10, step=1, key='f_popyt_min')

    wybrani_producenci = str_web.sidebar.multiselect("Producent", 
        options=lista_producentów, 
        key='f_wybrani_producenci'
    )

    if wybrani_producenci:
        df_filtr_tymczasowy = df_stany[df_stany['Producent'].isin(wybrani_producenci)]
    else:
        df_filtr_tymczasowy = df_stany

    lista_grup = sorted([str(x) for x in df_filtr_tymczasowy['Grupa Towarowa'].dropna().unique() if str(x).strip() != ''])
    
    wybrane_grupy = str_web.sidebar.multiselect(
        "Grupa Towarowa", 
        options=lista_grup, 
        key='f_wybrane_grupy',
        help="Lista grup dostosowuje się do wybranego Producenta."
    )

    wybrane_statusy = str_web.sidebar.multiselect("Status", 
        options=lista_statusów, 
        key='f_wybrane_statusy'
    )
    wybrane_filie_zrodlo = str_web.sidebar.multiselect(
        "Filia Źródłowa", 
        options=lista_wszystkich_sklepow, 
        key='f_wybrane_filie_zrodlo',
        help="Wybierz filie, w której chcesz zlokalizować zalegający towar."
    )
    wybrane_filie_cel = str_web.sidebar.multiselect("Filia Docelowa", 
        options=lista_wszystkich_sklepow, 
        key='f_wybrane_filie_cel',
        help="Wybierz filie, które chcesz dotowarować"
    )

    # --- 📊 ROZBUDOWANE STATYSTYKI SIDEBARA ---
    str_web.sidebar.markdown("<br><hr>", unsafe_allow_html=True)
    str_web.sidebar.subheader("📈 Licznik")
    
    rejestr_mm = str_web.session_state['rejestr_przesuniec_mm']
    liczba_mm = len(rejestr_mm)
    
    str_web.sidebar.metric(label="Wykonane przesunięcia (szt.)", value=f"{liczba_mm}")
    
    if liczba_mm > 0:
        statystyki_producentow = {}
        statystyki_skad = {}
        statystyki_dokad = {}
        
        for transakcja in rejestr_mm:
            sku = transakcja['Indeks']
            skad = transakcja['Skąd']
            dokad = transakcja['Dokąd']
            wiersz_stany = df_stany[df_stany['Indeks'] == sku]
            producent = str(wiersz_stany['Producent'].iloc[0]).upper().strip() if not wiersz_stany.empty else "NIEZNANY"
            statystyki_producentow[producent] = statystyki_producentow.get(producent, 0) + 1
            statystyki_skad[skad] = statystyki_skad.get(skad, 0) + 1
            statystyki_dokad[dokad] = statystyki_dokad.get(dokad, 0) + 1
            
        str_web.sidebar.markdown("📦 **Podział na marki:**")
        for prod, ilosc in sorted(statystyki_producentow.items(), key=lambda x: x[1], reverse=True):
            str_web.sidebar.markdown(f"🔹 {prod} : **{ilosc}**")
        str_web.sidebar.markdown("<br>🛫 **Skąd zabrano (szt.):**", unsafe_allow_html=True)
        for filia_zr, ilosc in sorted(statystyki_skad.items(), key=lambda x: x[1], reverse=True):
            str_web.sidebar.markdown(f"🔸 {filia_zr} : **{ilosc}**")
        str_web.sidebar.markdown("<br>🛬 **Dokąd wysłano (szt.):**", unsafe_allow_html=True)
        for filia_cel, ilosc in sorted(statystyki_dokad.items(), key=lambda x: x[1], reverse=True):
            str_web.sidebar.markdown(f"🔸 {filia_cel} : **{ilosc}**")

    najnowsza_data = df_sprzedaz_surowa['Data_Transakcji'].max()
    data_graniczna = najnowsza_data - pd.Timedelta(days=zakres_dni)
    
    df_sprzedaz_okresowa = df_sprzedaz_surowa[df_sprzedaz_surowa['Data_Transakcji'] >= data_graniczna]
    df_sprzedaz_zagregowana = df_sprzedaz_okresowa.groupby(['Indeks', 'Filia'])['Ilosc_szt'].sum().reset_index()
    df_sprzedaz_zagregowana.rename(columns={'Ilosc_szt': 'Sprzedaz_szt'}, inplace=True)

    df_minmax_clean = df_minmax.drop_duplicates(subset=['Indeks', 'Filia']).copy()

    df_czm_stan = df_stany[df_stany['Filia'] == 'CZM'][['Indeks', 'Stan_szt']].copy()
    df_czm_stan.rename(columns={'Stan_szt': 'Stan_CZM'}, inplace=True)
    df_czm_max = df_minmax_clean[df_minmax_clean['Filia'] == 'CZM'][['Indeks', 'Max_Ilosc']].copy()
    df_czm_max.rename(columns={'Max_Ilosc': 'Max_CZM'}, inplace=True)

    df_czm_logistyka = pd.merge(df_czm_stan, df_czm_max, on='Indeks', how='left')
    df_czm_logistyka['Stan_CZM'] = df_czm_logistyka['Stan_CZM'].fillna(0)
    df_czm_logistyka['Max_CZM'] = df_czm_logistyka['Max_CZM'].fillna(0)
    df_czm_logistyka['Wolny_Zapas_CZM'] = df_czm_logistyka['Stan_CZM'] - df_czm_logistyka['Max_CZM']
    df_czm_logistyka.loc[df_czm_logistyka['Wolny_Zapas_CZM'] < 0, 'Wolny_Zapas_CZM'] = 0

    df_sklepy_stany = df_stany[~df_stany['Filia'].isin(MAGAZYNY_CENTRALNE)].copy()
    df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Stan_szt'] > 0]

    if wybrani_producenci: df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Producent'].isin(wybrani_producenci)]
    if wybrane_grupy: df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Grupa Towarowa'].isin(wybrane_grupy)]
    if wybrane_statusy: df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Status_produktu'].isin(wybrane_statusy)]

    baza_zrodlowa = pd.merge(df_sklepy_stany, df_sprzedaz_zagregowana, on=['Indeks', 'Filia'], how='left')
    baza_zrodlowa['Sprzedaz_szt'] = baza_zrodlowa['Sprzedaz_szt'].fillna(0)

    zlogi = baza_zrodlowa[
        (baza_zrodlowa['Stan_szt'] > 0) & 
        (baza_zrodlowa['Sprzedaz_szt'] == 0) & 
        (baza_zrodlowa['Cena'] >= cena_min) &
        (baza_zrodlowa['Marza_PLN'] >= marza_min)
    ]

    popyt = df_sprzedaz_zagregowana[df_sprzedaz_zagregowana['Sprzedaz_szt'] >= popyt_min].copy()
    popyt = popyt[~popyt['Filia'].isin(MAGAZYNY_CENTRALNE)]
    popyt.rename(columns={'Filia': 'Filia_Cel', 'Sprzedaz_szt': 'Sprzedaz_Cel'}, inplace=True)

    sprawdzenie_stanu_celu = df_stany[['Indeks', 'Filia', 'Stan_szt']].copy()
    sprawdzenie_stanu_celu.columns = ['Indeks', 'Filia_Cel', 'Stan_Cel']
    popyt = pd.merge(popyt, sprawdzenie_stanu_celu, on=['Indeks', 'Filia_Cel'], how='left')
    popyt['Stan_Cel'] = popyt['Stan_Cel'].fillna(0)
    popyt_pusta_polka = popyt[popyt['Stan_Cel'] == 0].copy()

    df_minmax_sklepy = df_minmax_clean[~df_minmax_clean['Filia'].isin(MAGAZYNY_CENTRALNE)].copy()
    df_minmax_sklepy['Ma_Profil'] = True
    
    popyt_matryca = pd.merge(popyt_pusta_polka, df_minmax_sklepy[['Indeks', 'Filia', 'Ma_Profil', 'Max_Ilosc']], left_on=['Indeks', 'Filia_Cel'], right_on=['Indeks', 'Filia'], how='left')
    if 'Filia' in popyt_matryca.columns: popyt_matryca.drop(columns=['Filia'], inplace=True)
    popyt_matryca['Ma_Profil'] = popyt_matryca['Ma_Profil'].fillna(False)
    popyt_matryca['Max_Ilosc'] = popyt_matryca['Max_Ilosc'].fillna(0)

    popyt_weryfikacja_czm = pd.merge(popyt_matryca, df_czm_logistyka[['Indeks', 'Stan_CZM', 'Max_CZM', 'Wolny_Zapas_CZM']], on='Indeks', how='left')
    popyt_weryfikacja_czm['Stan_CZM'] = popyt_weryfikacja_czm['Stan_CZM'].fillna(0)
    popyt_weryfikacja_czm['Max_CZM'] = popyt_weryfikacja_czm['Max_CZM'].fillna(0)
    popyt_weryfikacja_czm['Wolny_Zapas_CZM'] = popyt_weryfikacja_czm['Wolny_Zapas_CZM'].fillna(0)

    popyt_uzasadniony = popyt_weryfikacja_czm[(popyt_weryfikacja_czm['Ma_Profil'] == False) | (popyt_weryfikacja_czm['Wolny_Zapas_CZM'] == 0)]

    rekomendacje = pd.merge(zlogi, popyt_uzasadniony, on='Indeks')
    rekomendacje = rekomendacje[rekomendacje['Filia'] != rekomendacje['Filia_Cel']]

    if dni_karencji > 0 and 'slownik_karencji_mm' in str_web.session_state:
        slownik_dostaw = str_web.session_state['slownik_karencji_mm']
        dzis = datetime.date.today()
        
        def zweryfikuj_karencje_wiersza(row):
            klucz = f"{str(row['Indeks']).strip()}_{str(row['Filia_Cel']).strip()}"
            if klucz in slownik_dostaw:
                dni_od_dostawy = (dzis - slownik_dostaw[klucz]).days
                return (dni_od_dostawy - 1) >= dni_karencji
            return True

        rekomendacje = rekomendacje[rekomendacje.apply(zweryfikuj_karencje_wiersza, axis=1)].copy()

    str_web.subheader(f"Wyniki Analizy (zakres {zakres_dni} dni)") 

    if rekomendacje.empty: 
        str_web.warning("Brak rekomendacji przesunięć dla wybranych w tym momencie kryteriów.") 
    else:
        raport_grouped = rekomendacje.groupby([ 
            'Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu',  
            'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM' 
        ]).agg({ 
            'Filia': lambda x: ', '.join(x.unique()), 
            'Stan_szt': 'sum' 
        }).reset_index() 

        raport_grouped = raport_grouped[['Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu', 'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM', 'Filia', 'Stan_szt']]
        
        raport_grouped['🔍'] = False
        raport_grouped['✅'] = raport_grouped.apply(lambda r: f"{r['Indeks']}_{r['Filia_Cel']}" in str_web.session_state['zrobione_transakcje'], axis=1)
        raport_grouped['🔍'] = raport_grouped['🔍'].astype(bool)
        raport_grouped['✅'] = raport_grouped['✅'].astype(bool)

        try:
            import os
            # 🔴 NAPRAWIONE: ścieżka względna 'Smart_MM' zależała od katalogu roboczego (CWD) w
            # momencie uruchomienia streamlita - działała tylko wtedy, gdy aplikację odpalano z
            # katalogu głównego projektu. Teraz używamy tej samej ścieżki bezwzględnej co
            # core/data_loader.py, więc działa niezależnie od CWD.
            sciezka_bo = os.path.join(FOLDER_DANYCH, 'dostawy_bo.csv')
            if not os.path.exists(sciezka_bo):
                # 🔴 NAPRAWIONE: literówka - ta gałąź ustawiała kolumnę 'BO', a kod niżej (finalny
                # wybór kolumn) oczekuje 'Ilość BO'. Nigdy się to nie ujawniło, bo plik BO zawsze
                # istniał przy uruchomieniu z katalogu głównego.
                raport_grouped['Ilość BO'] = 0
                raport_grouped['Dostawy_BO_Tooltip'] = "Brak pliku 'dostawy_bo.csv' w folderze Smart_MM"
            else:
                try:
                    df_dostawy = pd.read_csv(sciezka_bo, dtype=str, encoding='utf-8')
                except UnicodeDecodeError:
                    df_dostawy = pd.read_csv(sciezka_bo, dtype=str, encoding='cp1250')
                
                if len(df_dostawy.columns) == 1:
                    try:
                        df_dostawy = pd.read_csv(sciezka_bo, dtype=str, sep=';', encoding='utf-8')
                    except UnicodeDecodeError:
                        df_dostawy = pd.read_csv(sciezka_bo, dtype=str, sep=';', encoding='cp1250')

                df_dostawy.columns = [c.strip() for c in df_dostawy.columns]
                
                if 'Indeks' in df_dostawy.columns and 'Ilość BO' in df_dostawy.columns:
                    df_dostawy['Indeks'] = df_dostawy['Indeks'].astype(str).str.strip()
                    df_dostawy['Ilość BO'] = pd.to_numeric(df_dostawy['Ilość BO'], errors='coerce').fillna(0).astype(int)
                    
                    if 'Termin' in df_dostawy.columns:
                        df_dostawy['Termin'] = df_dostawy['Termin'].fillna('Brak daty').astype(str).str.strip()
                        df_dostawy['Termin'] = df_dostawy['Termin'].apply(lambda x: str(x).split(' ')[0] if x != 'Brak daty' else x)
                    else:
                        df_dostawy['Termin'] = 'Brak daty'
                    
                    df_bo_sumarycznie = df_dostawy.groupby('Indeks')['Ilość BO'].sum().reset_index()
                    
                    def buduj_tekst_dymka(sub_df):
                        linijki = ["Planowane dostawy z BO:"]
                        for _, r in sub_df.iterrows():
                            if r['Ilość BO'] > 0:
                                linijki.append(f"• {r['Termin']}: {r['Ilość BO']} szt.")
                        return "\n".join(linijki) if len(linijki) > 1 else "Brak zaplanowanych dostaw w BO."

                    df_bo_tooltips = df_dostawy.groupby('Indeks').apply(buduj_tekst_dymka, include_groups=False).reset_index()
                    df_bo_tooltips.columns = ['Indeks', 'Dostawy_BO_Tooltip']
                    
                    raport_grouped['Indeks'] = raport_grouped['Indeks'].astype(str).str.strip()
                    raport_grouped = pd.merge(raport_grouped, df_bo_sumarycznie, on='Indeks', how='left')
                    raport_grouped = pd.merge(raport_grouped, df_bo_tooltips, on='Indeks', how='left')
                    
                    raport_grouped['Ilość BO'] = raport_grouped['Ilość BO'].fillna(0).astype(int)
                    raport_grouped['Dostawy_BO_Tooltip'] = raport_grouped['Dostawy_BO_Tooltip'].fillna("Brak zaplanowanych dostaw w BO.")
                else:
                    raport_grouped['Ilość BO'] = 0
                    raport_grouped['Dostawy_BO_Tooltip'] = "Błąd struktury kolumn w pliku BO."
        except Exception as e:
            raport_grouped['Ilość BO'] = 0
            raport_grouped['Dostawy_BO_Tooltip'] = f"Problem techniczny: {str(e)}"

        nazwa_kolumny_sprzedazy = f'PJM ({zakres_dni} dni)'
        
        raport_grouped = raport_grouped[[
            '🔍', '✅', 'Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu', 
            'Ilość BO', 'Dostawy_BO_Tooltip', 'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM', 'Filia', 'Stan_szt'
        ]]
        
        raport_grouped.columns = [
            '🔍', '✅',
            'Indeks', 'Producent', 'Nazwa Produktu', 'Cena Detal Netto', 'Marża Netto', 'Status', 
            'BO', 'Dostawy_BO_Tooltip',
            'Sklep', nazwa_kolumny_sprzedazy, 'MAX', 
            'CZM Stan', 'CZM MAX', f'Skąd zabrać (Sklepy bez sprzedaży w {zakres_dni} dni)', 
            'Łączna ilość w sklepach bez sprzedaży'
        ]
        
        kolumny_liczbowe = [nazwa_kolumny_sprzedazy, 'MAX', 'CZM Stan', 'CZM MAX', 'Łączna ilość w sklepach bez sprzedaży', 'BO']
        for col in kolumny_liczbowe:
            if col in raport_grouped.columns:
                raport_grouped[col] = pd.to_numeric(raport_grouped[col], errors='coerce').fillna(0).astype(int)
                
        # 🟢 DOMYŚLNE SORTOWANIE OD NAJWIĘKSZEJ SPRZEDAŻY, A POTEM OD NAJWYŻSZEJ CENY
        raport_grouped = raport_grouped.sort_values(by=[nazwa_kolumny_sprzedazy, 'Cena Detal Netto'], ascending=[False, False])

        if wybrane_filie_cel:
            raport_grouped = raport_grouped[raport_grouped['Sklep'].isin(wybrane_filie_cel)]
        if wybrane_filie_zrodlo:
            pattern = '|'.join(wybrane_filie_zrodlo)
            col_skad_nazwa = [c for c in raport_grouped.columns if "Skąd zabrać" in c][0]
            raport_grouped = raport_grouped[raport_grouped[col_skad_nazwa].astype(str).str.contains(pattern, case=False, na=False)]
        
        raport_grouped = raport_grouped[
            (raport_grouped['Cena Detal Netto'] >= cena_min) & 
            (raport_grouped['Marża Netto'] >= marza_min)
        ]
        
        col_search1, col_search2, col_search3 = str_web.columns(3)
        with col_search1: szukaj_indeks = str_web.text_input("Filtruj po kolumnie: Indeks", value="")
        with col_search2: szukaj_producent = str_web.text_input("Filtruj po kolumnie: Producent", value="")
        with col_search3: szukaj_nazwa = str_web.text_input("Filtruj po kolumnie: Opis", value="")

        if szukaj_indeks: raport_grouped = raport_grouped[raport_grouped['Indeks'].astype(str).str.contains(szukaj_indeks, case=False, na=False)]
        if szukaj_producent: raport_grouped = raport_grouped[raport_grouped['Producent'].astype(str).str.contains(szukaj_producent, case=False, na=False)]
        if szukaj_nazwa: raport_grouped = raport_grouped[raport_grouped['Nazwa Produktu'].astype(str).str.contains(szukaj_nazwa, case=False, na=False)]

        str_web.info("💡 Kliknij dwukrotnie w kwadracik w kolumnie 🔍 lub ✅ aby go zaznaczyć. Zmiany są odzwierciedlane natychmiast.")

        # ==============================================================================
        # --- ZAKLESZCZENIE GŁÓWNEJ MATRYCY W SILNIK AG GRID ---
        # ==============================================================================
        gb = GridOptionsBuilder.from_dataframe(raport_grouped)
        
        gb.configure_default_column(
            resizable=True,
            filterable=True,
            sortable=True,
            suppressMovable=True,
            suppressSizeToFit=True,  
            flex=0                  
        )
        
        gb.configure_column("🔍", width=55, editable=True, cellRenderer="agCheckboxCellRenderer", cellEditor="agCheckboxCellEditor")
        gb.configure_column("✅", width=55, editable=True, cellRenderer="agCheckboxCellRenderer", cellEditor="agCheckboxCellEditor")
        
        gb.configure_column("Indeks", cellStyle={"textAlign": "left"}, width=130)
        gb.configure_column("Producent", cellStyle={"textAlign": "left"}, width=120)
        gb.configure_column("Nazwa Produktu", cellStyle={"textAlign": "left"}, width=200)
        gb.configure_column("Cena Detal Netto", cellStyle={"textAlign": "center"}, width=170, valueFormatter="x.toFixed(2) + ' PLN'")
        gb.configure_column("Marża Netto", cellStyle={"textAlign": "center"}, width=150, valueFormatter="x.toFixed(2) + ' PLN'")
        gb.configure_column("Status", cellStyle={"textAlign": "center"}, width=110)
        
        js_pobierz_tooltip_bo = JsCode("function(params) { return params.data.Dostawy_BO_Tooltip; }")
        gb.configure_column(
            "BO",
            cellStyle={"textAlign": "center", "color": "#0055A4", "fontWeight": "bold", "borderRight": "2px solid #17202A"},
            tooltipValueGetter=js_pobierz_tooltip_bo,
            width=115
        )
        gb.configure_column("Dostawy_BO_Tooltip", hide=True) 
        
        # --- BLOK GRUPOWANIA ANALIZY SKLEPU DOCELOWEGO Z PEŁNYM OBRAMOWANIEM PIONOWYM ---
        gb.configure_column(
            "Sklep", 
            cellStyle={"textAlign": "center", "fontWeight": "bold", "borderLeft": "3px solid #1c1c1c"},
            headerClass="left-border",
            width=90
        )
        gb.configure_column(
            nazwa_kolumny_sprzedazy, 
            cellStyle={"textAlign": "center"}, 
            width=140
        )
        gb.configure_column(
            "MAX", 
            cellStyle={"textAlign": "center", "borderRight": "3px solid #1c1c1c"}, 
            headerClass="right-border",
            width=80
        )
        
        gb.configure_column("CZM Stan", cellStyle={"textAlign": "center"}, width=90)
        gb.configure_column(
            "CZM MAX", 
            cellStyle={"textAlign": "center", "borderRight": "3px solid #1c1c1c"}, 
            headerClass="right-border",
            width=100
        )
        gb.configure_column("Łączna ilość w sklepach bez sprzedaży", cellStyle={"textAlign": "center"}, width=120)
        gb.configure_column(f"Skąd zabrać (Sklepy bez sprzedaży w {zakres_dni} dni)", cellStyle={"textAlign": "left"}, width=290)
        
        grid_options = gb.build()
        
        grid_options["tooltipShowDelay"] = 0
        grid_options["enableCellTextSelection"] = True
        
        old_cols = grid_options["columnDefs"]
        new_cols = []
        target_group_children = []
        czm_group_children = []
        
        for col in old_cols:
            field_name = col.get("field")
            if field_name in ["Sklep", nazwa_kolumny_sprzedazy, "MAX"]:
                target_group_children.append(col)
            elif field_name in ["CZM Stan", "CZM MAX"]:
                czm_group_children.append(col)
            elif field_name == "Dostawy_BO_Tooltip":
                continue 
            else:
                new_cols.append(col)
                
        new_cols.insert(9, {
            "headerName": "SKLEP DOCELOWY",
            "marryChildren": True,
            "headerClass": "group-border full-box-border",
            "children": target_group_children
        })
        
        for child in czm_group_children:
            if child["field"] == "CZM Stan":
                child["headerName"] = "Stan"
            elif child["field"] == "CZM MAX":
                child["headerName"] = "MAX"
                child["cellStyle"] = {"textAlign": "center", "borderRight": "3px solid #1c1c1c"}
                child["headerClass"] = "right-border"

        new_cols.insert(10, {
            "headerName": "MAGAZYN CZM",
            "marryChildren": True,
            "headerClass": "group-border",
            "children": czm_group_children
        })
        
        grid_options["columnDefs"] = new_cols

        custom_css = {
            ".ag-header-cell": {"text-align": "center !important"},
            ".ag-header-cell-label": {"justify-content": "center !important", "text-align": "center !important"},
            ".ag-header-group-cell-label": {"justify-content": "center !important", "text-align": "center !important"},
            ".left-border": {"border-left": "3px solid #1c1c1c !important"},
            ".right-border": {"border-right": "3px solid #1c1c1c !important"},
            ".group-border": {
                "border-right": "3px solid #1c1c1c !important",
                "text-align": "center !important"
            },
            ".full-box-border": {
                "border-left": "3px solid #1c1c1c !important"
            }
        }

        grid_response = AgGrid(
            raport_grouped,
            gridOptions=grid_options,
            custom_css=custom_css,
            data_return_mode="FILTERED_AND_SORTED",
            update_mode="VALUE_CHANGED",
            allow_unsafe_jscode=True, 
            fit_columns_on_grid_load=False,
            columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE,
            domLayout='normal',
            theme="alpine",
            height=400,
            width="100%"
        )
        
        raport_grouped_filtered = pd.DataFrame(grid_response["data"])

        if not grid_response["data"].empty:
            df_zmiany = grid_response["data"]
            for idx, wiersz in df_zmiany.iterrows():
                
                kliknieto_lupa = wiersz.get("🔍") == True or str(wiersz.get("🔍")).lower() == 'true'
                if kliknieto_lupa:
                    pelna_nazwa_towaru = wiersz['Nazwa Produktu']
                    str_web.session_state['aktywny_ekran'] = "detal_maski"
                    str_web.session_state['wybrany_rdzen_opisu'] = wyciagnij_rdzen_po_przecinku(pelna_nazwa_towaru)
                    str_web.session_state['klikniety_indeks_startowy'] = wiersz['Indeks']
                    str_web.session_state['klikniety_cel'] = wiersz['Sklep']
                    col_skad = [c for c in raport_grouped.columns if "Skąd zabrać" in c][0]
                    str_web.session_state['klikniete_zrodla'] = [x.strip() for x in str(wiersz[col_skad]).split(',')]
                    str_web.rerun()
                
                klucz_transakcji = f"{wiersz['Indeks']}_{wiersz['Sklep']}"
                kliknieto_zapis = wiersz.get("✅") == True or str(wiersz.get("✅")).lower() == 'true'
                
                if kliknieto_zapis:
                    if klucz_transakcji not in str_web.session_state['zrobione_transakcje']:
                        str_web.session_state['zrobione_transakcje'].append(klucz_transakcji)
                        str_web.rerun()
                else:
                    if klucz_transakcji in str_web.session_state['zrobione_transakcje']:
                        str_web.session_state['zrobione_transakcje'].remove(klucz_transakcji)
                        str_web.rerun()

        raport_do_excela = raport_grouped_filtered.drop(columns=['✅', '🔍', 'Dostawy_BO_Tooltip'], errors='ignore')
        excel_data = convert_df(raport_do_excela)
        str_web.download_button(
            label=f"📥 Pobierz ten odfiltrowany widok ({len(raport_grouped_filtered)} pozycji) do Excela",
            data=excel_data,
            file_name=f"SmartAlert_Filtrowany_{zakres_dni}dni.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- HISTORIA Z KRZYŻYKIEM ❌ ---
    str_web.markdown("---")
    str_web.subheader("📋 Rejestr Przesunięć MM (Bieżąca Sesja)")
    
    if str_web.session_state['rejestr_przesuniec_mm']:
        df_rejestr_widok = pd.DataFrame(str_web.session_state['rejestr_przesuniec_mm']).copy()
        df_rejestr_widok['❌'] = False  
        
        kolumny_widoku = ['❌', 'Indeks', 'Skąd', 'Dokąd']
        if 'Dni na filii' in df_rejestr_widok.columns:
            kolumny_widoku.append('Dni na filii')
            
        df_rejestr_widok = df_rejestr_widok[kolumny_widoku]
        
        col_rej1, col_rej2 = str_web.columns([3, 1])
        with col_rej1:
            edytor_glowny = str_web.data_editor(
                df_rejestr_widok, 
                width="stretch", 
                hide_index=True,
                key="edytor_rejestru_glownego",
                disabled=['Indeks', 'Skąd', 'Dokąd', 'Dni na filii'],
                column_config={"❌": str_web.column_config.CheckboxColumn("❌", width=45, help="Zaznacz, aby usunąć ten wpis")}
            )
            
            if "edytor_rejestru_glownego" in str_web.session_state and "edited_rows" in str_web.session_state["edytor_rejestru_glownego"]:
                zmiany_rej = str_web.session_state["edytor_rejestru_glownego"]["edited_rows"]
                if zmiany_rej:
                    do_usuniecia_idx = [int(k) for k, v in zmiany_rej.items() if v.get("❌") == True]
                    if do_usuniecia_idx:
                        wpis = str_web.session_state['rejestr_przesuniec_mm'][do_usuniecia_idx[0]]
                        k1 = f"{wpis['Indeks']}_{wpis['Skąd']}"
                        k2 = f"{wpis['Indeks']}_{wpis['Dokąd']}"
                        if k1 in str_web.session_state['wykonane_mm_rozmiary']: str_web.session_state['wykonane_mm_rozmiary'].remove(k1)
                        if k2 in str_web.session_state['wykonane_mm_rozmiary']: str_web.session_state['wykonane_mm_rozmiary'].remove(k2)
                        
                        str_web.session_state['rejestr_przesuniec_mm'].pop(do_usuniecia_idx[0])
                        str_web.rerun()
                        
        with col_rej2:
            excel_globalny = generuj_excel_rejestru(str_web.session_state['rejestr_przesuniec_mm'])
            str_web.download_button(
                label="📥 Pobierz całą historę do Excela",
                data=excel_globalny,
                file_name="Calkowity_Rejestr_MM.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )
    else:
        str_web.info("Rejestr jest pusty. Przejdź do siatek rozmiarowych (🔍) i zatwierdź przesunięcia.")