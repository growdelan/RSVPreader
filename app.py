import os
import sys
import time
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QLabel, QSlider, QFileDialog, QHBoxLayout, QProgressBar, QDialog, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap  # Dodane do obsługi okładki
from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE
from bs4 import BeautifulSoup

# Plik JSON przechowujący postęp czytania dla poszczególnych książek
PROGRESS_JSON = "reading_progress.json"

# Plik JSON przechowujący globalne ustawienia aplikacji (np. prędkość, czcionkę)
SETTINGS_JSON = "app_settings.json"

def load_all_progress():
    """
    Wczytuje z pliku JSON (PROGRESS_JSON) słownik z postępami czytania.
    Jeśli plik nie istnieje lub jest niepoprawny, zwraca pusty słownik.
    """
    if os.path.exists(PROGRESS_JSON):
        try:
            with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_all_progress(data):
    """
    Zapisuje w pliku JSON (PROGRESS_JSON) słownik z postępami czytania.
    """
    with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_progress(file_path):
    """
    Zwraca zapamiętany indeks słowa (postęp) dla danej ścieżki pliku EPUB.
    Jeśli nie ma takiego wpisu, zwraca 0.
    """
    data = load_all_progress()
    return data.get(file_path, 0)

def save_progress(file_path, index):
    """
    Zapisuje indeks słowa (postęp) dla danej ścieżki pliku EPUB
    w słowniku i aktualizuje plik JSON.
    """
    data = load_all_progress()
    data[file_path] = index
    save_all_progress(data)

def extract_text_from_epub(file_path):
    """
    Wyciąga cały tekst (z wszystkich rozdziałów) z pliku EPUB.
    """
    book = epub.read_epub(file_path)
    text = []
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text.append(soup.get_text())
    return ' '.join(text)

def extract_cover_image_from_epub(file_path):
    """
    Zwraca surowe dane (bytes) okładki EPUB, jeśli uda się ją znaleźć.
    W przeciwnym wypadku zwraca None.
    """
    book = epub.read_epub(file_path)
    for item in book.get_items():
        # Szukamy elementu typu ITEM_IMAGE, który ma w nazwie "cover"
        if item.get_type() == ITEM_IMAGE and 'cover' in item.get_name().lower():
            return item.get_content()
    return None

def load_app_settings():
    """
    Wczytuje ustawienia aplikacji (prędkość słów, wielkość czcionki) z pliku SETTINGS_JSON.
    Jeśli plik nie istnieje lub jest niepoprawny, zwraca pusty słownik.
    """
    if os.path.exists(SETTINGS_JSON):
        try:
            with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_app_settings(settings):
    """
    Zapisuje w pliku JSON (SETTINGS_JSON) słownik z ustawieniami aplikacji.
    """
    with open(SETTINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

class WordDisplayThread(QThread):
    """
    Wątek odpowiedzialny za wyświetlanie słów w zadanym tempie
    (words_per_minute) oraz emitowanie sygnałów do aktualizacji
    labelki z tekstem i paska postępu.
    """
    word_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, file_path, text, words_per_minute):
        super().__init__()
        self.file_path = file_path
        self.text = text
        self.words_per_minute = words_per_minute
        self.running = True
        self.current_index = 0

    def run(self):
        words = self.text.split()
        # Odczytujemy zapisany postęp dla danej książki
        start_index = load_progress(self.file_path)
        delay = 60 / self.words_per_minute
        total_words = len(words)

        try:
            for i in range(start_index, total_words):
                if not self.running:
                    break
                self.current_index = i
                self.word_signal.emit(words[i])
                progress = int((i + 1) / total_words * 100)
                self.progress_signal.emit(progress)
                time.sleep(delay)
                # Zapisujemy postęp w pliku JSON
                save_progress(self.file_path, i + 1)
        except KeyboardInterrupt:
            # W razie nagłego przerwania wątku, i tak zapiszmy bieżący postęp
            save_progress(self.file_path, self.current_index)

    def stop(self):
        self.running = False

class ContextWindow(QDialog):
    """
    Okno wyświetlające kontekst wokół aktualnie czytanego słowa.
    """
    def __init__(self, parent, text, current_index):
        super().__init__(parent)
        self.setWindowTitle("Context Viewer")
        self.setGeometry(200, 200, 600, 400)
        self.text = text
        self.current_index = current_index
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.text_browser = QTextBrowser(self)
        self.text_browser.setReadOnly(True)
        self.update_context()
        layout.addWidget(self.text_browser)
        self.setLayout(layout)

    def update_context(self):
        words = self.text.split()
        start = max(0, self.current_index - 60)
        end = min(len(words), self.current_index + 61)

        context = []
        for i in range(start, end):
            if i == self.current_index:
                context.append(f'<span style="color: red; font-weight: bold;">{words[i]}</span>')
            else:
                context.append(words[i])
        self.text_browser.setHtml(" ".join(context))

class MainWindow(QMainWindow):
    """
    Główne okno aplikacji do szybkiego czytania EPUB (RSVP).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RSVPreader")

        # Domyślne wartości — zostaną nadpisane przez wczytane ustawienia (jeśli istnieją)
        self.words_per_minute = 300
        self.font_size = 16

        # Wczytujemy ustawienia aplikacji (jeśli istnieją)
        self.load_settings_from_file()

        self.text = ""
        self.thread = None
        self.current_file_path = None  # Trzymamy ścieżkę do aktualnie otwartej książki

        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()

        # Ustawienie tła okna
        self.setStyleSheet("background-color: rgb(235, 222, 200);")

        # ---------------------------------------
        # 1. Label do wyświetlania okładki
        # ---------------------------------------
        self.cover_label = QLabel(self)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("Cover not found")
        self.cover_label.setStyleSheet("background-color: rgb(235, 222, 200);")
        self.layout.addWidget(self.cover_label)

        # ---------------------------------------
        # 2. Label wyświetlający aktualne słowo
        # ---------------------------------------
        self.word_label = QLabel("Load an EPUB file to start", self)
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setStyleSheet(f"font-size: {self.font_size}px; background-color: rgb(235, 222, 200);")
        self.layout.addWidget(self.word_label)

        # ---------------------------------------
        # 3. Przycisk do ładowania plików EPUB
        # ---------------------------------------
        self.load_button = QPushButton("Load EPUB File", self)
        self.layout.addWidget(self.load_button)
        self.load_button.clicked.connect(self.load_file)

        # ---------------------------------------
        # 4. Ustawienie prędkości (słów/min) + suwak
        # ---------------------------------------
        self.speed_layout = QHBoxLayout()
        self.speed_label = QLabel("Speed (WPM):", self)
        self.speed_value = QLabel(f"{self.words_per_minute}", self)
        self.speed_slider = QSlider(Qt.Horizontal, self)
        self.speed_slider.setMinimum(100)
        self.speed_slider.setMaximum(600)
        self.speed_slider.setValue(self.words_per_minute)
        self.speed_slider.valueChanged.connect(self.update_speed)

        self.speed_layout.addWidget(self.speed_label)
        self.speed_layout.addWidget(self.speed_slider)
        self.speed_layout.addWidget(self.speed_value)
        self.layout.addLayout(self.speed_layout)

        # ---------------------------------------
        # 5. Ustawienie wielkości czcionki + suwak
        # ---------------------------------------
        self.font_layout = QHBoxLayout()
        self.font_label = QLabel("Font Size:", self)
        self.font_value = QLabel(f"{self.font_size}", self)
        self.font_slider = QSlider(Qt.Horizontal, self)
        self.font_slider.setMinimum(10)
        self.font_slider.setMaximum(50)
        self.font_slider.setValue(self.font_size)
        self.font_slider.valueChanged.connect(self.update_font_size)

        self.font_layout.addWidget(self.font_label)
        self.font_layout.addWidget(self.font_slider)
        self.font_layout.addWidget(self.font_value)
        self.layout.addLayout(self.font_layout)

        # ---------------------------------------
        # 6. Pasek postępu
        # ---------------------------------------
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #000;
                background-color: #e5ded4;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50; /* kolor zielony */
                width: 20px;
            }
        """)
        self.layout.addWidget(self.progress_bar)

        # ---------------------------------------
        # 7. Przycisk wyświetlania kontekstu
        # ---------------------------------------
        self.context_button = QPushButton("Show Context", self)
        self.context_button.clicked.connect(self.show_context)
        self.layout.addWidget(self.context_button)

        # ---------------------------------------
        # 8. Przyciski Start / Stop
        # ---------------------------------------
        self.start_button = QPushButton("Start Display", self)
        self.start_button.clicked.connect(self.start_display)
        self.layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Display", self)
        self.stop_button.clicked.connect(self.stop_display)
        self.layout.addWidget(self.stop_button)

        # ---------------------------------------
        # 9. Przycisk resetowania postępu czytania
        # ---------------------------------------
        spacer = QWidget(self)
        spacer.setFixedHeight(30)
        self.layout.addWidget(spacer)
        self.reset_button = QPushButton("Reset Progress", self)
        self.reset_button.clicked.connect(self.reset_progress)
        self.layout.addWidget(self.reset_button)

        # ---------------------------------------
        # 10. Ustawienie centralnego widgetu
        # ---------------------------------------
        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

    def load_settings_from_file(self):
        """
        Wczytuje ustawienia aplikacji z pliku i ustawia je w MainWindow.
        """
        settings = load_app_settings()
        self.words_per_minute = settings.get("words_per_minute", 300)
        self.font_size = settings.get("font_size", 16)

    def save_current_settings(self):
        """
        Zapisuje bieżące ustawienia aplikacji (prędkość, czcionkę) do pliku.
        """
        settings = {
            "words_per_minute": self.words_per_minute,
            "font_size": self.font_size
        }
        save_app_settings(settings)

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open EPUB File", "", "EPUB Files (*.epub)")
        if file_path:
            # Zapisujemy, którą książkę wczytaliśmy
            self.current_file_path = file_path

            # Wczytanie tekstu z pliku
            self.text = extract_text_from_epub(file_path)
            self.word_label.setText("File loaded. Ready to start.")

            # Wczytanie i wyświetlenie okładki
            cover_data = extract_cover_image_from_epub(file_path)
            if cover_data:
                pixmap = QPixmap()
                pixmap.loadFromData(cover_data)
                # Skalowanie okładki, aby pasowała do widoku (np. 300x400)
                pixmap = pixmap.scaled(300, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.cover_label.setPixmap(pixmap)
            else:
                self.cover_label.setText("No cover found.")

            # Ustawienie paska postępu na wartości z pliku (jeśli istnieje)
            start_index = load_progress(self.current_file_path)
            total_words = len(self.text.split())
            if total_words > 0:
                progress_value = int(start_index / total_words * 100)
                self.progress_bar.setValue(progress_value)
            else:
                self.progress_bar.setValue(0)

    def update_speed(self, value):
        self.words_per_minute = value
        self.speed_value.setText(f"{value}")
        # Zapisz nowe ustawienia od razu
        self.save_current_settings()

    def update_font_size(self, value):
        self.font_size = value
        self.font_value.setText(f"{value}")
        self.word_label.setStyleSheet(f"font-size: {self.font_size}px; background-color: rgb(235, 222, 200);")
        # Zapisz nowe ustawienia od razu
        self.save_current_settings()

    def start_display(self):
        if not self.text:
            self.word_label.setText("Please load an EPUB file first.")
            return

        self.stop_display()  # zatrzymaj ewentualnie działający poprzedni wątek
        self.thread = WordDisplayThread(self.current_file_path, self.text, self.words_per_minute)
        self.thread.word_signal.connect(self.update_word_label)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.start()

    def stop_display(self):
        if self.thread:
            self.thread.stop()
            self.thread.wait()

    def highlight_middle_letter(self, word):
        if len(word) <= 1:
            return word
        middle_index = len(word) // 2
        highlighted = (
            word[:middle_index] +
            f'<span style="color:red;">{word[middle_index]}</span>' +
            word[middle_index + 1:]
        )
        return highlighted

    def update_word_label(self, word):
        highlighted_word = self.highlight_middle_letter(word)
        self.word_label.setText(f'<html><body style="text-align:center;">{highlighted_word}</body></html>')

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def show_context(self):
        if self.thread and self.text:
            context_window = ContextWindow(self, self.text, self.thread.current_index)
            context_window.exec_()

    def reset_progress(self):
        """
        Resetuje postęp czytania (ustawia go na 0) dla aktualnie wczytanej książki.
        """
        if self.current_file_path:
            save_progress(self.current_file_path, 0)
            self.progress_bar.setValue(0)
            self.word_label.setText("Progress has been reset to the start.")

    def closeEvent(self, event):
        # Zatrzymaj wyświetlanie słów
        self.stop_display()
        # Zamknij okno
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
