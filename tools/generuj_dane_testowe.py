"""
Generuje syntetyczne dane testowe (stany_surowe.csv, sprzedaz_surowa.csv, min_max.csv)
w folderze Smart_MM/ (obok tego projektu), zgodne ze strukturą kolumn oczekiwaną przez
core/data_loader.py - żeby aplikację dało się uruchomić zaraz po sklonowaniu repo, bez
dostępu do prawdziwych danych firmowych.

⚠️ UWAGA: ten skrypt NADPISUJE stany_surowe.csv, sprzedaz_surowa.csv i min_max.csv w
folderze Smart_MM/. Jeśli w tym folderze są prawdziwe dane Inter Cars - NIE uruchamiaj
tego bez zastanowienia. Skrypt wymaga potwierdzenia (albo ręcznego, albo flagą --force).

Wszystkie dane są w całości zmyślone: generyczne kody sklepów (S01, S02, ..., CZM),
sztuczne indeksy (SKU-001-M, SKU-DEMO-001), losowe stany/sprzedaż/ceny. Zero
jakichkolwiek prawdziwych danych Inter Cars.

Uruchomienie: python tools/generuj_dane_testowe.py [--force]
"""

import argparse
import csv
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_loader import FOLDER_DANYCH_ABS
from config.constants import MAGAZYNY_CENTRALNE, PLIK_STANY, PLIK_SPRZEDAZ, PLIK_MINMAX

SEED = 42
SKLEPY_ZWYKLE = [f"S{str(i).zfill(2)}" for i in range(1, 11)]
ROZMIARY = ['S', 'M', 'L', 'XL', '2XL']
PRODUCENCI = ['MARKA1', 'MARKA2', 'MARKA3', 'MARKA4', 'MARKA5']
GRUPY = ['GRUPA_A', 'GRUPA_B', 'GRUPA_C', 'GRUPA_D']
LICZBA_MODELI = 40
LICZBA_GWARANTOWANYCH = 12

KOLUMNY_STANY = ['Filia Kod', 'Indeks', 'Nazwa Towaru', 'Magazyn PJM', 'Producent', 'Grupa Towarowa', 'Status', 'Cena Detaliczna Netto', 'Cena ewidencyjna', 'Waluta Ceny Ewidencyjnej']
KOLUMNY_SPRZEDAZ = ['Indeks', 'Filia Kod', 'Data', 'Sprzedaz PJM', 'Nazwa Towaru']
KOLUMNY_MINMAX = ['Indeks', 'Filia Kod', 'MIN MAX']


def generuj_modele_tlo(rng):
    """
    Losowe modele produktów (kilka rozmiarów każdy) rozrzucone po sklepach - realistyczny
    szum w danych. Nie ma gwarancji, że coś z tego przejdzie filtry rekomendacji (chociaż
    czasem przypadkiem przejdzie) - o to dba osobno generuj_gwarantowane_rekomendacje().
    """
    stany, sprzedaz, minmax = [], [], []
    wszystkie_filie = SKLEPY_ZWYKLE + MAGAZYNY_CENTRALNE
    dzis = datetime.now().date()

    for i in range(1, LICZBA_MODELI + 1):
        nazwa_modelu = f"Produkt Testowy {i:03d}"
        producent = rng.choice(PRODUCENCI)
        grupa = rng.choice(GRUPY)
        rozmiary_modelu = rng.sample(ROZMIARY, k=rng.randint(3, len(ROZMIARY)))

        for rozmiar in rozmiary_modelu:
            sku = f"SKU-{i:03d}-{rozmiar}"
            nazwa = f"{nazwa_modelu}, rozmiar {rozmiar}"
            cena = round(rng.uniform(50, 2000), 2)
            cena_ewid = round(cena * rng.uniform(0.5, 0.85), 2)
            status = rng.choices(['Aktywny', 'Wyprzedaż', 'Zablokowany'], weights=[0.85, 0.1, 0.05])[0]

            filie_ze_stanem = rng.sample(wszystkie_filie, k=rng.randint(2, 6))
            for filia in filie_ze_stanem:
                stany.append({
                    'Filia Kod': filia, 'Indeks': sku, 'Nazwa Towaru': nazwa,
                    'Magazyn PJM': rng.randint(0, 25), 'Producent': producent, 'Grupa Towarowa': grupa,
                    'Status': status, 'Cena Detaliczna Netto': cena,
                    'Cena ewidencyjna': cena_ewid, 'Waluta Ceny Ewidencyjnej': 'PLN',
                })
                if rng.random() < 0.5:
                    minmax.append({'Indeks': sku, 'Filia Kod': filia, 'MIN MAX': rng.randint(1, 10)})

            filie_ze_sprzedaza = rng.sample(wszystkie_filie, k=rng.randint(1, 4))
            for filia in filie_ze_sprzedaza:
                for _ in range(rng.randint(1, 5)):
                    dni_wstecz = rng.randint(0, 89)
                    sprzedaz.append({
                        'Indeks': sku, 'Filia Kod': filia,
                        'Data': (dzis - timedelta(days=dni_wstecz)).isoformat(),
                        'Sprzedaz PJM': rng.randint(1, 3), 'Nazwa Towaru': nazwa,
                    })

    return stany, sprzedaz, minmax


def generuj_gwarantowane_rekomendacje(rng):
    """
    Jawnie konstruuje pary (sklep źródłowy ze zlogiem, sklep docelowy z popytem), które
    przejdą wszystkie DOMYŚLNE filtry aplikacji przy pierwszym uruchomieniu (zakres 30 dni,
    cena >= 300, marża >= 0, popyt >= 2; karencja jest no-opem, bo ten skrypt nie generuje
    plików rejestru MM) - żeby appka po starcie na pewno pokazała kilka rekomendacji, a nie
    pustą tabelę.

    Dla każdej pary:
    - sklep źródłowy dostaje stan > 0 i CELOWO zero wpisów sprzedaży (zalega),
    - sklep docelowy CELOWO nie dostaje wpisu stanu (pusta półka po fillna(0) przy merge'u)
      ani wpisu w min_max.csv (Ma_Profil=False, więc warunek pokrycia z CZM jest spełniony
      niezależnie od stanu magazynu centralnego), za to dostaje kilka sprzedaży w ostatnich
      ~15 dniach.
    """
    stany, sprzedaz = [], []
    dzis = datetime.now().date()

    for i in range(1, LICZBA_GWARANTOWANYCH + 1):
        sku = f"SKU-DEMO-{i:03d}"
        nazwa = f"Produkt Demo {i:03d}"
        zrodlo, cel = rng.sample(SKLEPY_ZWYKLE, k=2)
        cena = round(rng.uniform(300, 1500), 2)
        cena_ewid = round(cena * 0.6, 2)  # gwarantuje dodatnią marżę (>= 0)

        stany.append({
            'Filia Kod': zrodlo, 'Indeks': sku, 'Nazwa Towaru': nazwa,
            'Magazyn PJM': rng.randint(5, 20), 'Producent': rng.choice(PRODUCENCI),
            'Grupa Towarowa': rng.choice(GRUPY), 'Status': 'Aktywny',
            'Cena Detaliczna Netto': cena, 'Cena ewidencyjna': cena_ewid,
            'Waluta Ceny Ewidencyjnej': 'PLN',
        })

        for _ in range(rng.randint(3, 5)):
            dni_wstecz = rng.randint(1, 15)
            sprzedaz.append({
                'Indeks': sku, 'Filia Kod': cel,
                'Data': (dzis - timedelta(days=dni_wstecz)).isoformat(),
                'Sprzedaz PJM': rng.randint(1, 2), 'Nazwa Towaru': nazwa,
            })

    return stany, sprzedaz


def zapisz_csv(sciezka, wiersze, kolumny):
    with open(sciezka, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=kolumny)
        writer.writeheader()
        writer.writerows(wiersze)


def potwierdz_nadpisanie(folder, force):
    if force:
        return True
    if not os.path.isdir(folder) or not os.listdir(folder):
        return True

    print(f"UWAGA: folder '{folder}' już istnieje i zawiera pliki.")
    print(f"Ten skrypt NADPISZE {PLIK_STANY}, {PLIK_SPRZEDAZ} i {PLIK_MINMAX} w tym folderze.")
    print("Jeśli to Twoje prawdziwe dane firmowe - przerwij teraz (Ctrl+C) i nie kontynuuj.")
    odpowiedz = input("Wpisz TAK, aby kontynuować: ").strip().upper()
    return odpowiedz == "TAK"


def main():
    parser = argparse.ArgumentParser(description="Generuje syntetyczne dane testowe dla Smart Alert MM w folderze Smart_MM/.")
    parser.add_argument('--force', action='store_true', help="Pomija potwierdzenie i nadpisuje pliki bez pytania.")
    args = parser.parse_args()

    if not potwierdz_nadpisanie(FOLDER_DANYCH_ABS, args.force):
        print("Przerwano - nic nie zostało zmienione.")
        sys.exit(1)

    os.makedirs(FOLDER_DANYCH_ABS, exist_ok=True)

    rng = random.Random(SEED)
    stany_tlo, sprzedaz_tlo, minmax = generuj_modele_tlo(rng)
    stany_gwar, sprzedaz_gwar = generuj_gwarantowane_rekomendacje(rng)

    stany = stany_tlo + stany_gwar
    sprzedaz = sprzedaz_tlo + sprzedaz_gwar

    zapisz_csv(os.path.join(FOLDER_DANYCH_ABS, PLIK_STANY), stany, KOLUMNY_STANY)
    zapisz_csv(os.path.join(FOLDER_DANYCH_ABS, PLIK_SPRZEDAZ), sprzedaz, KOLUMNY_SPRZEDAZ)
    zapisz_csv(os.path.join(FOLDER_DANYCH_ABS, PLIK_MINMAX), minmax, KOLUMNY_MINMAX)

    print(f"Gotowe. Zapisano do: {FOLDER_DANYCH_ABS}")
    print(f"  {PLIK_STANY}: {len(stany)} wierszy")
    print(f"  {PLIK_SPRZEDAZ}: {len(sprzedaz)} wierszy")
    print(f"  {PLIK_MINMAX}: {len(minmax)} wierszy")
    print(f"Wśród nich {LICZBA_GWARANTOWANYCH} par SKU-DEMO-*, gwarantowanych do przejścia domyślnych filtrów.")


if __name__ == "__main__":
    main()
