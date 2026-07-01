"""Shared constants used across the Smart Alert MM application."""

# Magazyny centralne - traktowane inaczej niż zwykłe sklepy w logice rekomendacji
# (nie liczą się jako "sklep docelowy" ani "sklep źródłowy" w analizie zalegania)
MAGAZYNY_CENTRALNE = ['CZM', 'HZA', 'HSN']

# Kursy walut do przeliczenia ceny ewidencyjnej na PLN (używane przy liczeniu marży)
SLOWNIK_KURSOW = {
    'PLN': 1.00, 'EUR': 4.40, 'EU2': 4.40, 'GBP': 6.00, 'GB2': 6.00, 'USD': 4.00, 'US2': 4.00
}

# Kolejność sortowania rozmiarów w masce rozmiarowej (od najmniejszego do największego)
KOLEJNOSC_ROZMIAROW = ['5XS', '4XS', '3XS', '2XS', 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL'] + [str(i) for i in range(1, 100)]

# Nazwy plików danych źródłowych
PLIK_STANY = "stany_surowe.csv"
PLIK_SPRZEDAZ = "sprzedaz_surowa.csv"
PLIK_MINMAX = "min_max.csv"
PLIK_DOSTAWY_BO = "dostawy_bo.csv"
PLIK_REJESTR_MM_2025 = "rejestr_przesuniec_mm_2025.csv"
PLIK_REJESTR_MM_2026 = "rejestr_przesuniec_mm_2026.csv"

# Nazwa folderu z danymi
FOLDER_DANYCH = "Smart_MM"

# Kolory brandowanego eksportu Excela (nagłówek, obramowanie, zebra) -
# używane przez core/excel_export.py, żeby nie były zaszyte w helperach
KOLOR_MARKI_CZERWONY = "E31B23"
KOLOR_OBRAMOWANIA = "E0E0E0"
KOLOR_ZEBRA_JASNY = "F9F9F9"
