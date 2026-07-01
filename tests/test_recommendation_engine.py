"""Unit tests for core.recommendation_engine."""

import datetime
import pandas as pd

from core.recommendation_engine import generuj_rekomendacje_mm


# --- POMOCNICZE BUDOWNICZE WIERSZY (żeby testy niżej były krótkie i czytelne) ---

def wiersz_stanu(indeks, filia, stan, cena=500.0, marza=50.0, producent='MARKA', grupa='GRUPA', status='Aktywny'):
    return {
        'Indeks': indeks, 'Filia': filia, 'Nazwa': f'Produkt {indeks}',
        'Stan_szt': stan, 'Producent': producent, 'Grupa Towarowa': grupa,
        'Status_produktu': status, 'Cena': cena, 'Marza_PLN': marza,
    }


def wiersz_sprzedazy(indeks, filia, ilosc, data='2026-06-25'):
    return {'Indeks': indeks, 'Filia': filia, 'Ilosc_szt': ilosc, 'Data_Transakcji': pd.Timestamp(data)}


def wiersz_minmax(indeks, filia, max_ilosc):
    return {'Indeks': indeks, 'Filia': filia, 'Max_Ilosc': max_ilosc}


def pusty_minmax():
    return pd.DataFrame(columns=['Indeks', 'Filia', 'Max_Ilosc'])


def test_podstawowe_dopasowanie():
    """Sklep S1 ma zalegający towar (stan>0, zero sprzedaży), sklep S2 ma popyt i pustą półkę -> powstaje rekomendacja S1 -> S2."""
    df_stany = pd.DataFrame([
        wiersz_stanu('A1', 'S1', stan=5),
        wiersz_stanu('A1', 'S2', stan=0),
    ])
    df_sprzedaz = pd.DataFrame([
        wiersz_sprzedazy('A1', 'S2', ilosc=3),
    ])

    rekomendacje = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz, pusty_minmax(),
        zakres_dni=30, cena_min=0, marza_min=0, popyt_min=1, dni_karencji=0,
    )

    assert len(rekomendacje) == 1
    wiersz = rekomendacje.iloc[0]
    assert wiersz['Filia'] == 'S1'
    assert wiersz['Filia_Cel'] == 'S2'


def test_wykluczenie_tej_samej_filii():
    """
    Gdy dane źródłowe są niespójne (dwa wiersze stanu dla tej samej pary Indeks+Filia -
    jeden ze stanem, jeden bez), silnik mógłby sparować sklep sam ze sobą.
    Filtr `Filia != Filia_Cel` musi taką rekomendację odrzucić.
    """
    df_stany = pd.DataFrame([
        wiersz_stanu('A1', 'S1', stan=5),   # kwalifikuje S1 jako źródło (zlog)
        wiersz_stanu('A1', 'S1', stan=0),   # ten sam sklep, ale z zerowym stanem - kwalifikuje S1 jako cel (pusta półka)
    ])
    df_sprzedaz = pd.DataFrame([
        wiersz_sprzedazy('A1', 'S1', ilosc=3),
    ])

    rekomendacje = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz, pusty_minmax(),
        zakres_dni=30, cena_min=0, marza_min=0, popyt_min=1, dni_karencji=0,
    )

    assert rekomendacje.empty


def test_karencja_blokuje_swieza_dostawe():
    """Sklep S2 dostał ten towar wczoraj w ramach MM - przy dni_karencji=14 rekomendacja musi zniknąć."""
    df_stany = pd.DataFrame([
        wiersz_stanu('A1', 'S1', stan=5),
        wiersz_stanu('A1', 'S2', stan=0),
    ])
    df_sprzedaz = pd.DataFrame([
        wiersz_sprzedazy('A1', 'S2', ilosc=3),
    ])
    wczoraj = datetime.date.today() - datetime.timedelta(days=1)
    slownik_karencji = {'A1_S2': wczoraj}

    rekomendacje = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz, pusty_minmax(),
        zakres_dni=30, cena_min=0, marza_min=0, popyt_min=1, dni_karencji=14,
        slownik_karencji=slownik_karencji,
    )

    assert rekomendacje.empty


def test_regula_czm_pokrywa_popyt():
    """
    Sklep S2 ma profil MIN-MAX dla towaru A1, a magazyn CZM ma wolny zapas ponad ten profil
    -> uzupełnienie powinno iść zwykłą dostawą z CZM, więc MM między sklepami nie jest rekomendowane.
    """
    df_stany = pd.DataFrame([
        wiersz_stanu('A1', 'S1', stan=5),
        wiersz_stanu('A1', 'S2', stan=0),
        wiersz_stanu('A1', 'CZM', stan=10),
    ])
    df_sprzedaz = pd.DataFrame([
        wiersz_sprzedazy('A1', 'S2', ilosc=3),
    ])
    df_minmax = pd.DataFrame([
        wiersz_minmax('A1', 'S2', max_ilosc=5),   # S2 ma profil MIN-MAX
        wiersz_minmax('A1', 'CZM', max_ilosc=2),  # CZM: stan 10 - max 2 = wolny zapas 8 (> 0)
    ])

    rekomendacje = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz, df_minmax,
        zakres_dni=30, cena_min=0, marza_min=0, popyt_min=1, dni_karencji=0,
    )

    assert rekomendacje.empty


def test_prog_ceny_odrzuca_tani_towar():
    """Zlog poniżej progu cena_min musi odpaść z rekomendacji, mimo że reszta warunków jest spełniona."""
    df_stany = pd.DataFrame([
        wiersz_stanu('A1', 'S1', stan=5, cena=100.0),
        wiersz_stanu('A1', 'S2', stan=0, cena=100.0),
    ])
    df_sprzedaz = pd.DataFrame([
        wiersz_sprzedazy('A1', 'S2', ilosc=3),
    ])

    rekomendacje = generuj_rekomendacje_mm(
        df_stany, df_sprzedaz, pusty_minmax(),
        zakres_dni=30, cena_min=300, marza_min=0, popyt_min=1, dni_karencji=0,
    )

    assert rekomendacje.empty
