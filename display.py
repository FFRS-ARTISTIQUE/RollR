import sys
import os
import socket
import time

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QDialog, QLineEdit, QFrame
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QTimer

from network.client import DisplayClient


DATA_TIMEOUT = 60


# ================== UTILS ==================
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
        
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ================== DIALOG ==================
class ServerIPDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Connexion écran")
        self.setFixedSize(420, 250)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        
        self.setStyleSheet("""
            QDialog { background-color: white; color: black; }
            QLabel { color: black; }
            QLineEdit {
                background-color: white;
                color: black;
                border: 1px solid #888;
                padding: 6px;
            }
            QPushButton {
                background-color: #e0e0e0;
                color: black;
                padding: 8px 14px;
            }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        label = QLabel("Adresse IP du serveur :")
        label.setFont(QFont("Arial", 14))

        self.input_ip = QLineEdit()
        self.input_ip.setFont(QFont("Arial", 14))
        self.input_ip.setPlaceholderText("ex : 192.168.1.10")
        
        label_port = QLabel("Adresse du port du serveur :")
        label_port.setFont(QFont("Arial", 14))

        self.input_port = QLineEdit("5000")
        self.input_port.setFont(QFont("Arial", 14))
        self.input_port.setPlaceholderText("5000")

        btn = QPushButton("Valider")
        btn.setFont(QFont("Arial", 14))
        btn.clicked.connect(self.accept)

        layout.addWidget(label)
        layout.addWidget(self.input_ip)
        layout.addWidget(label_port)
        layout.addWidget(self.input_port)
        layout.addWidget(btn, alignment=Qt.AlignRight)

    def get_ip(self):
        return self.input_ip.text().strip()
    
    def get_port(self):
        return self.input_port.text().strip()


# ================== UI ==================
class DistantDisplay(QWidget):
    def __init__(self, server_ip, server_port):
        super().__init__()

        self.server_ip = server_ip
        self.server_port = server_port
        self.last_data_time = time.time()
        
        self.setWindowTitle("Affichage Distant — Système de Notation Roller")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # ===== LABELS =====
        self.label_nom = QLabel("NOM PRENOM", alignment=Qt.AlignCenter)

        self.label_tech = QLabel("TECH 0.0", alignment=Qt.AlignCenter)
        self.label_comp = QLabel("COMP 0.0", alignment=Qt.AlignCenter)
        self.label_pen = QLabel("DED 0.0", alignment=Qt.AlignCenter)

        self.label_total = QLabel("0.0", alignment=Qt.AlignCenter)
        self.label_rank = QLabel("1", alignment=Qt.AlignCenter)
        
        self.label_ip = QLabel(f"v0.2.2 - 18/04/2026 – Écran : {get_local_ip()}  ->  Serveur : {server_ip}:{server_port}          ", alignment=Qt.AlignCenter)
        # ===== BOUTON =====
        self.btn_quit = QPushButton("Quitter")
        self.btn_quit.clicked.connect(self.close)

        # ===== LAYOUT =====
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # TOP
        top_layout = QHBoxLayout()
        top_layout.setSpacing(0)
        top_layout.addWidget(self._box(self.label_tech))
        top_layout.addWidget(self._box(self.label_comp))
        top_layout.addWidget(self._box(self.label_pen))

        # CENTER
        center_layout = QHBoxLayout()
        center_layout.setSpacing(0)

        left = QVBoxLayout()
        left.setSpacing(0)
        left.addWidget(self._box(self.label_total), 5)

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self._box(self.label_rank), 5)

        center_layout.addLayout(left, 4)
        center_layout.addLayout(right, 1)

        # NAME
        name_layout = QHBoxLayout()
        name_layout.addWidget(self._box(self.label_nom))

        # FOOTER
        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self.label_ip)
        footer_layout.addWidget(self.btn_quit)
        footer_layout.addStretch()

        # ASSEMBLAGE
        main_layout.addLayout(top_layout, 1)
        main_layout.addLayout(center_layout, 5)
        main_layout.addLayout(name_layout, 1)
        main_layout.addLayout(footer_layout)

        # STYLE
        self.apply_white_text()

        # TIMER
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_data_timeout)
        self.timer.start(1000)

        # NETWORK
        DisplayClient(server_ip, int(server_port), self.update_from_server)

        # FULLSCREEN
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.showFullScreen()

    # ================== BOX SIMPLE (PLEINE) ==================
    def _box(self, widget):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)

        frame.setStyleSheet("""
            QFrame {
                border: 5px solid #c8e58a;

            }
        """)
        return frame

    # ================== RESPONSIVE ==================
    def resizeEvent(self, event):
        if not hasattr(self, "label_nom"):
            return

        base = min(self.width(), self.height())

        self.label_nom.setFont(QFont("Arial", int(base * 0.06), QFont.Bold))

        self.label_tech.setFont(QFont("Arial", int(base * 0.05)))
        self.label_comp.setFont(QFont("Arial", int(base * 0.05)))
        self.label_pen.setFont(QFont("Arial", int(base * 0.05)))

        self.label_total.setFont(QFont("Arial", int(base * 0.28), QFont.Bold))
        self.label_rank.setFont(QFont("Arial", int(base * 0.28), QFont.Bold))

    # ================== STYLE ==================
    def apply_white_text(self):
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: white;
            }
            QPushButton {
                background-color: #222;
                color: white;
                padding: 10px;
            }
        """)

    def apply_idle_text(self):
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: #696969;
            }
            QPushButton {
                background-color: #222;
                color: #696969;
                padding: 10px;
            }
        """)

    # ================== EVENTS ==================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    # ================== LOGIC ==================
    def check_data_timeout(self):
        if time.time() - self.last_data_time >= DATA_TIMEOUT:
            self.apply_idle_text()

    def update_from_server(self, data):
        self.last_data_time = time.time()
        self.apply_white_text()

        self.label_nom.setText(f"{data['nom']} {data['prenom']}")
        self.label_tech.setText(f"TECH {data['tech']:.2f}")
        self.label_comp.setText(f"COMP {data['comp']:.2f}")
        self.label_pen.setText(f"DED {data['pen']:.2f}")
        self.label_total.setText(f"{data['total']:.2f}")
        self.label_rank.setText(f"{data['classement']}")


# ================== MAIN ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    dialog = ServerIPDialog()
    if dialog.exec() != QDialog.Accepted or not dialog.get_ip():
        sys.exit(0)

    window = DistantDisplay(dialog.get_ip(), dialog.get_port())
    window.show()

    sys.exit(app.exec())