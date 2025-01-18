# RSVPreader

## Opis
RSVPreader to aplikacja umożliwiająca szybkie czytanie książek w formacie EPUB za pomocą metody RSVP. Program wyświetla pojedyncze słowa z ustaloną prędkością, co ułatwia skupienie się na czytanym tekście i eliminuje potrzebę „czytania słów w głowie”.

## Instalacja

### 1. Powołanie środowiska wirtualnego
Zaleca się korzystanie ze środowiska wirtualnego, aby zarządzać zależnościami projektu i uniknąć konfliktów między wersjami bibliotek. Aby utworzyć środowisko wirtualne, wykonaj poniższe kroki:

```bash
python -m venv env
```

Aktywuj środowisko wirtualne:
- Na systemie Linux/macOS:
  ```bash
  source env/bin/activate
  ```
- Na systemie Windows:
  ```bash
  .\env\Scripts\activate
  ```

### 2. Instalacja paczek
Zainstaluj wymagane zależności znajdujące się w pliku `requirements.txt`:

```bash
pip install -r requirements.txt
```

Plik `requirements.txt` zawiera następujące biblioteki:
- `bs4 == 0.0.2`: Do przetwarzania HTML/XML w e-bookach.
- `EbookLib == 0.18`: Do pracy z plikami EPUB.
- `PyQt5 == 5.15.11`: Do stworzenia graficznego interfejsu użytkownika.

## Uruchomienie

Po skonfigurowaniu środowiska i zainstalowaniu zależności aplikację można uruchomić, korzystając z poniższego polecenia w terminalu:

```bash
python app.py
```



