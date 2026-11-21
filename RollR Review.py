import sys
import os
import sqlite3

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog,
    QComboBox, QMessageBox, QLineEdit,
    QFormLayout, QGridLayout, QScrollArea,
    QFrame, QSizePolicy,
)

from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox as _QComboBox
from datetime import datetime

class QComboBox(_QComboBox):
    def wheelEvent(self, event):
        event.ignore()

# ======================================================
# UTIL
# ======================================================

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ======================================================
# FENÊTRE PRINCIPALE
# ======================================================

class DBEditor(QWidget):

    def __init__(self):
        super().__init__()

        self.conn = None
        self.cur = None
        self.selected_resultat_id = None

        self.init_ui()

        # ouverture du fichier DB dès le lancement
        self.open_database()

    def init_ui(self):

        self.setWindowTitle("Modification en base de données")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setFixedSize(700, 270)

        self.setStyleSheet("""
            QWidget {
                background-color: white;
            }

            QLabel {
                color: black;
            }

            QLineEdit, QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
                padding: 6px;
            }

            QPushButton {
                background-color: #e6e6e6;
                color: black;
                padding: 8px 14px;
                border: 1px solid #ccc;
            }

            QPushButton:hover {
                background-color: #d9d9d9;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #d9d9d9;
                selection-color: black;
                border: 1px solid #ccc;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        title = QLabel("Modification de l'évaluation")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)

        # ================== COMBOS ==================

        self.combo_competition = QComboBox()
        self.combo_competition.setFont(QFont("Arial", 12))
        self.combo_competition.setFixedWidth(580)
        self.combo_competition.currentIndexChanged.connect(
            self.load_categories
        )

        self.combo_categorie = QComboBox()
        self.combo_categorie.setFont(QFont("Arial", 12))
        self.combo_categorie.setFixedWidth(580)
        self.combo_categorie.currentIndexChanged.connect(
            self.load_patineurs
        )

        self.combo_patineur = QComboBox()
        self.combo_patineur.setFont(QFont("Arial", 12))
        self.combo_patineur.setFixedWidth(580)
        self.combo_patineur.currentIndexChanged.connect(
            self.load_patineur_data
        )


        # ================== BOUTON SAVE ==================

        btn_save = QPushButton("Modifier ce patineur")
        btn_save.setFont(QFont("Arial", 13, QFont.Bold))
        btn_save.clicked.connect(self.open_edit_window)

        # ================== VERSION LOGICIEL ==================
        version = QLabel("v0.0.2 - 21/11/2026")
        version.setFont(QFont("Arial", 8))

        # ================== AJOUT LAYOUT ==================

        main_layout.addWidget(title)

        # ================== COMPÉTITION ==================
        row = QHBoxLayout()
        row.addWidget(QLabel("Compétition :"))
        row.addWidget(self.combo_competition)
        main_layout.addLayout(row)

        # ================== CATÉGORIE ==================
        row = QHBoxLayout()
        row.addWidget(QLabel("Catégorie :"))
        row.addWidget(self.combo_categorie)
        main_layout.addLayout(row)

        # ================== PATINEUR ==================
        row = QHBoxLayout()
        row.addWidget(QLabel("Patineur :"))
        row.addWidget(self.combo_patineur)
        main_layout.addLayout(row)

        main_layout.addWidget(btn_save)

        main_layout.addWidget(version)

    # ======================================================
    # DB
    # ======================================================

    def open_database(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une base SQLite",
            "",
            "SQLite Database (*.db)"
        )

        if not path:
            QMessageBox.critical(
                self,
                "Erreur",
                "Aucune base sélectionnée."
            )
            sys.exit()

        self.conn = sqlite3.connect(path)
        self.cur = self.conn.cursor()

        self.load_competitions()

    # ======================================================
    # LOAD COMPETITIONS
    # ======================================================

    def load_competitions(self):

        self.combo_competition.clear()

        self.cur.execute("""
            SELECT id, name
            FROM competitions
            ORDER BY name
        """)

        for comp_id, name in self.cur.fetchall():
            self.combo_competition.addItem(name, comp_id)

    # ======================================================
    # LOAD CATEGORIES
    # ======================================================

    def load_categories(self):

        self.combo_categorie.clear()

        competition_id = self.combo_competition.currentData()

        if competition_id is None:
            return

        self.cur.execute("""
            SELECT id, discipline, niveau, categorie, genre
            FROM categories
            WHERE competition_id=?
        """, (competition_id,))

        rows = self.cur.fetchall()

        for cat_id, discipline, niveau, categorie, genre in rows:

            text = (
                f"{discipline} | "
                f"{niveau} | "
                f"{categorie} | "
                f"{genre}"
            )

            self.combo_categorie.addItem(text, cat_id)

    # ======================================================
    # LOAD PATINEURS
    # ======================================================

    def load_patineurs(self):

        self.combo_patineur.clear()

        categorie_id = self.combo_categorie.currentData()

        if categorie_id is None:
            return

        self.cur.execute("""
            SELECT p.id, p.nom, p.prenom, p.club,
                   r.id
            FROM patineurs p
            LEFT JOIN resultats r
            ON (
                p.nom = r.nom
                AND p.prenom = r.prenom
                AND p.club = r.club
                AND p.categorie_id = r.categorie_id
            )
            WHERE p.categorie_id=?
            ORDER BY p.ordre
        """, (categorie_id,))

        rows = self.cur.fetchall()

        for pat_id, nom, prenom, club, resultat_id in rows:

            status = "✅ Évalué" if resultat_id else "❌ Non évalué"

            text = f"{nom} {prenom} - {club} ({status})"

            self.combo_patineur.addItem(
                text,
                (pat_id, resultat_id)
            )

    # ======================================================
    # LOAD PATINEUR DATA
    # ======================================================

    def load_patineur_data(self):

        data = self.combo_patineur.currentData()

        if not data:
            return

        pat_id, resultat_id = data
        self.selected_resultat_id = resultat_id

    def open_edit_window(self):

        data = self.combo_patineur.currentData()
        if not data:
            return

        pat_id, resultat_id = data

        if not resultat_id:
            QMessageBox.warning(self, "Erreur", "La modification est impossible car le patineur n'a pas encore été évalué.")
            return

        self.edit_window = ResultEditWindow(self.conn, resultat_id)
        self.edit_window.showFullScreen()

# ======================================================
# FENÊTRE EDITION
# ======================================================

class ResultEditWindow(QWidget):

    def set_fixed_width(self, widget, width):
        widget.setMinimumWidth(width)
        widget.setMaximumWidth(width)

    def make_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        return lbl
    
    def delete_penalite(self, id_, widget):
        self.revise()
        self.cur.execute("""
            DELETE FROM details_resultats
            WHERE id=?
        """, (id_,))

        self.conn.commit()
        self.recalcul_scores()
        self.refresh()
 
    def __init__(self, conn, resultat_id):

        super().__init__()

        self.conn = conn
        self.cur = conn.cursor()
        self.resultat_id = resultat_id

        self.inputs = {}

        self.init_ui()
        self.load_data()

    # ======================================================
    # DATE ET HEURE DE LA MODIFICATION
    # ======================================================

    def revise(self):
        # Date et heure de la modification
        date_revision = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        self.cur.execute("""
            UPDATE resultats
            SET revise = ?
            WHERE id = ?
        """, (date_revision, self.resultat_id))

    # ---------------- UI ----------------

    def init_ui(self):

        self.setWindowTitle("Modification d'un patineur")
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        
        self.setStyleSheet("""
            QWidget {
                background-color: white;
                color: black;
                font-size: 13px;
            }

            QLabel {
                color: black;
            }

            QLineEdit, QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
                padding: 5px;
                min-height: 28px;
            }

            QPushButton {
                background-color: #e6e6e6;
                color: black;
                padding: 8px 14px;
                border-radius: 4px;
                border: 1px solid #ccc;
            }

            QPushButton:hover {
                background-color: #d9d9d9;
            }

            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
            }

            QComboBox QAbstractItemView {
                background-color: white;
                color: black;
                selection-background-color: #d9d9d9;
                selection-color: black;
                border: 1px solid #ccc;
            }
        """)

        self.layout = QVBoxLayout(self)

        # -------- INFOS --------

        self.info_widget = QWidget()
        info_layout = QGridLayout(self.info_widget)

        self.lbl_categorie = QLabel("")
        self.lbl_nom = QLabel("")
        self.lbl_result = QLabel("")
        self.lbl_revise = QLabel("")
        info_layout.addWidget(self.lbl_categorie, 0, 0)
        info_layout.addWidget(self.lbl_nom, 0, 1)
        info_layout.addWidget(self.lbl_result, 1, 0)
        info_layout.addWidget(self.lbl_revise, 1, 1)

        self.layout.addWidget(self.info_widget)

        # -------- SCROLL --------

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)

        scroll.setWidget(self.content)

        self.layout.addWidget(scroll)

        # -------- BOUTONS --------

        btn_layout = QHBoxLayout()

        btn_save = QPushButton("Enregistrer")
        btn_cancel = QPushButton("Annuler")

        btn_save.clicked.connect(self.save)
        btn_cancel.clicked.connect(self.close)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        self.layout.addLayout(btn_layout)

    # ---------------- LOAD ----------------

    def load_data(self):

        self.cur.execute("""
            SELECT c.discipline,
                   c.niveau,
                   c.categorie,
                   c.genre,
                   r.revise,
                   r.nom,
                   r.prenom,
                   r.club,
                   r.score_technique,
                   r.score_composantes,
                   r.penalites,
                   r.score_total
            FROM resultats r
            LEFT JOIN categories c
                ON r.categorie_id = c.id
            WHERE r.id=?
        """, (self.resultat_id,))

        result = self.cur.fetchone()

        if result:

            self.discipline, niveau, categorie, genre, revise, nom, prenom, club, score_technique, score_composantes, penalites, score_total = result

            self.lbl_categorie.setText(
                f"{self.discipline} | {niveau} | {categorie} | {genre}"
            )
            self.lbl_nom.setText(f"{nom} {prenom} - {club}")
            self.lbl_result.setText(
                f"Score technique: {score_technique} points   |    Score composantes: {score_composantes} points    |    Pénalités: {penalites} points    |    Score total : {score_total} points"
            )
            if revise is not None:
                self.lbl_revise.setText(
                    f'<font color="red"><b>Révisé le {revise}</b></font>'
                )
            else:
                self.lbl_revise.setText("Pas de révision")

        self.cur.execute("""
            SELECT id,
                   ordre,
                   discipline,
                   type,
                   element_type,
                   element_label,
                   niveau,
                   points
            FROM details_resultats
            WHERE resultat_id=?
            ORDER BY ordre
        """, (self.resultat_id,))

        self.create_sections(self.cur.fetchall())

    # ---------------- CREATE ----------------

    def create_sections(self, rows):

        technique_box = QFrame()
        technique_layout = QVBoxLayout(technique_box)

        comp_box = QFrame()
        comp_layout = QVBoxLayout(comp_box)

        penalite_box = QFrame()
        penalite_layout = QVBoxLayout(penalite_box)

        technique_layout.addWidget(self.make_title("Techniques"))
        
        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        lbl_ordre = QLabel("Ordre")
        lbl_type = QLabel("Type")
        lbl_label = QLabel("Nom")
        lbl_niveau = QLabel("Level")
        lbl_points = QLabel("Points")

        for lbl in [lbl_ordre, lbl_type, lbl_label, lbl_niveau, lbl_points]:
            lbl.setStyleSheet("font-weight: bold;")

        h.addWidget(lbl_ordre, 1)
        if self.discipline == "Freeskating":
            h.addWidget(lbl_type, 3)

        h.addWidget(lbl_label, 2)
        h.addWidget(lbl_niveau, 2)
        h.addWidget(lbl_points, 2)


        technique_layout.addWidget(header)
        comp_layout.addWidget(self.make_title("Composantes"))
        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lbl_nom = QLabel("Nom")
        lbl_points = QLabel("Points")
        lbl_nom.setStyleSheet("font-weight: bold;")
        lbl_points.setStyleSheet("font-weight: bold;")
        h.addWidget(lbl_nom, 8)
        h.addWidget(lbl_points, 2)
        comp_layout.addWidget(header)

        penalite_layout.addWidget(self.make_title("Déductions"))
        header = QWidget()
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lbl_nom = QLabel("Nom")
        lbl_pts = QLabel("Points")
        lbl_nom.setStyleSheet("font-weight: bold;")
        lbl_pts.setStyleSheet("font-weight: bold;")
        h.addWidget(lbl_nom, 7)
        h.addWidget(lbl_pts, 3)

        penalite_layout.addWidget(header)
        for row in rows:

            id_, ordre, discipline, type_, element_type, label, niveau, points = row
            fields = {}

            # ====================================================
            # TECHNIQUES
            # ====================================================

            if type_ == "technique":

                line = QWidget()
                line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                h = QHBoxLayout(line)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(8)

                lbl_ordre = QLabel(str(ordre))
                lbl_type = QLabel(element_type)
                h.addWidget(lbl_ordre, 1)
                

                # FREE
                if discipline == "FREE":

                    txt_label = QLineEdit(label)

                    txt_niveau = QComboBox()
                    txt_niveau.addItems(["*", "0", "1", "2", "3", "4"])

                    index = txt_niveau.findText(str(niveau))
                    if index >= 0:
                        txt_niveau.setCurrentIndex(index)

                    txt_points = QLineEdit(str(points))

                    h.addWidget(lbl_type, 3)
                    h.addWidget(txt_label, 2)
                    h.addWidget(txt_niveau, 2)
                    h.addWidget(txt_points, 2)

                    fields = {
                        "element_label": txt_label,
                        "niveau": txt_niveau,
                        "points": txt_points
                    }

                # DANSE
                else:

                    lbl_element = QLabel(label)

                    combo_level = QComboBox()
                    combo_level.addItems([
                        "No level",
                        "Level Base",
                        "Level 1",
                        "Level 2",
                        "Level 3",
                        "Level 4"
                    ])

                    index = combo_level.findText(str(niveau))
                    if index >= 0:
                        combo_level.setCurrentIndex(index)

                    txt_points = QLineEdit(str(points))


                    h.addWidget(lbl_element, 2)
                    h.addWidget(combo_level,2)
                    h.addWidget(txt_points, 2)

                    fields = {
                        "niveau": combo_level,
                        "points": txt_points
                    }

                technique_layout.addWidget(line)
                self.inputs[id_] = fields

            # ====================================================
            # COMPOSANTES
            # ====================================================

            elif type_ == "composante":

                line = QWidget()

                h = QHBoxLayout(line)
                h.setContentsMargins(0, 0, 0, 0)
                h.setSpacing(8)
                
                lbl_nom = QLabel(label)
                combo_points = QComboBox()
                combo_points.addItems(["0.5", "1", "1.5", "2", "2.5", "3"])

                value = str(points)

                if value.endswith(".0"):
                    value = value[:-2]

                idx = combo_points.findText(value)

                if idx >= 0:
                    combo_points.setCurrentIndex(idx)

                h.addWidget(lbl_nom, 8)
                h.addWidget(combo_points, 2) 

                comp_layout.addWidget(line)

                self.inputs[id_] = {
                    "points": combo_points
                }

            # ====================================================
            # PENALITES
            # ====================================================

            elif type_ == "penalite":

                line = QWidget()
                h = QHBoxLayout(line)
                h.setContentsMargins(0, 0, 0, 0)

                lbl_nom = QLabel(label)
                lbl_pts = QLabel(str(points))

                btn_delete = QPushButton("X")
                
                btn_delete.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        font-weight: bold;
                        border: none;
                        border-radius: 4px;
                    }

                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)
                
                h.addWidget(lbl_nom, 7)
                h.addWidget(lbl_pts, 2)
                h.addWidget(btn_delete, 1)
                btn_delete.clicked.connect(lambda _, lid=id_: self.delete_penalite(lid, line))

                penalite_layout.addWidget(line)

        # ---------------- ADD PENALTIES ----------------

        self.penalties = {
            "Time violation": -0.5,
            "Lyrics": -1,
            "Entry and exit": -0.5,
            "Costume": -1,
            "Floor": -1,
            "Outside the rink": -0.5,
            "Fall": -1
        }

        add_pen = QWidget()
        h = QHBoxLayout(add_pen)

        self.combo_penalty = QComboBox()
        self.combo_penalty.addItems(self.penalties.keys())

        btn_add = QPushButton("Ajouter")
        btn_add.clicked.connect(self.add_penalite)

        h.addWidget(self.combo_penalty)
        h.addWidget(btn_add)

        penalite_layout.addWidget(add_pen)

        # ---------------- ADD TO UI ----------------

        self.content_layout.addWidget(technique_box)
        self.content_layout.addWidget(comp_box)
        self.content_layout.addWidget(penalite_box)

    # ---------------- PENALITE ----------------

    def add_penalite(self):
        self.revise()
        label = self.combo_penalty.currentText()
        value = self.penalties[label]
        if self.discipline == "Freeskating":
            discipline_="FREE"
        else :
            discipline_="DANSE"
        self.cur.execute("""
            INSERT INTO details_resultats
            (resultat_id, discipline, type, element_label, points)
            VALUES (?, ?, 'penalite', ?, ?)
        """, (self.resultat_id, discipline_, label, value))

        self.conn.commit()
        self.recalcul_scores()
        self.refresh()

    # ---------------- SAVE ----------------

    def save(self):

        for id_, fields in self.inputs.items():

            values = {}

            for k, w in fields.items():
                values[k] = w.currentText() if isinstance(w, QComboBox) else w.text()

            self.cur.execute("""
                UPDATE details_resultats
                SET element_label = COALESCE(?, element_label),
                    niveau = COALESCE(?, niveau),
                    points = COALESCE(?, points)
                WHERE id=?
            """, (
                values.get("element_label"),
                values.get("niveau"),
                values.get("points"),
                id_
            ))

        self.revise()
        self.recalcul_scores()

        msg = QMessageBox(self)
        msg.setWindowTitle("Validation")
        msg.setText("Données sauvegardés et scores mis à jour")
        msg.setIcon(QMessageBox.Information)
        msg.setWindowIcon(QIcon(resource_path("icon.ico")))
        msg.exec_()
        self.refresh()
    
    def recalcul_scores(self):
        # ---------------------------
        # 1. RECALCUL SCORES FROM DB
        # ---------------------------

        self.cur.execute("""
            SELECT type, points
            FROM details_resultats
            WHERE resultat_id=?
        """, (self.resultat_id,))

        total_tech = 0
        total_comp = 0
        total_pen = 0

        rows = self.cur.fetchall()

        for type_, pts in rows:

            try:
                pts = float(pts)
            except:
                pts = 0

            if type_ == "technique":
                total_tech += pts

            elif type_ == "composante":
                total_comp += pts

            elif type_ == "penalite":
                total_pen += pts  # déjà négatif

        # ---------------------------
        # 2. TOTAL
        # ---------------------------

        score_total = total_tech + total_comp + total_pen

        # ---------------------------
        # 3. UPDATE RESULTATS TABLE
        # ---------------------------

        self.cur.execute("""
            UPDATE resultats
            SET score_technique=?,
                score_composantes=?,
                penalites=?,
                score_total=?
            WHERE id=?
        """, (
            total_tech,
            total_comp,
            total_pen,
            score_total,
            self.resultat_id
        ))

        self.conn.commit()


    # ---------------- REFRESH ----------------

    def refresh(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.inputs.clear()
        self.load_data()

# ======================================================
# MAIN
# ======================================================

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = DBEditor()
    w.show()

    sys.exit(app.exec())