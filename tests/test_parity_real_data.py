"""
Test integracyjny parzystości: porównuje starą logikę main_report.py (skopiowaną tu
1:1, bez streamlita) z core.recommendation_engine, uruchamiając obie na tych samych,
prawdziwych danych firmowych z folderu Smart_MM/.

Dane firmowe nie są w repo (patrz .gitignore), więc na maszynie bez folderu Smart_MM/
ten test jest automatycznie pomijany (skip), a nie failuje.
"""

import os
import datetime
import pandas as pd
import pytest

from core.recommendation_engine import generuj_rekomendacje_mm, zbuduj_raport_grouped

PROJEKT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER_DANYCH = os.environ.get('SMART_MM_DATA_DIR', os.path.join(PROJEKT_ROOT, "Smart_MM"))

WYMAGANE_PLIKI = ['stany_surowe.csv', 'sprzedaz_surowa.csv', 'min_max.csv', 'rejestr_przesuniec_mm_2026.csv']


def dane_dostepne():
    return all(os.path.exists(os.path.join(FOLDER_DANYCH, plik)) for plik in WYMAGANE_PLIKI)


pytestmark = pytest.mark.skipif(
    not dane_dostepne(),
    reason=f"Brak danych firmowych w '{FOLDER_DANYCH}' - test parzystości pomijany (dane nie są w repo)."
)

MAGAZYNY_CENTRALNE = ['CZM', 'HZA', 'HSN']
SLOWNIK_KURSOW = {
    'PLN': 1.00, 'EUR': 4.40, 'EU2': 4.40, 'GBP': 6.00, 'GB2': 6.00, 'USD': 4.00, 'US2': 4.00
}

SCENARIUSZE = [
    dict(nazwa="domyslne_filtry", zakres_dni=30, cena_min=300, marza_min=0, popyt_min=2, dni_karencji=14),
    dict(nazwa="luzne_filtry", zakres_dni=90, cena_min=0, marza_min=-100, popyt_min=1, dni_karencji=0),
    dict(nazwa="ostre_filtry", zakres_dni=60, cena_min=500, marza_min=100, popyt_min=3, dni_karencji=30),
]


# --- WCZYTANIE DANYCH (replika core/data_loader.py, bez zależności od streamlit) ---

def wczytaj_dane():
    sciezka_stany = os.path.join(FOLDER_DANYCH, 'stany_surowe.csv')
    sciezka_sprzedaz = os.path.join(FOLDER_DANYCH, 'sprzedaz_surowa.csv')
    sciezka_minmax = os.path.join(FOLDER_DANYCH, 'min_max.csv')

    with open(sciezka_stany, 'r', encoding='utf-8') as f_stany, \
         open(sciezka_sprzedaz, 'r', encoding='utf-8') as f_sprzedaz, \
         open(sciezka_minmax, 'r', encoding='utf-8') as f_minmax:
        df_stany_raw = pd.read_csv(f_stany, sep=',', on_bad_lines='skip')
        df_sprzedaz_raw = pd.read_csv(f_sprzedaz, sep=',', on_bad_lines='skip')
        df_minmax_raw = pd.read_csv(f_minmax, sep=',', on_bad_lines='skip')

    df_stany_raw.columns = [c.strip() for c in df_stany_raw.columns]
    df_sprzedaz_raw.columns = [c.strip() for c in df_sprzedaz_raw.columns]
    df_minmax_raw.columns = [c.strip() for c in df_minmax_raw.columns]

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

    df_sprzedaz_surowa = pd.DataFrame()
    df_sprzedaz_surowa['Indeks'] = df_sprzedaz_raw['Indeks'].astype(str).str.strip()
    df_sprzedaz_surowa['Filia'] = df_sprzedaz_raw['Filia Kod'].astype(str).str.strip()
    df_sprzedaz_surowa['Data_Transakcji'] = pd.to_datetime(df_sprzedaz_raw['Data'], errors='coerce')
    df_sprzedaz_surowa['Ilosc_szt'] = pd.to_numeric(df_sprzedaz_raw['Sprzedaz PJM'], errors='coerce').fillna(0).astype(int)

    df_minmax = pd.DataFrame()
    df_minmax['Indeks'] = df_minmax_raw['Indeks'].astype(str).str.strip()
    df_minmax['Filia'] = df_minmax_raw['Filia Kod'].astype(str).str.strip()
    df_minmax['Max_Ilosc'] = pd.to_numeric(df_minmax_raw['MIN MAX'], errors='coerce').fillna(0).astype(int)

    return df_stany, df_sprzedaz_surowa, df_minmax


def wczytaj_slownik_karencji():
    sciezka_2025 = os.path.join(FOLDER_DANYCH, 'rejestr_przesuniec_mm_2025.csv')
    sciezka_2026 = os.path.join(FOLDER_DANYCH, 'rejestr_przesuniec_mm_2026.csv')

    df_2026 = pd.read_csv(sciezka_2026, sep=',', dtype={'Filia Kod': str, 'Indeks': str, 'Data MM': str}, engine='c')
    df_2026.columns = [c.strip() for c in df_2026.columns]

    if os.path.exists(sciezka_2025):
        df_2025 = pd.read_csv(sciezka_2025, sep=',', dtype={'Filia Kod': str, 'Indeks': str, 'Data MM': str}, engine='c')
        df_2025.columns = [c.strip() for c in df_2025.columns]
        df_kompletny = pd.concat([df_2025, df_2026], ignore_index=True)
    else:
        df_kompletny = df_2026

    df_kompletny['Filia Kod'] = df_kompletny['Filia Kod'].str.strip()
    df_kompletny['Indeks'] = df_kompletny['Indeks'].str.strip()
    df_kompletny['Data_Clean'] = pd.to_datetime(df_kompletny['Data MM'], errors='coerce')
    df_kompletny = df_kompletny.dropna(subset=['Data_Clean'])
    df_kompletny['Data_Clean'] = df_kompletny['Data_Clean'].dt.date
    df_kompletny['Klucz'] = df_kompletny['Indeks'] + "_" + df_kompletny['Filia Kod']
    df_kompletny = df_kompletny.sort_values('Data_Clean').drop_duplicates(subset=['Klucz'], keep='last')

    return dict(zip(df_kompletny['Klucz'], df_kompletny['Data_Clean']))


# --- STARA LOGIKA (kopia 1:1 z oryginalnego views/main_report.py, linie 207-298) ---

def stara_logika_rekomendacji(df_stany, df_sprzedaz_surowa, df_minmax, *,
                                zakres_dni, cena_min, marza_min, popyt_min, dni_karencji,
                                slownik_karencji, wybrani_producenci, wybrane_grupy, wybrane_statusy):
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

    if dni_karencji > 0:
        dzis = datetime.date.today()

        def zweryfikuj_karencje_wiersza(row):
            klucz = f"{str(row['Indeks']).strip()}_{str(row['Filia_Cel']).strip()}"
            if klucz in slownik_karencji:
                dni_od_dostawy = (dzis - slownik_karencji[klucz]).days
                return (dni_od_dostawy - 1) >= dni_karencji
            return True

        rekomendacje = rekomendacje[rekomendacje.apply(zweryfikuj_karencje_wiersza, axis=1)].copy()

    return rekomendacje


def stary_raport_grouped(rekomendacje):
    if rekomendacje.empty:
        return rekomendacje
    raport_grouped = rekomendacje.groupby([
        'Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu',
        'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM'
    ]).agg({
        'Filia': lambda x: ', '.join(x.unique()),
        'Stan_szt': 'sum'
    }).reset_index()

    raport_grouped = raport_grouped[['Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu', 'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM', 'Filia', 'Stan_szt']]
    return raport_grouped


# --- FIXTURE: dane wczytujemy raz na cały moduł (71k+ wierszy - kosztowne) ---

@pytest.fixture(scope="module")
def dane_rzeczywiste():
    df_stany, df_sprzedaz_surowa, df_minmax = wczytaj_dane()
    slownik_karencji = wczytaj_slownik_karencji()
    return df_stany, df_sprzedaz_surowa, df_minmax, slownik_karencji


@pytest.mark.parametrize("scenariusz", SCENARIUSZE, ids=lambda s: s["nazwa"])
def test_parytet_starej_i_nowej_logiki(dane_rzeczywiste, scenariusz):
    """Stara logika (skopiowana 1:1) i nowy silnik muszą dać identyczny raport_grouped na tych samych danych."""
    df_stany, df_sprzedaz_surowa, df_minmax, slownik_karencji = dane_rzeczywiste

    wspolne_kwargs = dict(
        zakres_dni=scenariusz["zakres_dni"], cena_min=scenariusz["cena_min"], marza_min=scenariusz["marza_min"],
        popyt_min=scenariusz["popyt_min"], dni_karencji=scenariusz["dni_karencji"],
        wybrani_producenci=[], wybrane_grupy=[], wybrane_statusy=[],
    )

    rekomendacje_stare = stara_logika_rekomendacji(
        df_stany, df_sprzedaz_surowa, df_minmax, slownik_karencji=slownik_karencji, **wspolne_kwargs,
    )
    raport_stary = stary_raport_grouped(rekomendacje_stare)

    rekomendacje_nowe = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz_surowa, df_minmax, slownik_karencji=slownik_karencji, **wspolne_kwargs,
    )
    raport_nowy = zbuduj_raport_grouped(rekomendacje_nowe)

    klucz_sortowania = ['Indeks', 'Filia_Cel', 'Filia']
    a = raport_stary.sort_values(klucz_sortowania).reset_index(drop=True)
    b = raport_nowy.sort_values(klucz_sortowania).reset_index(drop=True)

    pd.testing.assert_frame_equal(a, b, check_dtype=False)
