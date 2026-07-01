"""Size-grid screen: store x size matrix for a single product model."""

import streamlit as str_web
import pandas as pd
import datetime
from st_aggrid import AgGrid, JsCode, ColumnsAutoSizeMode

from config.constants import MAGAZYNY_CENTRALNE, KOLEJNOSC_ROZMIAROW

def generuj_plaskie_dane_matrycy(rdzen_opisu, _df_stany, _df_sprzedaz_surowa, _df_minmax, _slownik_karencji, _wykonane_mm, _indeks_startowy, _filia_cel, _wyciagnij_rdzen_po_przecinku, _wyciagnij_czysty_rozmiar):
    df_stany_kopia = _df_stany.copy()
    df_stany_kopia['Rdzen_Tymczasowy'] = df_stany_kopia['Nazwa'].apply(_wyciagnij_rdzen_po_przecinku)
    stany_maski = df_stany_kopia[df_stany_kopia['Rdzen_Tymczasowy'].str.lower() == rdzen_opisu.lower()].copy()

    if stany_maski.empty:
        return None, None, None

    opisy_rozmiarow = stany_maski[['Indeks', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu']].drop_duplicates(subset=['Indeks']).copy()
    opisy_rozmiarow['Czysty_Rozmiar'] = opisy_rozmiarow['Nazwa'].apply(_wyciagnij_czysty_rozmiar)
    opisy_rozmiarow['Czysty_Rozmiar'] = pd.Categorical(opisy_rozmiarow['Czysty_Rozmiar'], categories=KOLEJNOSC_ROZMIAROW, ordered=True)
    opisy_rozmiarow = opisy_rozmiarow.sort_values(by='Czysty_Rozmiar', na_position='last')

    unikalne_filie = sorted([f for f in _df_stany['Filia'].unique() if f not in MAGAZYNY_CENTRALNE])
    wszystkie_filie = MAGAZYNY_CENTRALNE + unikalne_filie

    plaskie_dane = []
    lista_sku_modelu = []
    dzis = datetime.date.today()

    for _, row_item in opisy_rozmiarow.iterrows():
        sku = row_item['Indeks']
        lista_sku_modelu.append(sku)

        rekord = {
            'Indeks': sku,
            'Nazwa Produktu': row_item['Nazwa'],
            'Cena Netto': f"{row_item['Cena']:.2f} PLN",
            'Marża Netto': f"{row_item['Marza_PLN']:.2f} PLN",
            'Status': str(row_item['Status_produktu']).strip(),
            'Startowy_Indeks': str(_indeks_startowy).strip(),
            'Sklep_Cel': str(_filia_cel).strip()
        }

        for filia in wszystkie_filie:
            stan_filii = _df_stany[(_df_stany['Indeks'] == sku) & (_df_stany['Filia'] == filia)]['Stan_szt'].sum()
            df_mm_filia = _df_minmax[(_df_minmax['Indeks'] == sku) & (_df_minmax['Filia'] == filia)]
            minmax_filii = df_mm_filia['Max_Ilosc'].sum() if not df_mm_filia.empty else 0

            transakcje_sprzedazy = _df_sprzedaz_surowa[(_df_sprzedaz_surowa['Indeks'] == sku) & (_df_sprzedaz_surowa['Filia'] == filia)]
            sprzedaz_filii = transakcje_sprzedazy['Ilosc_szt'].sum()

            if not transakcje_sprzedazy.empty and sprzedaz_filii > 0:
                ost_data_sprzedazy = transakcje_sprzedazy['Data_Transakcji'].max().strftime('%d.%m.%Y')
                tooltip_sprzedaz = f"Ostatnia sprzedaż: {ost_data_sprzedazy}"
            else:
                tooltip_sprzedaz = "Brak sprzedaży w okresie"

            klucz_parowania = f"{sku}_{filia}"
            dni_zalegania = 0

            if klucz_parowania in _slownik_karencji:
                data_dostawy = _slownik_karencji[klucz_parowania]
                if isinstance(data_dostawy, (datetime.date, datetime.datetime)):
                    if isinstance(data_dostawy, datetime.datetime):
                        data_dostawy = data_dostawy.date()
                    dni_zalegania = (dzis - data_dostawy).days
                data_dostawy_str = data_dostawy.strftime('%d.%m.%Y') if isinstance(data_dostawy, (datetime.date, datetime.datetime)) else str(data_dostawy)
                tooltip_stan = f"Towar na filii od dostawy MM w dniu: {data_dostawy_str} (Zalega: {dni_zalegania} dni)"
            else:
                tooltip_stan = "Brak historii przyjęć MM dla tego indeksu na ten sklep."

            rekord[f"{filia}_Wykonane"] = True if klucz_parowania in _wykonane_mm else False
            rekord[f"{filia}_Stan"] = int(stan_filii) if stan_filii > 0 else 0
            rekord[f"{filia}_Sprzedaz"] = int(sprzedaz_filii) if sprzedaz_filii > 0 else 0
            rekord[f"{filia}_MinMax"] = int(minmax_filii) if minmax_filii > 0 else 0

            rekord[f"{filia}_TooltipSprzedaz"] = tooltip_sprzedaz
            rekord[f"{filia}_TooltipStan"] = tooltip_stan
            rekord[f"{filia}_DniZalegania"] = int(dni_zalegania)

        plaskie_dane.append(rekord)

    return pd.DataFrame(plaskie_dane), wszystkie_filie, lista_sku_modelu

def wyswietl_karte_rozmiarowa(stylizuj_matryce_logistycznie, wyciagnij_czysty_rozmiar, wyciagnij_rdzen_po_przecinku, eksport_karty_maski):
    rdzen_opisu = str_web.session_state['wybrany_rdzen_opisu']
    indeks_startowy = str_web.session_state['klikniety_indeks_startowy']
    filia_cel_startowa = str_web.session_state.get('klikniety_cel', '')
    klikniete_zrodla = [str(x).strip() for x in str_web.session_state.get('klikniete_zrodla', [])]

    if str_web.button("◀ POWRÓT DO GŁÓWNEGO RAPORTU MM", width="stretch"):
        str_web.session_state['aktywny_ekran'] = "glowny"
        str_web.session_state['wybrany_rdzen_opisu'] = None
        str_web.session_state['klikniety_indeks_startowy'] = None
        str_web.session_state['klikniety_cel'] = None
        str_web.session_state['klikniete_zrodla'] = None
        str_web.session_state.pop('df_plaski_cache', None)
        str_web.rerun()

    str_web.subheader("📊 Maska Rozmiarowa")
    str_web.markdown(f"**Model:** `{rdzen_opisu}`")

    df_stany = str_web.session_state['df_stany']
    df_sprzedaz_surowa = str_web.session_state['df_sprzedaz_surowa']
    df_minmax = str_web.session_state['df_minmax']
    slownik_karencji = str_web.session_state.get('slownik_karencji_mm', {})
    wykonane_mm = str_web.session_state.get('wykonane_mm_rozmiary', [])

    if 'df_plaski_cache' not in str_web.session_state:
        df_plaski, wszystkie_filie, lista_sku_modelu = generuj_plaskie_dane_matrycy(
            rdzen_opisu, df_stany, df_sprzedaz_surowa, df_minmax, slownik_karencji, wykonane_mm,
            indeks_startowy, filia_cel_startowa, wyciagnij_rdzen_po_przecinku, wyciagnij_czysty_rozmiar
        )
        str_web.session_state['df_plaski_cache'] = df_plaski
        str_web.session_state['wszystkie_filie_cache'] = wszystkie_filie
        str_web.session_state['lista_sku_cache'] = lista_sku_modelu
    else:
        df_plaski = str_web.session_state['df_plaski_cache']
        wszystkie_filie = str_web.session_state['wszystkie_filie_cache']
        lista_sku_modelu = str_web.session_state['lista_sku_cache']

    if df_plaski is None or df_plaski.empty:
        str_web.error("Brak danych dla tej pozycji.")
        str_web.stop()

    js_zrodla_array = str(klikniete_zrodla)

    js_kolorowanie_indeksu = JsCode("""
    function(params) {
        if (params.data && params.value === params.data.Startowy_Indeks) {
            return {'backgroundColor': '#2ECC71', 'color': '#FFFFFF', 'fontWeight': 'bold', 'border': '1px solid #27AE60', 'textAlign': 'left'};
        }
        return {'border': '1px solid #E0E0E0', 'textAlign': 'left'};
    }
    """)

    js_formatuj_zero = JsCode("""
    function(params) {
        return (params.value === 0 || params.value === null) ? '' : params.value;
    }
    """)

    js_kolorowanie_stanu = JsCode(f"""
    function(params) {{
        let filia = params.colDef.field.split('_')[0];
        let sprzedaz = params.data[filia + '_Sprzedaz'];
        let wykonane = params.data[filia + '_Wykonane'];
        let zrodlaRekorowe = {js_zrodla_array};

        let statusCzysty = params.data.Status ? params.data.Status.toString().trim().toLowerCase() : "";
        let defBorders = {{'borderLeft': '2px solid #17202A', 'borderRight': '1px solid #E0E0E0', 'borderTop': '1px solid #E0E0E0', 'borderBottom': '1px solid #E0E0E0'}};

        if (statusCzysty === "zablokowany" || statusCzysty === "archiwalny" || statusCzysty === "wyprzedaż") {{
            return Object.assign({{'backgroundColor': '#E5E7E9', 'color': '#95A5A6', 'fontStyle': 'italic', 'textAlign': 'center'}}, defBorders);
        }}

        let style = Object.assign({{'textAlign': 'center'}}, defBorders);

        if (wykonane === true) {{
            style['backgroundColor'] = '#2980B9';
            style['color'] = '#FFFFFF';
            style['fontWeight'] = 'bold';
            return style;
        }}
        if (params.value > 0 && (sprzedaz === 0 || sprzedaz === null)) {{
            style['backgroundColor'] = '#FADBD8';
            style['color'] = '#78281F';
            style['fontWeight'] = 'bold';
            if (params.data.Indeks === params.data.Startowy_Indeks && zrodlaRekorowe.includes(filia)) {{
                style['border'] = '3px solid #E74C3C';
            }}
        }}
        return style;
    }}
    """)

    js_kolorowanie_sprzedazy = JsCode(f"""
    function(params) {{
        let filia = params.colDef.field.split('_')[0];
        let stan = params.data[filia + '_Stan'];
        let wykonane = params.data[filia + '_Wykonane'];

        let statusCzysty = params.data.Status ? params.data.Status.toString().trim().toLowerCase() : "";
        let defBorders = {{'borderLeft': '1px solid #E0E0E0', 'borderRight': '1px solid #E0E0E0', 'borderTop': '1px solid #E0E0E0', 'borderBottom': '1px solid #E0E0E0'}};

        if (statusCzysty === "zablokowany" || statusCzysty === "archiwalny" || statusCzysty === "wyprzedaż") {{
            return Object.assign({{'backgroundColor': '#E5E7E9', 'color': '#95A5A6', 'fontStyle': 'italic', 'textAlign': 'center'}}, defBorders);
        }}

        let style = Object.assign({{'textAlign': 'center'}}, defBorders);

        if (wykonane === true) {{
            style['backgroundColor'] = '#2980B9';
            style['color'] = '#FFFFFF';
            style['fontWeight'] = 'bold';
            return style;
        }}
        if (params.value > 0 && (stan === 0 || stan === null)) {{
            style['backgroundColor'] = '#D4EFDF';
            style['color'] = '#196F3D';
            style['fontWeight'] = 'bold';
            if (params.data.Indeks === params.data.Startowy_Indeks && filia === params.data.Sklep_Cel) {{
                style['border'] = '3px solid #2ECC71';
            }}
        }}
        return style;
    }}
    """)

    js_pobierz_tooltip_stanu = JsCode("function(params) { let filia = params.colDef.field.split('_')[0]; return params.data[filia + '_TooltipStan']; }")
    js_pobierz_tooltip_sprzedazy = JsCode("function(params) { let filia = params.colDef.field.split('_')[0]; return params.data[filia + '_TooltipSprzedaz']; }")

    column_defs = [
        {"headerName": "Indeks", "field": "Indeks", "pinned": "left", "width": 160, "minWidth": 160, "cellStyle": js_kolorowanie_indeksu},
        {"headerName": "Nazwa Produktu", "field": "Nazwa Produktu", "pinned": "left", "width": 240, "minWidth": 200, "cellStyle": {'border': '1px solid #E0E0E0', 'textAlign': 'left'}},
        {"headerName": "Cena Netto", "field": "Cena Netto", "pinned": "left", "width": 110, "cellStyle": {'textAlign': 'center', 'border': '1px solid #E0E0E0'}},
        {"headerName": "Marża Netto", "field": "Marża Netto", "pinned": "left", "width": 110, "cellStyle": {'textAlign': 'center', 'border': '1px solid #E0E0E0'}},
        {"headerName": "Status", "field": "Status", "pinned": "left", "width": 100, "cellStyle": {'textAlign': 'center', 'borderTop': '1px solid #E0E0E0', 'borderBottom': '1px solid #E0E0E0', 'borderLeft': '1px solid #E0E0E0', 'borderRight': '2px solid #17202A'}}
    ]

    for filia in wszystkie_filie:
        grupa_filii = {
            "headerName": filia,
            "marryChildren": True,
            "children": [
                {"headerName": "Stan", "field": f"{filia}_Stan", "width": 75, "minWidth": 75, "cellStyle": js_kolorowanie_stanu, "tooltipValueGetter": js_pobierz_tooltip_stanu, "valueFormatter": js_formatuj_zero},
                {"headerName": "Sprzedaż", "field": f"{filia}_Sprzedaz", "width": 90, "minWidth": 90, "cellStyle": js_kolorowanie_sprzedazy, "tooltipValueGetter": js_pobierz_tooltip_sprzedazy, "valueFormatter": js_formatuj_zero},
                {"headerName": "MIN MAX", "field": f"{filia}_MinMax", "width": 95, "minWidth": 95, "cellStyle": {'textAlign': 'center', 'borderTop': '1px solid #E0E0E0', 'borderBottom': '1px solid #E0E0E0', 'borderLeft': '1px solid #E0E0E0', 'borderRight': '2px solid #17202A'}, "valueFormatter": js_formatuj_zero}
            ]
        }
        column_defs.append(grupa_filii)

    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {"resizable": True, "sortable": True},
        "tooltipShowDelay": 0,
        "enableCellTextSelection": True,
        "ensureDomOrder": True,
        "suppressClipboardApi": True,
        "suppressSizeToFit": True,
        "domLayout": "autoHeight"
    }

    AgGrid(
        df_plaski,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        theme="alpine",
        columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE
    )

    # --- PANEL REJESTRACJI I USUWANIA MM ---
    str_web.markdown("---")
    str_web.subheader("🔵 Panel rejestracji wykonanych przesunięć MM")

    with str_web.form(key="formularz_mm"):
        col_form1, col_form2, col_form3 = str_web.columns(3)

        with col_form1:
            def_idx = lista_sku_modelu.index(indeks_startowy) if indeks_startowy in lista_sku_modelu else 0
            wybrane_mm_sku = str_web.selectbox("Wybierz rozmiar (Indeks):", options=lista_sku_modelu, index=def_idx)

        with col_form2:
            wybrana_mm_zrodlo = str_web.selectbox("Skąd:", options=wszystkie_filie)

        with col_form3:
            def_cel_idx = wszystkie_filie.index(filia_cel_startowa) if filia_cel_startowa in wszystkie_filie else 0
            wybrana_mm_cel = str_web.selectbox("Dokąd:", options=wszystkie_filie, index=def_cel_idx)

        zatwierdz_klikniete = str_web.form_submit_button("🔵 Zatwierdź MM", width="stretch")

        if zatwierdz_klikniete:
            klucz_zrodlo = f"{wybrane_mm_sku}_{wybrana_mm_zrodlo}"
            klucz_cel = f"{wybrane_mm_sku}_{wybrana_mm_cel}"

            if klucz_zrodlo not in str_web.session_state['wykonane_mm_rozmiary']:
                str_web.session_state['wykonane_mm_rozmiary'].append(klucz_zrodlo)
            if klucz_cel not in str_web.session_state['wykonane_mm_rozmiary']:
                str_web.session_state['wykonane_mm_rozmiary'].append(klucz_cel)

            # 🟢 POBIERANIE WYLICZONYCH DNI ZALEGANIA DLA WYBRANEJ FILII ŹRÓDŁOWEJ
            wiersz_sku = df_plaski[df_plaski['Indeks'] == wybrane_mm_sku]
            wyliczone_dni = 0
            if not wiersz_sku.empty:
                pole_dni = f"{wybrana_mm_zrodlo}_DniZalegania"
                if pole_dni in wiersz_sku.columns:
                    wyliczone_dni = int(wiersz_sku[pole_dni].iloc[0])

            str_web.session_state['rejestr_przesuniec_mm'].append({
                'Indeks': wybrane_mm_sku,
                'Skąd': wybrana_mm_zrodlo,
                'Dokąd': wybrana_mm_cel,
                'Dni na filii': wyliczone_dni
            })

            if 'df_plaski_cache' in str_web.session_state:
                str_web.session_state['df_plaski_cache'].loc[
                    str_web.session_state['df_plaski_cache']['Indeks'] == wybrane_mm_sku,
                    [f"{wybrana_mm_zrodlo}_Wykonane", f"{wybrana_mm_cel}_Wykonane"]
                ] = True

            str_web.toast(f"✅ Zarejestrowano MM dla {wybrane_mm_sku}! (Zalegał: {wyliczone_dni} dni)", icon="🔵")
            str_web.rerun()

    # --- USUWANIE LOKALNE WPISÓW MODELU ---
    lokalne_transakcje = [t for t in str_web.session_state['rejestr_przesuniec_mm'] if t['Indeks'] in lista_sku_modelu]
    if lokalne_transakcje:
        str_web.markdown("**Przesunięcia zarejestrowane dla tego modelu (Możesz usunąć za pomocą ❌):**")
        df_lokalny_widok = pd.DataFrame(lokalne_transakcje).copy()
        df_lokalny_widok['❌'] = False

        kolumny_widoku = ['❌', 'Indeks', 'Skąd', 'Dokąd']
        if 'Dni na filii' in df_lokalny_widok.columns:
            kolumny_widoku.append('Dni na filii')

        df_lokalny_widok = df_lokalny_widok[kolumny_widoku]

        col_lok_tabelka, col_lok_przycisk = str_web.columns([3, 1])
        with col_lok_tabelka:
            edytor_lokalny = str_web.data_editor(
                df_lokalny_widok, width="stretch", hide_index=True,
                key="edytor_rejestru_lokalnego", disabled=['Indeks', 'Skąd', 'Dokąd', 'Dni na filii'],
                column_config={"❌": str_web.column_config.CheckboxColumn("❌", width=45)}
            )

            if "edytor_rejestru_lokalnego" in str_web.session_state and "edited_rows" in str_web.session_state["edytor_rejestru_lokalnego"]:
                zmiany_lok = str_web.session_state["edytor_rejestru_lokalnego"]["edited_rows"]
                if zmiany_lok:
                    id_do_wywalenia_lok = [int(k) for k, v in zmiany_lok.items() if v.get("❌") == True]
                    if id_do_wywalenia_lok:
                        wpis_lok = lokalne_transakcje[id_do_wywalenia_lok[0]]
                        k1_l = f"{wpis_lok['Indeks']}_{wpis_lok['Skąd']}"
                        k2_l = f"{wpis_lok['Indeks']}_{wpis_lok['Dokąd']}"

                        if k1_l in str_web.session_state['wykonane_mm_rozmiary']: str_web.session_state['wykonane_mm_rozmiary'].remove(k1_l)
                        if k2_l in str_web.session_state['wykonane_mm_rozmiary']: str_web.session_state['wykonane_mm_rozmiary'].remove(k2_l)

                        if 'df_plaski_cache' in str_web.session_state:
                            str_web.session_state['df_plaski_cache'].loc[
                                str_web.session_state['df_plaski_cache']['Indeks'] == wpis_lok['Indeks'],
                                [f"{wpis_lok['Skąd']}_Wykonane", f"{wpis_lok['Dokąd']}_Wykonane"]
                            ] = False

                        str_web.session_state['rejestr_przesuniec_mm'].remove(wpis_lok)
                        str_web.rerun()

        with col_lok_przycisk:
            df_rejestr_lok = pd.DataFrame(lokalne_transakcje)
            kolumny_eksportu = ['Indeks', 'Skąd', 'Dokąd']
            if not df_rejestr_lok.empty and 'Dni na filii' in df_rejestr_lok.columns:
                kolumny_eksportu.append('Dni na filii')

            if df_rejestr_lok.empty:
                df_rejestr_lok = pd.DataFrame(columns=kolumny_eksportu)
            else:
                df_rejestr_lok = df_rejestr_lok[kolumny_eksportu]

            from io import BytesIO
            output_lok = BytesIO()
            with pd.ExcelWriter(output_lok, engine='openpyxl') as writer:
                df_rejestr_lok.to_excel(writer, index=False, sheet_name="Model MM")
                worksheet = writer.sheets["Model MM"]
                from openpyxl.styles import Font
                for cell in worksheet[1]:
                    cell.font = Font(name="Segoe UI", size=11, bold=True)

            excel_lokalny = output_lok.getvalue()

            str_web.download_button(
                label="📥 Pobierz MM tego modelu", data=excel_lokalny,
                file_name=f"MM_Modelu_{rdzen_opisu}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )

    cols_to_drop = ['Startowy_Indeks', 'Sklep_Cel']
    for filia in wszystkie_filie:
        cols_to_drop.extend([f"{filia}_Wykonane", f"{filia}_TooltipSprzedaz", f"{filia}_TooltipStan", f"{filia}_DniZalegania"])

    df_eksport = df_plaski.drop(columns=cols_to_drop, errors='ignore').copy()
    raw_excel_maska = eksport_karty_maski(df_eksport)

    str_web.download_button(
        label="📥 Pobierz całą siatkę rozmiarową tego modelu do Excela",
        data=raw_excel_maska,
        file_name=f"Maska_Wielopoziomowa_{indeks_startowy}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch"
    )
