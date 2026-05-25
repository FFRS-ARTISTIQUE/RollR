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
        self.setFixedSize(420, 430)
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

        label1 = QLabel("Adresse IP du serveur 1 :")
        label1.setFont(QFont("Arial", 14))

        self.input_ip1 = QLineEdit()
        self.input_ip1.setFont(QFont("Arial", 14))
        self.input_ip1.setPlaceholderText("ex : 192.168.1.11")

        label_port1 = QLabel("Adresse du port du serveur 1 :")
        label_port1.setFont(QFont("Arial", 14))

        self.input_port1 = QLineEdit("5000")
        self.input_port1.setFont(QFont("Arial", 14))
        self.input_port1.setPlaceholderText("5000")

        label2 = QLabel("Adresse IP du serveur 2 :")
        label2.setFont(QFont("Arial", 14))

        self.input_ip2 = QLineEdit()
        self.input_ip2.setFont(QFont("Arial", 14))
        self.input_ip2.setPlaceholderText("ex : 192.168.1.10")

        label_port2 = QLabel("Adresse du port du serveur 2 :")
        label_port2.setFont(QFont("Arial", 14))

        self.input_port2 = QLineEdit("5000")
        self.input_port2.setFont(QFont("Arial", 14))
        self.input_port2.setPlaceholderText("5000")

        btn = QPushButton("Valider")
        btn.setFont(QFont("Arial", 14))
        btn.clicked.connect(self.accept)

        layout.addWidget(label1)
        layout.addWidget(self.input_ip1)
        layout.addWidget(label_port1)
        layout.addWidget(self.input_port1)
        layout.addWidget(label2)
        layout.addWidget(self.input_ip2)
        layout.addWidget(label_port2)
        layout.addWidget(self.input_port2)
        layout.addWidget(btn, alignment=Qt.AlignRight)

    def get_servers(self):
        return [
            (self.input_ip1.text().strip(), self.input_port1.text().strip()),
            (self.input_ip2.text().strip(), self.input_port2.text().strip()),
        ]


# ================== UI ==================
class DistantDisplay(QWidget):
    def __init__(self, servers):
        super().__init__()

        self.setWindowTitle("Affichage Distant — Système de Notation Roller")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        # ===== SERVEURS =====
        self.server_ip_1, self.server_port_1 = servers[0]
        self.server_ip_2, self.server_port_2 = servers[1]

        self.servers_data = {0: None, 1: None}
        self.active_server = 0
        self.last_data_time = time.time()

        # ===== LABELS =====
        self.label_nom = QLabel("NOM PRENOM", alignment=Qt.AlignCenter)

        self.label_tech = QLabel("TECH 0.0", alignment=Qt.AlignCenter)
        self.label_comp = QLabel("COMP 0.0", alignment=Qt.AlignCenter)
        self.label_pen = QLabel("DED 0.0", alignment=Qt.AlignCenter)

        self.label_total = QLabel("0.0", alignment=Qt.AlignCenter)
        self.label_rank = QLabel("1", alignment=Qt.AlignCenter)

        self.label_ip = QLabel(
            f"v0.2.2 - 18/04/2026 – Écran : {get_local_ip()}  ->  Serveur 1 : {self.server_ip_1}:{self.server_port_1} & Serveur 2 : {self.server_ip_2}:{self.server_port_2}          ",
            alignment=Qt.AlignCenter
        )

        # ===== BOUTON =====
        self.btn_quit = QPushButton("Quitter")
        self.btn_quit.clicked.connect(self.close)

        # ===== LAYOUT =====
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(0)
        top_layout.addWidget(self._box(self.label_tech))
        top_layout.addWidget(self._box(self.label_comp))
        top_layout.addWidget(self._box(self.label_pen))

        center_layout = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(self._box(self.label_total), 5)

        right = QVBoxLayout()
        right.addWidget(self._box(self.label_rank), 5)

        center_layout.addLayout(left, 4)
        center_layout.addLayout(right, 1)

        name_layout = QHBoxLayout()
        name_layout.addWidget(self._box(self.label_nom))

        footer_layout = QHBoxLayout()
        footer_layout.addWidget(self.label_ip)
        footer_layout.addWidget(self.btn_quit)
        footer_layout.addStretch()

        main_layout.addLayout(top_layout, 1)
        main_layout.addLayout(center_layout, 5)
        main_layout.addLayout(name_layout, 1)
        main_layout.addLayout(footer_layout)

        self.apply_white_text()

        # ===== NETWORK (2 SERVEURS) =====
        DisplayClient(
            self.server_ip_1,
            int(self.server_port_1),
            self.make_callback(0)
        )

        DisplayClient(
            self.server_ip_2,
            int(self.server_port_2),
            self.make_callback(1)
        )

        # ===== TIMEOUT =====
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_data_timeout)
        self.timer.start(1000)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.showFullScreen()

    # ================== BOX ==================
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

    # ================== DATA STORE (AUTO-SWITCH) ==================
    def store_data(self, server_id, data):
        self.servers_data[server_id] = data

        # AUTO SWITCH IMMÉDIAT
        self.active_server = server_id
        self.update_ui(data)

    # ================== UPDATE UI ==================
    def update_ui(self, data):
        self.last_data_time = time.time()
        self.apply_white_text()

        self.label_nom.setText(f"{data['nom']} {data['prenom']}")
        self.label_tech.setText(f"TECH {data['tech']:.2f}")
        self.label_comp.setText(f"COMP {data['comp']:.2f}")
        self.label_pen.setText(f"DED {data['pen']:.2f}")
        self.label_total.setText(f"{data['total']:.2f}")
        self.label_rank.setText(f"{data['classement']}")

    # ================== KEY EVENTS ==================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

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

    # ================== TIMEOUT ==================
    def check_data_timeout(self):
        if time.time() - self.last_data_time >= DATA_TIMEOUT:
            self.apply_idle_text()

    # ================== CALLBACK ==================
    def make_callback(self, server_id):
        def callback(data):
            self.store_data(server_id, data)
        return callback


# ================== MAIN ==================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    dialog = ServerIPDialog()
    if dialog.exec() != QDialog.Accepted:
        sys.exit(0)

    servers = dialog.get_servers()

    window = DistantDisplay(servers)
    sys.exit(app.exec())