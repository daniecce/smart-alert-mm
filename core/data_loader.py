"""Loading and parsing of source CSV files (stany, sprzedaz, min-max, MM history)."""

import os
import pandas as pd
import streamlit as str_web
import datetime

from config.constants import (
    FOLDER_DANYCH, PLIK_STANY, PLIK_SPRZEDAZ, PLIK_MINMAX,
    PLIK_REJESTR_MM_2025, PLIK_REJESTR_MM_2026, SLOWNIK_KURSOW,
)

def pobierz_sciezke_folderu():
    sciezka_core = os.path.dirname(os.path.abspath(__file__))  # .../core
    sciezka_glowna = os.path.dirname(sciezka_core)              # katalog główny projektu
    return os.path.join(sciezka_glowna, FOLDER_DANYCH)

FOLDER_DANYCH_ABS = pobierz_sciezke_folderu()

def zaladuj_baze_karencji_mm():
    """
    Łączy statyczny plik z 2025 roku ('rejestr_przesuniec_mm_2025.csv')
    ze świeżym zrzutem z 2026 roku ('rejestr_przesuniec_mm_2026.csv'),
    wybierając dla każdej pary zawsze najnowszą datę dostawy.
    """
    sciezka_2025 = os.path.join(FOLDER_DANYCH_ABS, PLIK_REJESTR_MM_2025)
    sciezka_2026 = os.path.join(FOLDER_DANYCH_ABS, PLIK_REJESTR_MM_2026)
    slownik_karencji = {}

    # Warunek stopu: plik 2026 jest wymagany na start
    if not os.path.exists(sciezka_2026):
        str_web.warning("⚠️ Brak bieżącego pliku 'rejestr_przesuniec_mm_2026.csv' w folderze Smart_MM. Filtry karencji are inactive.")
        str_web.session_state['slownik_karencji_mm'] = slownik_karencji
        return

    try:
        start_time = datetime.datetime.now()

        # 1. Ładowanie pliku bieżącego (2026)
        df_2026 = pd.read_csv(sciezka_2026, sep=',', dtype={'Filia Kod': str, 'Indeks': str, 'Data MM': str}, engine='c')
        df_2026.columns = [c.strip() for c in df_2026.columns]

        # 2. Ładowanie pliku historycznego (2025) - jeśli istnieje, zostanie automatycznie scalony
        if os.path.exists(sciezka_2025):
            df_2025 = pd.read_csv(sciezka_2025, sep=',', dtype={'Filia Kod': str, 'Indeks': str, 'Data MM': str}, engine='c')
            df_2025.columns = [c.strip() for c in df_2025.columns]
            df_kompletny = pd.concat([df_2025, df_2026], ignore_index=True)
        else:
            df_kompletny = df_2026

        # 3. Twarde czyszczenie danych tekstowych i dat
        df_kompletny['Filia Kod'] = df_kompletny['Filia Kod'].str.strip()
        df_kompletny['Indeks'] = df_kompletny['Indeks'].str.strip()

        df_kompletny['Data_Clean'] = pd.to_datetime(df_kompletny['Data MM'], errors='coerce')
        df_kompletny = df_kompletny.dropna(subset=['Data_Clean'])
        df_kompletny['Data_Clean'] = df_kompletny['Data_Clean'].dt.date

        # Budowanie unikalnego klucza parowania w RAM
        df_kompletny['Klucz'] = df_kompletny['Indeks'] + "_" + df_kompletny['Filia Kod']

        # Chronologiczne sortowanie i odrzucenie starych dubli (zostaje tylko najświeższa data dostawy)
        df_kompletny = df_kompletny.sort_values('Data_Clean').drop_duplicates(subset=['Klucz'], keep='last')

        # Konwersja na ultra-szybki słownik Pythona O(1)
        slownik_karencji = dict(zip(df_kompletny['Klucz'], df_kompletny['Data_Clean']))

        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"[Sukces] Hybrydowa baza dostaw postawiona: {len(slownik_karencji)} par w {duration:.2f} sek.")

    except Exception as e:
        str_web.error(f"🚨 Krytyczny błąd podczas parsuwania plików rejestru MM: {str(e)}")
        slownik_karencji = {}

    str_web.session_state['slownik_karencji_mm'] = slownik_karencji

def zaladuj_i_parsuj_dane():
    sciezka_stany = os.path.join(FOLDER_DANYCH_ABS, PLIK_STANY)
    sciezka_sprzedaz = os.path.join(FOLDER_DANYCH_ABS, PLIK_SPRZEDAZ)
    sciezka_minmax = os.path.join(FOLDER_DANYCH_ABS, PLIK_MINMAX)

    if os.path.exists(sciezka_stany) and os.path.exists(sciezka_sprzedaz) and os.path.exists(sciezka_minmax):
        with str_web.spinner("⏳ Proszę czekać, trwa ładowanie i analiza danych..."):
            try:
                with open(sciezka_stany, 'r', encoding='utf-8') as f_stany, \
                     open(sciezka_sprzedaz, 'r', encoding='utf-8') as f_sprzedaz, \
                     open(sciezka_minmax, 'r', encoding='utf-8') as f_minmax:

                    df_stany_raw = pd.read_csv(f_stany, sep=',', on_bad_lines='skip')
                    df_sprzedaz_raw = pd.read_csv(f_sprzedaz, sep=',', on_bad_lines='skip')
                    df_minmax_raw = pd.read_csv(f_minmax, sep=',', on_bad_lines='skip')

                df_stany_raw.columns = [c.strip() for c in df_stany_raw.columns]
                df_sprzedaz_raw.columns = [c.strip() for c in df_sprzedaz_raw.columns]
                df_minmax_raw.columns = [c.strip() for c in df_minmax_raw.columns]

                # --- PARSOWANIE: STANY SUROWE ---
                df_stany = pd.DataFrame()
                df_stany['Filia'] = df_stany_raw['Filia Kod'].astype(str).str.strip()
                df_stany['Indeks'] = df_stany_raw['Indeks'].astype(str).str.strip()
                df_stany['Nazwa'] = df_stany_raw['Nazwa Towaru'].astype(str).str.strip()
                df_stany['Stan_szt'] = pd.to_numeric(df_stany_raw['Magazyn PJM'], errors='coerce').fillna(0).astype(int)
                df_stany['Producent'] = df_stany_raw['Producent'].astype(str).str.strip()
                df_stany['Grupa Towarowa'] = df_stany_raw['Grupa Towarowa'].astype(str).str.strip()
                df_stany['Status_produktu'] = df_stany_raw['Status'].astype(str).str.strip()

                if 'Cena Detaliczna Netto' in df_stany_raw.columns:
                    df_stany['Cena'] = pd.to_numeric(df_stany_raw['Cena Detaliczna Netto'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                else:
                    df_stany['Cena'] = 0.0

                if 'Cena ewidencyjna' in df_stany_raw.columns and 'Waluta Ceny Ewidencyjnej' in df_stany_raw.columns:
                    cena_ew_surowa = pd.to_numeric(df_stany_raw['Cena ewidencyjna'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)
                    waluta_surowa = df_stany_raw['Waluta Ceny Ewidencyjnej'].astype(str).str.strip().str.upper()
                    kursy_wierszy = waluta_surowa.map(SLOWNIK_KURSOW).fillna(1.00)
                    cena_ew_pln = cena_ew_surowa * kursy_wierszy
                    df_stany['Marza_PLN'] = df_stany['Cena'] - cena_ew_pln
                else:
                    df_stany['Marza_PLN'] = 0.0

                # --- PARSOWANIE: SPRZEDAŻ SUROWA ---
                df_sprzedaz_surowa = pd.DataFrame()
                df_sprzedaz_surowa['Indeks'] = df_sprzedaz_raw['Indeks'].astype(str).str.strip()
                df_sprzedaz_surowa['Filia'] = df_sprzedaz_raw['Filia Kod'].astype(str).str.strip()
                df_sprzedaz_surowa['Data_Transakcji'] = pd.to_datetime(df_sprzedaz_raw['Data'], errors='coerce')
                df_sprzedaz_surowa['Ilosc_szt'] = pd.to_numeric(df_sprzedaz_raw['Sprzedaz PJM'], errors='coerce').fillna(0).astype(int)
                df_sprzedaz_surowa['Nazwa'] = df_sprzedaz_raw['Nazwa Towaru'].astype(str).str.strip()
                df_sprzedaz_surowa['Status_produktu'] = df_sprzedaz_raw['Status'].astype(str).str.strip() if 'Status' in df_sprzedaz_raw.columns else "Aktywny"

                if 'Sprzedaz Netto' in df_sprzedaz_raw.columns:
                    df_sprzedaz_surowa['Wartosc_Netto'] = pd.to_numeric(df_sprzedaz_raw['Sprzedaz Netto'].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce').fillna(0.0)
                else:
                    df_sprzedaz_surowa['Wartosc_Netto'] = 0.0

                if 'Marza' in df_sprzedaz_raw.columns:
                    df_sprzedaz_surowa['Marza_Faktyczna'] = pd.to_numeric(df_sprzedaz_raw['Marza'].astype(str).str.replace(',', '.').str.replace(' ', ''), errors='coerce').fillna(0.0)
                else:
                    df_sprzedaz_surowa['Marza_Faktyczna'] = 0.0

                # --- PARSOWANIE: MIN MAX ---
                df_minmax = pd.DataFrame()
                df_minmax['Indeks'] = df_minmax_raw['Indeks'].astype(str).str.strip()
                df_minmax['Filia'] = df_minmax_raw['Filia Kod'].astype(str).str.strip()
                df_minmax['Max_Ilosc'] = pd.to_numeric(df_minmax_raw['MIN MAX'], errors='coerce').fillna(0).astype(int)

                str_web.session_state['df_stany'] = df_stany
                str_web.session_state['df_sprzedaz_surowa'] = df_sprzedaz_surowa
                str_web.session_state['df_minmax'] = df_minmax

                # 🔵 DOPISANE: Równoległe wywołanie ładowania bazy dostaw i weryfikacja pliku BO
                zaladuj_baze_karencji_mm()

                str_web.session_state['dane_loaded_successfully'] = True
                str_web.session_state['dane_zaladowane'] = True
                str_web.rerun()

            except Exception as e:
                str_web.error(f"❌ Wykryto problem podczas automatycznego odczytu baz: {str(e)}")
    else:
        str_web.warning(f"⏳ Oczekiwanie na komplet plików w folderze OneDrive... Oczekiwana lokalizacja: `{FOLDER_DANYCH_ABS}`")
        str_web.info("Upewnij się, że w folderze znajdują się dokładnie pliki: `stany_surowe.csv`, `sprzedaz_surowa.csv` oraz `min_max.csv`")
        str_web.stop()
