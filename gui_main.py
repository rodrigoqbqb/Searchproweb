import sys
import asyncio
import threading
import re
import webbrowser

import csv
import traceback
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel, QScrollArea, QFrame, QGraphicsDropShadowEffect,
    QFileDialog, QMessageBox, QCompleter
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize, QTimer
from PyQt5.QtGui import QIcon, QFont, QPixmap, QColor
import qtawesome as qta
from backend.services.cep_service import get_cords_from_cep, search_nearby_stores, get_cep_from_ip
from backend.services.distance_service import calculate_distance

from backend.services.synonyms import expand_search_term
from backend.core.vault import init_vault, log_search
from backend.core.bootstrap import install_dependencies

# Garante dependências antes de iniciar a interface
install_dependencies()


# Estilos CSS Premium (CanalQb Style)
STYLES = """
QMainWindow { background-color: #121212; }
QWidget#CentralWidget { background-color: #121212; }
QLabel { color: #e0e0e0; }
QLineEdit {
    background-color: #1e1e1e; border: 2px solid #333; border-radius: 8px;
    padding: 12px; color: #ffffff; font-size: 14px;
}
QLineEdit:focus { border: 2px solid #28a745; }
QPushButton#SearchBtn {
    background-color: #28a745; color: white; border: none; border-radius: 8px;
    padding: 12px 24px; font-weight: bold; font-size: 14px;
}
QPushButton#SearchBtn:hover { background-color: #218838; }
QPushButton#SearchBtn.active { background-color: #d32f2f; }
QPushButton#ExportBtn {
    background-color: #1e1e1e; color: #ffc107; border: 1px solid #ffc107;
    border-radius: 8px; padding: 12px; font-weight: bold;
}
QPushButton#ExportBtn:hover { background-color: #ffc107; color: #000; }
QFrame#ResultCard {
    background-color: #1e1e1e; border-radius: 12px; padding: 15px;
    margin-bottom: 12px; border: 1px solid #333;
}
QLabel#CardTitle { color: #28a745; font-size: 18px; font-weight: bold; }
QLabel#CardInfo { color: #aaaaaa; font-size: 13px; }
QLabel#CardDistance { color: #ffc107; font-size: 14px; font-weight: bold; }
QPushButton#WebBtn {
    background-color: #333; color: #28a745; border: 1px solid #28a745;
    border-radius: 4px; padding: 5px; font-size: 11px;
}
QScrollBar:vertical { border: none; background: #121212; width: 8px; }
QScrollBar::handle:vertical { background: #333; border-radius: 4px; }
"""

class WorkerSignals(QObject):
    finished = pyqtSignal(list)
    progress = pyqtSignal(dict) # Streaming de resultados
    error = pyqtSignal(str)

class SearchWorker(threading.Thread):
    def __init__(self, cep, search_term, signals):
        super().__init__()
        self.cep = cep
        self.search_term = search_term
        self.signals = signals
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            coords = loop.run_until_complete(get_cords_from_cep(self.cep))
            if not self._is_running: return
            
            if not coords:
                self.signals.error.emit(f"CEP {self.cep} inválido.")
                return

            # Busca otimizada (parallel + cache + synonyms + Web Hunter)
            results = loop.run_until_complete(search_nearby_stores(
                coords.latitude, coords.longitude, self.search_term, self.cep
            ))
            
            if not self._is_running: return

            
            processed = []
            for store in results:
                if not self._is_running: return
                lat = store.get("latitude")
                lon = store.get("longitude")
                if lat is not None and lon is not None:
                    try:
                        dist = calculate_distance(
                            float(coords.latitude), float(coords.longitude),
                            float(lat), float(lon)
                        )
                    except (ValueError, TypeError):
                        dist = 9999.0
                else:
                    dist = 9999.0  # Web results sem coordenadas ficam no final
                store["distance_km"] = dist
                processed.append(store)
                self.signals.progress.emit(store)  # Stream

            
            if not self._is_running: return
            
            processed.sort(key=lambda x: x["distance_km"])
            log_search(self.cep, self.search_term, len(processed))
            self.signals.finished.emit(processed)
            loop.close()
        except Exception as e:
            if self._is_running:
                self.signals.error.emit(str(e))
            print(f"\n[ERRO WORKER]: {e}")
            traceback.print_exc()


class ResultCard(QFrame):
    def __init__(self, data):
        super().__init__()
        self.setObjectName("ResultCard")
        layout = QVBoxLayout()
        title_layout = QHBoxLayout()
        title = QLabel(data["name"])
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        title_layout.addWidget(title)
        
        source_text = data.get("source", "OSM")
        if "Web" in source_text and data.get("search_url"):
            source_badge = QPushButton(source_text)
            source_badge.setCursor(Qt.PointingHandCursor)
            source_badge.setStyleSheet("background: #ffc107; color: #000; border-radius: 4px; padding: 3px 8px; font-size: 10px; font-weight: bold;")
            source_badge.clicked.connect(lambda _, url=data["search_url"]: webbrowser.open(url))
        else:
            source_badge = QLabel(source_text)
            source_badge.setStyleSheet("background: #333; color: #aaa; border-radius: 4px; padding: 2px 6px; font-size: 10px;")
        
        title_layout.addWidget(source_badge)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        
        if data.get("address"):
            addr = QLabel(f"🏠 {data['address']}")
            addr.setObjectName("CardInfo")
            addr.setWordWrap(True)
            layout.addWidget(addr)
            
        if data.get("phone"):
            phone = QLabel(f"📞 {data['phone']}")
            phone.setObjectName("CardInfo")
            phone.setWordWrap(True)
            layout.addWidget(phone)
            
        import urllib.parse
        
        # GPS Buttons Layout
        gps_layout = QHBoxLayout()
        dist = QLabel(f"📍 {data['distance_km']:.2f} km")
        dist.setObjectName("CardDistance")
        gps_layout.addWidget(dist)
        
        gps_layout.addStretch()
        
        # URL Logic
        lat = data.get("latitude")
        lon = data.get("longitude")
        
        if lat is not None and lon is not None and data.get("distance_km", 9999) < 9999:
            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            waze_url = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"
        else:
            query = urllib.parse.quote(f"{data['name']} {data.get('address', '')}")
            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={query}"
            waze_url = f"https://waze.com/ul?q={query}&navigate=yes"
            
        maps_btn = QPushButton("Maps")
        maps_btn.setObjectName("GpsBtn")
        maps_btn.setCursor(Qt.PointingHandCursor)
        maps_btn.setStyleSheet("background-color: #4285F4; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px;")
        maps_btn.clicked.connect(lambda _, url=gmaps_url: webbrowser.open(url))
        gps_layout.addWidget(maps_btn)
        
        waze_btn = QPushButton("Waze")
        waze_btn.setObjectName("GpsBtn")
        waze_btn.setCursor(Qt.PointingHandCursor)
        waze_btn.setStyleSheet("background-color: #33ccff; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px;")
        waze_btn.clicked.connect(lambda _, url=waze_url: webbrowser.open(url))
        gps_layout.addWidget(waze_btn)
        
        if data.get("website"):
            web = QPushButton("Website")
            web.setObjectName("WebBtn")
            web.setCursor(Qt.PointingHandCursor)
            web.setStyleSheet("background-color: #444; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px;")
            web.clicked.connect(lambda _, url=data["website"]: webbrowser.open(url))
            gps_layout.addWidget(web)
            
        layout.addLayout(gps_layout)
        self.setLayout(layout)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)

class FastSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("@CanalQb SearchPRO Web")
        self.setMinimumSize(550, 850)
        self.setWindowIcon(QIcon("logo.jpg"))
        
        init_vault()
        self.worker = None
        self.current_results = []
        
        self.init_ui()

        self.setStyleSheet(STYLES)

    def init_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap("logo.png").scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(logo)
        
        title_box = QVBoxLayout()
        main_t = QLabel("@CanalQb SearchPRO Web")
        main_t.setFont(QFont("Segoe UI", 18, QFont.Bold))
        main_t.setStyleSheet("color: #28a745;")
        sub_t = QLabel("Otimizado para Resultados Instantâneos")
        sub_t.setStyleSheet("color: #666; font-size: 11px;")
        title_box.addWidget(main_t)
        title_box.addWidget(sub_t)
        header.addLayout(title_box)
        header.addStretch()
        layout.addLayout(header)
        
        # Search Inputs
        cep_box = QHBoxLayout()
        self.cep_input = QLineEdit()
        self.cep_input.setPlaceholderText("Seu CEP...")
        self.cep_input.returnPressed.connect(self.handle_search_toggle)
        cep_box.addWidget(self.cep_input)
        
        self.loc_btn = QPushButton()
        self.loc_btn.setIcon(qta.icon("fa5s.map-marker-alt", color="#28a745"))
        self.loc_btn.setToolTip("Detectar Localização Automática")
        self.loc_btn.setFixedSize(40, 40)
        self.loc_btn.setStyleSheet("background: #1e1e1e; border: 1px solid #333; border-radius: 8px;")
        self.loc_btn.clicked.connect(self.auto_detect_location)
        cep_box.addWidget(self.loc_btn)
        layout.addLayout(cep_box)

        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Busque onibus, emprego, mecanica...")
        self.search_input.returnPressed.connect(self.handle_search_toggle)
        layout.addWidget(self.search_input)

        
        # Autocomplete Dinâmico
        from backend.services.synonyms import SYNONYM_MAP
        from backend.services.category import CATEGORY_MAP
        all_terms = list(set(list(SYNONYM_MAP.keys()) + list(CATEGORY_MAP.keys())))
        completer = QCompleter(all_terms)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.search_input.setCompleter(completer)

        
        # Buttons
        btns = QHBoxLayout()
        self.search_btn = QPushButton("Iniciar Pesquisa")
        self.search_btn.setObjectName("SearchBtn")
        self.search_btn.setIcon(qta.icon("fa5s.search", color="white"))
        self.search_btn.clicked.connect(self.handle_search_toggle)
        btns.addWidget(self.search_btn, 3)
        
        self.export_btn = QPushButton()
        self.export_btn.setObjectName("ExportBtn")
        self.export_btn.setIcon(qta.icon("fa5s.file-csv", color="#ffc107"))
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_results_csv)
        btns.addWidget(self.export_btn, 1)
        layout.addLayout(btns)
        
        # Results area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_c = QWidget()
        self.scroll_c.setObjectName("ScrollContent")
        self.results_layout = QVBoxLayout(self.scroll_c)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.scroll_c)
        layout.addWidget(self.scroll)
        
        self.status_label = QLabel("Pronto.")
        self.status_label.setStyleSheet("color: #555;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def auto_detect_location(self):
        self.status_label.setText("🌐 Detectando localização...")
        def _detect():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            cep = loop.run_until_complete(get_cep_from_ip())
            loop.close()
            if cep:
                self.cep_input.setText(cep)
                self.status_label.setText("📍 Localização detectada!")
            else:
                self.status_label.setText("❌ Falha ao detectar IP.")
        threading.Thread(target=_detect, daemon=True).start()

    def handle_search_toggle(self):
        if "Parar" in self.search_btn.text():
            self.stop_search()
        else:
            self.start_search()

    def start_search(self):
        cep = re.sub(r"\D", "", self.cep_input.text().strip())
        term = self.search_input.text().strip()
        
        if not cep or len(cep) != 8:
            self.status_label.setText("⚠️ CEP inválido (deve ter 8 dígitos).")
            return
            
        if not term: return

            
        self.status_label.setText("🔍 Buscando...")
        self.search_btn.setText("Parar")
        self.search_btn.setIcon(qta.icon("fa5s.stop", color="white"))
        self.search_btn.setProperty("class", "active")
        self.search_btn.setStyle(self.search_btn.style())
        
        for i in reversed(range(self.results_layout.count())): 
            self.results_layout.itemAt(i).widget().setParent(None)
        
        self.current_results = []
        self.signals = WorkerSignals()
        self.signals.progress.connect(self.on_item_found)
        self.signals.finished.connect(self.on_search_finished)
        self.signals.error.connect(self.on_search_error)
        
        self.worker = SearchWorker(cep, term, self.signals)
        self.worker.start()

    def stop_search(self):
        if self.worker:
            self.worker.stop()
            self.status_label.setText("🛑 Interrompido.")
            self.reset_button()

    def reset_button(self):
        self.search_btn.setText("Pesquisar")
        self.search_btn.setIcon(qta.icon("fa5s.search", color="white"))
        self.search_btn.setProperty("class", "")
        self.search_btn.setStyle(self.search_btn.style())

    def on_item_found(self, item):
        card = ResultCard(item)
        self.results_layout.addWidget(card)

    def on_search_finished(self, results):
        self.reset_button()
        self.current_results = results
        self.export_btn.setEnabled(len(results) > 0)
        
        # CLEAR cards added during stream
        for i in reversed(range(self.results_layout.count())): 
            widget = self.results_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # RE-RENDER sorted cards
        for item in results:
            card = ResultCard(item)
            self.results_layout.addWidget(card)

        if not results:
            term = self.search_input.text().lower()
            hint = ""
            if "onibus" in term or "ônibus" in term:
                hint = "\n💡 Tente buscar por 'ponto' ou 'parada'."
            self.status_label.setText(f"❌ Nenhum resultado.{hint}")
            return
            
        self.status_label.setText(f"✅ {len(results)} encontrados.")


    def on_search_error(self, message):
        self.reset_button()
        self.status_label.setText(f"❌ {message}")

    def export_results_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "", "CSV (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    w = csv.DictWriter(f, fieldnames=self.current_results[0].keys(), delimiter=';')
                    w.writeheader()
                    w.writerows(self.current_results)
                QMessageBox.information(self, "Sucesso", "CSV Exportado!")
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = FastSearchApp()
    window.show()
    sys.exit(app.exec_())
