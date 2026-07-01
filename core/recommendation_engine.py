"""Pure pandas business logic for generating MM (inter-store transfer) recommendations.

No streamlit imports here - only pandas and stdlib, so the logic stays unit-testable.

Reguła biznesowa w skrócie: towar "zalega" w jednym sklepie (jest na stanie, zero
sprzedaży w oknie analizy, cena/marża powyżej progu filtra), a jednocześnie ma popyt
w innym sklepie (sprzedaje się, ale półka pusta), i nie da się go uzupełnić z zapasu
magazynu centralnego CZM. Dodatkowo odrzucamy rekomendacje objęte "karencją" - czyli
świeżo dostarczone do sklepu docelowego w ramach wcześniejszego MM.
"""

import datetime
import pandas as pd

from config.constants import MAGAZYNY_CENTRALNE


def oblicz_sprzedaz_zagregowana(df_sprzedaz_surowa, zakres_dni):
    """Sumuje sprzedaż z ostatnich `zakres_dni` dni (licząc od najnowszej transakcji) per (Indeks, Filia)."""
    najnowsza_data = df_sprzedaz_surowa['Data_Transakcji'].max()
    data_graniczna = najnowsza_data - pd.Timedelta(days=zakres_dni)

    df_sprzedaz_okresowa = df_sprzedaz_surowa[df_sprzedaz_surowa['Data_Transakcji'] >= data_graniczna]
    df_sprzedaz_zagregowana = df_sprzedaz_okresowa.groupby(['Indeks', 'Filia'])['Ilosc_szt'].sum().reset_index()
    df_sprzedaz_zagregowana.rename(columns={'Ilosc_szt': 'Sprzedaz_szt'}, inplace=True)
    return df_sprzedaz_zagregowana


def oczysc_minmax(df_minmax):
    """Usuwa duplikaty (Indeks, Filia) z tabeli MIN MAX - zostaje jeden wiersz na parę."""
    return df_minmax.drop_duplicates(subset=['Indeks', 'Filia']).copy()


def oblicz_wolny_zapas_czm(df_stany, df_minmax_clean):
    """
    Liczy wolny zapas magazynu centralnego CZM per Indeks:
    Wolny_Zapas_CZM = Stan_CZM - Max_CZM, przycięty do 0 gdy wynik ujemny.
    """
    df_czm_stan = df_stany[df_stany['Filia'] == 'CZM'][['Indeks', 'Stan_szt']].copy()
    df_czm_stan.rename(columns={'Stan_szt': 'Stan_CZM'}, inplace=True)

    df_czm_max = df_minmax_clean[df_minmax_clean['Filia'] == 'CZM'][['Indeks', 'Max_Ilosc']].copy()
    df_czm_max.rename(columns={'Max_Ilosc': 'Max_CZM'}, inplace=True)

    df_czm_logistyka = pd.merge(df_czm_stan, df_czm_max, on='Indeks', how='left')
    df_czm_logistyka['Stan_CZM'] = df_czm_logistyka['Stan_CZM'].fillna(0)
    df_czm_logistyka['Max_CZM'] = df_czm_logistyka['Max_CZM'].fillna(0)
    df_czm_logistyka['Wolny_Zapas_CZM'] = df_czm_logistyka['Stan_CZM'] - df_czm_logistyka['Max_CZM']
    df_czm_logistyka.loc[df_czm_logistyka['Wolny_Zapas_CZM'] < 0, 'Wolny_Zapas_CZM'] = 0
    return df_czm_logistyka


def oblicz_zlogi(df_stany, df_sprzedaz_zagregowana, *,
                  wybrani_producenci=None, wybrane_grupy=None, wybrane_statusy=None,
                  cena_min=0, marza_min=0):
    """
    Znajduje "zalegający towar": stan > 0, brak sprzedaży w oknie analizy,
    cena i marża powyżej progów filtra. Wyklucza magazyny centralne.
    """
    df_sklepy_stany = df_stany[~df_stany['Filia'].isin(MAGAZYNY_CENTRALNE)].copy()
    df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Stan_szt'] > 0]

    if wybrani_producenci:
        df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Producent'].isin(wybrani_producenci)]
    if wybrane_grupy:
        df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Grupa Towarowa'].isin(wybrane_grupy)]
    if wybrane_statusy:
        df_sklepy_stany = df_sklepy_stany[df_sklepy_stany['Status_produktu'].isin(wybrane_statusy)]

    baza_zrodlowa = pd.merge(df_sklepy_stany, df_sprzedaz_zagregowana, on=['Indeks', 'Filia'], how='left')
    baza_zrodlowa['Sprzedaz_szt'] = baza_zrodlowa['Sprzedaz_szt'].fillna(0)

    zlogi = baza_zrodlowa[
        (baza_zrodlowa['Stan_szt'] > 0) &
        (baza_zrodlowa['Sprzedaz_szt'] == 0) &
        (baza_zrodlowa['Cena'] >= cena_min) &
        (baza_zrodlowa['Marza_PLN'] >= marza_min)
    ]
    return zlogi


def oblicz_popyt_uzasadniony(df_stany, df_sprzedaz_zagregowana, df_minmax_clean, df_czm_logistyka, popyt_min):
    """
    Znajduje sklepy z popytem (sprzedaż >= popyt_min) i pustą półką (stan == 0),
    dla których uzupełnienie z CZM nie jest zasadne (brak profilu MIN MAX na sklepie
    albo brak wolnego zapasu w CZM).
    """
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

    popyt_matryca = pd.merge(
        popyt_pusta_polka,
        df_minmax_sklepy[['Indeks', 'Filia', 'Ma_Profil', 'Max_Ilosc']],
        left_on=['Indeks', 'Filia_Cel'], right_on=['Indeks', 'Filia'], how='left'
    )
    if 'Filia' in popyt_matryca.columns:
        popyt_matryca.drop(columns=['Filia'], inplace=True)
    popyt_matryca['Ma_Profil'] = popyt_matryca['Ma_Profil'].fillna(False)
    popyt_matryca['Max_Ilosc'] = popyt_matryca['Max_Ilosc'].fillna(0)

    popyt_weryfikacja_czm = pd.merge(
        popyt_matryca,
        df_czm_logistyka[['Indeks', 'Stan_CZM', 'Max_CZM', 'Wolny_Zapas_CZM']],
        on='Indeks', how='left'
    )
    popyt_weryfikacja_czm['Stan_CZM'] = popyt_weryfikacja_czm['Stan_CZM'].fillna(0)
    popyt_weryfikacja_czm['Max_CZM'] = popyt_weryfikacja_czm['Max_CZM'].fillna(0)
    popyt_weryfikacja_czm['Wolny_Zapas_CZM'] = popyt_weryfikacja_czm['Wolny_Zapas_CZM'].fillna(0)

    popyt_uzasadniony = popyt_weryfikacja_czm[
        (popyt_weryfikacja_czm['Ma_Profil'] == False) | (popyt_weryfikacja_czm['Wolny_Zapas_CZM'] == 0)
    ]
    return popyt_uzasadniony


def odfiltruj_wedlug_karencji(rekomendacje, slownik_karencji, dni_karencji):
    """
    Odrzuca rekomendacje dla par (Indeks, Filia_Cel), które otrzymały towar w ramach MM
    w ciągu ostatnich `dni_karencji` dni (na podstawie historycznej bazy dostaw).
    """
    if dni_karencji <= 0 or not slownik_karencji:
        return rekomendacje

    dzis = datetime.date.today()

    def zweryfikuj_karencje_wiersza(row):
        klucz = f"{str(row['Indeks']).strip()}_{str(row['Filia_Cel']).strip()}"
        if klucz in slownik_karencji:
            dni_od_dostawy = (dzis - slownik_karencji[klucz]).days
            return (dni_od_dostawy - 1) >= dni_karencji
        return True

    return rekomendacje[rekomendacje.apply(zweryfikuj_karencje_wiersza, axis=1)].copy()


def generuj_rekomendacje_mm(
    df_stany, df_sprzedaz_surowa, df_minmax, *,
    zakres_dni, cena_min, marza_min, popyt_min, dni_karencji,
    slownik_karencji=None,
    wybrani_producenci=None, wybrane_grupy=None, wybrane_statusy=None,
):
    """
    Główna funkcja silnika rekomendacji MM (przesunięć międzymagazynowych).

    Łączy zalegający towar (zlogi) z uzasadnionym popytem w innych sklepach i odrzuca
    pary objęte karencją. Zwraca DataFrame na poziomie wiersza (jeden wiersz = jedna
    para zlogu i popytu), gotowy do dalszego grupowania przez `zbuduj_raport_grouped`.
    """
    slownik_karencji = slownik_karencji or {}

    df_sprzedaz_zagregowana = oblicz_sprzedaz_zagregowana(df_sprzedaz_surowa, zakres_dni)
    df_minmax_clean = oczysc_minmax(df_minmax)
    df_czm_logistyka = oblicz_wolny_zapas_czm(df_stany, df_minmax_clean)

    zlogi = oblicz_zlogi(
        df_stany, df_sprzedaz_zagregowana,
        wybrani_producenci=wybrani_producenci, wybrane_grupy=wybrane_grupy, wybrane_statusy=wybrane_statusy,
        cena_min=cena_min, marza_min=marza_min,
    )
    popyt_uzasadniony = oblicz_popyt_uzasadniony(
        df_stany, df_sprzedaz_zagregowana, df_minmax_clean, df_czm_logistyka, popyt_min
    )

    rekomendacje = pd.merge(zlogi, popyt_uzasadniony, on='Indeks')
    rekomendacje = rekomendacje[rekomendacje['Filia'] != rekomendacje['Filia_Cel']]

    rekomendacje = odfiltruj_wedlug_karencji(rekomendacje, slownik_karencji, dni_karencji)

    return rekomendacje


def zbuduj_raport_grouped(rekomendacje):
    """
    Grupuje rekomendacje wierszowe do jednego wiersza na (Indeks, Filia_Cel):
    łączy sklepy źródłowe w listę i sumuje ich stan.

    Uwaga: zwraca kolumny jeszcze w nazwach roboczych (Indeks, Filia_Cel, Nazwa, ...),
    bez rename/sortowania/konwersji liczb. To celowe - warstwa widoku dokłada tu
    kolumny checkboxów (🔍/✅) i BO na tych roboczych nazwach (np. `Filia_Cel`), a
    dopiero potem robi finalne przemianowanie i sortowanie na całości. Ich rozdzielenie
    tutaj popsułoby kolejność kolumn, od której zależy układ grup w AgGrid.
    """
    if rekomendacje.empty:
        return rekomendacje

    raport_grouped = rekomendacje.groupby([
        'Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu',
        'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM'
    ]).agg({
        'Filia': lambda x: ', '.join(x.unique()),
        'Stan_szt': 'sum'
    }).reset_index()

    raport_grouped = raport_grouped[[
        'Indeks', 'Producent', 'Nazwa', 'Cena', 'Marza_PLN', 'Status_produktu',
        'Filia_Cel', 'Sprzedaz_Cel', 'Max_Ilosc', 'Stan_CZM', 'Max_CZM', 'Filia', 'Stan_szt'
    ]]

    return raport_grouped
