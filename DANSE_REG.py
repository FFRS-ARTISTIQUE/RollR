# Modules standard
import os
import sys
import time
import json
import errno
import socket
import sqlite3
import re
from pathlib import Path

# Tkinter
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

# ReportLab pour les PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# Modules personnalisés
from config import get

class PatternKPEngine:
    def __init__(self):
        self.selected = []
        self.level = None

    def max_allowed(self):
        if self.level in ("NL", "B"):
            return 0
        return int(self.level)

    def toggle(self, kp):
        max_kp = self.max_allowed()

        if kp in self.selected:
            self.selected.remove(kp)
            return

        self.selected.append(kp)

        # Auto-remove oldest
        while len(self.selected) > max_kp:
            self.selected.pop(0)
            
class FootworkEngine:
    def __init__(self):
        self.level = None
        self.selected = []

    def rules(self):
        return {
            "NL": {"families": 0, "bm": 0},
            "B":  {"families": 0, "bm": 2},
            "1":  {"families": 1, "bm": 2},
            "2":  {"families": 2, "bm": 2},
            "3":  {"families": 3, "bm": 2},
            "4":  {"families": 4, "bm": 2},
        }.get(self.level, {"families": 0, "bm": 0})

    def is_bm(self, value):
        return value in ("BM1", "BM2")

    def count(self):
        bm = sum(1 for x in self.selected if self.is_bm(x))
        families = len([x for x in self.selected if not self.is_bm(x)])
        return bm, families

    def toggle(self, value):
        rules = self.rules()
        bm_count, fam_count = self.count()

        # Désélection
        if value in self.selected:
            self.selected.remove(value)
            return

        # NL → rien autorisé
        if self.level == "NL":
            return

        # ===== BM =====
        if self.is_bm(value):
            if bm_count >= rules["bm"]:
                return
            self.selected.append(value)
            return

        # ===== FAMILLES =====
        if value in self.selected:
            return  # évite doublon famille

        if fam_count >= rules["families"]:
            return

        self.selected.append(value)
        
class TravellingEngine:
    def __init__(self):
        self.level = None
        self.selected = []

    def rules(self):
        return {
            "NL": {"features": 0, "sets": 0},
            "B":  {"features": 0, "sets": 1},
            "1":  {"features": 0, "sets": 1},
            "2":  {"features": 1, "sets": 1},
            "3":  {"features": 2, "sets": 1},
            "4":  {"features": 3, "sets": 1},
        }.get(self.level, {"features": 0, "sets": 0})

    def is_bm(self, value):
        return value in ("1 set", "2 sets")

    def count(self):
        sets = sum(1 for x in self.selected if self.is_bm(x))
        features = len([x for x in self.selected if not self.is_bm(x)])
        return sets, features

    def toggle(self, value):
        rules = self.rules()
        st_count, fet_count = self.count()

        # Désélection
        if value in self.selected:
            self.selected.remove(value)
            return

        # NL → rien autorisé
        if self.level == "NL":
            return

        # ===== SETS =====
        if self.is_bm(value):
            if st_count >= rules["sets"]:
                return
            self.selected.append(value)
            return

        # ===== FEATURES =====
        if value in self.selected:
            return  # évite doublon features

        if fet_count >= rules["features"]:
            return

        self.selected.append(value)
        
DB_FILE = "competitions.db"
if len(sys.argv) < 9:
    messagebox.showerror(
        "Erreur de lancement",
        "DANSE_REG ne peut pas être lancé directement.\n\nVeuillez passer par le fichier RollR."
    )
    sys.exit(1)

LEVEL = sys.argv[1]
CATEGORIE = sys.argv[2]
GENRE = sys.argv[3]
COMPETITION = sys.argv[4]
PATINEUR_NOM = sys.argv[5]
PATINEUR_PRENOM = sys.argv[6]
PATINEUR_CLUB = sys.argv[7]
ORDRE_PASSAGE = sys.argv[8]

rules = None
state = None
total_technique = 0.0
total_penalites = 0.0
current_categorie_id = None
current_ordre = None

def skip_skater():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # récupère d'abord l'id exact du patineur
    cur.execute("""
        SELECT id
        FROM patineurs
        WHERE nom = ?
          AND prenom = ?
          AND club = ?
          AND ordre = ?
          AND categorie_id = ?
        LIMIT 1
    """, (
        root.nom,
        root.prenom,
        root.club,
        current_ordre,
        current_categorie_id
    ))
    row = cur.fetchone()
    # sécurité
    if not row:
        conn.close()
        messagebox.showerror(
            "Erreur",
            "Patineur introuvable. Veuillez fermer la page et la rouvrir."
        )
        return

    skater_id = row[0]

    # suppression du BON patineur
    cur.execute("""
        DELETE FROM patineurs
        WHERE id = ?
    """, (skater_id,))

    conn.commit()
    conn.close()
    evaluer_patineur_suivant()
    
def sequence_buttons(parent, title):
    row = tk.Frame(parent, bg=BG)
    row.pack(anchor="w", pady=40)

    tk.Label(
        row,
        text=title,
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG,
        width=16,
        anchor="w"
    ).pack(side="left", padx=(0, 10))

    levels = [
        ("NL", "#ea4747"),
        ("B", "#ffcddf"),
        ("1", "#08ace6"),
        ("2", "#91d153"),
        ("3", "#0dac50"),
        ("4", "#00853a"),
    ]

    for lvl, color in levels:
        tk.Button(
            row,
            text=lvl,
            bg=color,
            **BTN_STYLE,
            command=lambda l=lvl, s=title: on_button_click(s, l, l)
        ).pack(side="left", padx=6)


def resource_path(relative_path):
    """ Permet de retrouver les fichiers avec PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

BG = get("background_color")
history_lines = []
counter = 1
center_label = None

root = tk.Tk()
root.title("Système de Notation Roller Artistique – Régional")
icon_path = Path(resource_path("icon.png"))
if sys.platform.startswith("win"):  # Windows
    try:
        root.iconbitmap(resource_path("icon.ico"))  # Utilise le .ico sur Windows
    except tk.TclError:
        # Si problème, fallback vers le .png
        root.iconphoto(True, tk.PhotoImage(file=icon_path))
else:  # Linux / Mac
    root.iconphoto(True, tk.PhotoImage(file=icon_path))
root.attributes("-fullscreen", True)
root.configure(bg=BG)
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
root.nom = PATINEUR_NOM
root.prenom = PATINEUR_PRENOM
root.club = PATINEUR_CLUB

def reset_evaluation():
    global rules, state
    global total_technique, total_penalites
    global history_lines, current_combo, counter
    global center_label, LEVEL

    # Réinitialisation logique
    rules = None
    state = None

    total_technique = 0.0
    total_penalites = 0.0

    history_lines.clear()
    current_combo = None
    counter = 1

    # Nettoyage UI
    for widget in root.winfo_children():
        widget.destroy()

    # Retour à l’écran de sélection
    start_app()

def select_level():
    selector = tk.Frame(root, bg=BG)
    selector.pack(expand=True, fill="both")

    tk.Label(
        selector,
        text="Sélection du niveau",
        font=("Arial", 22, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=30)

    # ===== CHAMPS NOM / PRÉNOM =====
    form = tk.Frame(selector, bg=BG)
    form.pack(pady=20)

    tk.Label(
        form,
        text="Prénom",
        font=("Arial", 14, "bold"),
        fg="white",
        bg=BG
    ).grid(row=0, column=0, sticky="e", padx=10, pady=5)

    entry_prenom = tk.Entry(form, font=("Arial", 14), width=20)
    entry_prenom.grid(row=0, column=1, pady=5)

    tk.Label(
        form,
        text="NOM",
        font=("Arial", 14, "bold"),
        fg="white",
        bg=BG
    ).grid(row=1, column=0, sticky="e", padx=10, pady=5)

    entry_nom = tk.Entry(form, font=("Arial", 14), width=20)
    entry_nom.grid(row=1, column=1, pady=5)

    # ===== CHOIX DU NIVEAU =====
    def choose(level):
        prenom = entry_prenom.get().strip()
        nom = entry_nom.get().strip()

        if not prenom or not nom:
            messagebox.showerror(
                "Erreur",
                "Veuillez renseigner le prénom et le nom avant de continuer."
            )
            return

        global LEVEL
        LEVEL = level

        # Tu peux stocker les infos si besoin plus tard
        root.prenom = prenom
        root.nom = nom

        selector.destroy()
        start_app()

    # ===== BOUTONS =====
    btns = tk.Frame(selector, bg=BG)
    btns.pack(pady=30)

    tk.Button(
        btns,
        text="R",
        font=("Arial", 18, "bold"),
        width=10,
        bg="#7ED957",
        command=lambda: choose("R")
    ).pack(side="left", padx=20)

    quitt = tk.Frame(selector, bg=BG)
    quitt.pack(fill="x", pady=20)
    tk.Button(
        quitt,
        text="Exit",
        bg="#fcfdff",
        width=8,
        height=1,
        font=("Arial", 12, "bold"),
        command=root.destroy   # ferme l’application
    ).pack(side="right", padx=40)

class SequenceEngine:
    def __init__(self):
        self.used = set()



class ComposantesEngine:
    def __init__(self):
        self.values = []


class SessionState:
    def __init__(self):
        self.sequence_engine = SequenceEngine()
        self.composantes_engine = ComposantesEngine()
        self.pattern_kp_engine = PatternKPEngine()
        self.pattern_arts_engine = PatternKPEngine()
        self.pattern_foots_engine = FootworkEngine() 
        self.pattern_tras_engine = TravellingEngine() 
        self.pattern_composantes_engine = type('', (), {})()  # crée un objet vide
        self.pattern_composantes_engine.values = []

LEVEL = "R"

# ================== TABLE DES POINTS ==================
POINTS = {
    "Pattern Seq.": {
        "NL": [0],
        "B": [2],
        "1": [3],
        "2": [4],
        "3": [6],
        "4": [8]
    },
    "Artistic Seq.": {
        "NL": [0],
        "B": [2],
        "1": [3],
        "2": [4],
        "3": [6],
        "4": [8]
    },
    "Travelling Seq.": {
        "NL": [0],
        "B": [2],
        "1": [3],
        "2": [4],
        "3": [6],
        "4": [8]
    },
    "Footwork Seq.": {
        "NL": [0],
        "B": [2],
        "1": [3],
        "2": [4],
        "3": [6],
        "4": [8]
    },
    "Posture": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    },
    "Vitesse": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    },
    "Qualité de patinage": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    },
    "Chorégraphie": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    },
    "Implication": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    },
    "Attitudes": {
        "0.5": [0.5],
        "1": [1],
        "2": [2],
        "3": [3],
    }

}

def is_penalty_line(line):
    return (
        "Time violation" in line or
        "Lyrics" in line or
        "Entry and exit" in line or
        "Costume" in line or
        "Floor" in line or
        "Outside the rink" in line or
        "Fall" in line
    )
def normalize_level(level):
    mapping = {
        "No Level": "NL",
        "Level Base": "B",
        "Level 1": "1",
        "Level 2": "2",
        "Level 3": "3",
        "Level 4": "4",
    }
    return mapping.get(level, level)

def refresh_center():
        center_label.delete(0, tk.END)
        for line in history_lines:
            center_label.insert(tk.END, line)

def recalc_totals():
        global total_technique, total_penalites

        total_technique = 0
        total_penalites = 0

        for line in history_lines:
            pts = extract_points(line)
            if pts < 0:
                total_penalites += pts
            else:
                total_technique += pts

def edit_selected_line(event=None):
    selection = center_label.curselection()
    if not selection:
        return

    index = selection[0]
    old_line = history_lines[index]

    if is_penalty_line(old_line):
        return

    popup = tk.Toplevel(root)
    popup.title("Modifier les points")
    popup.configure(bg=get("background_color"))

    popup_width = 500
    popup_height = 220

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()

    # ===== PARSE SAFE =====
    def safe_parse(line):
        try:
            parts = line.split(" - ")
            if len(parts) < 2:
                return line, "0"
            element = parts[-3] if len(parts) == 3 else parts[0]
            level = parts[-2] if len(parts) >= 2 else "0"
            return element, level
        except:
            return line, "0"

    element, level = safe_parse(old_line)

    # ===== DISPLAY =====
    tk.Label(
        popup,
        text=f"Element : {element}",
        bg=get("background_color"),
        fg="white"
    ).pack(pady=5)

    tk.Label(
        popup,
        text="Level :",
        bg=get("background_color"),
        fg="white"
    ).pack(pady=5)

    level_var = tk.StringVar(value=level)

    level_values = ["No Level", "Level Base", "Level 1", "Level 2", "Level 3", "Level 4"]

    level_combo = ttk.Combobox(
        popup,
        textvariable=level_var,
        values=level_values,
        state="readonly"
    )
    level_combo.pack(pady=5)

    def detect_section_from_line(line):
        if "Pattern Seq." in line:
            return "Pattern Seq."
        if "Artistic Seq." in line:
            return "Artistic Seq."
        if "Footwork Seq." in line:
            return "Footwork Seq."
        if "Travelling Seq." in line:
            return "Travelling Seq."
        return None
    # ===== APPLY =====
    def apply_edit():
        new_level = level_var.get()

        # NORMALISATION
        level_clean = normalize_level(new_level)

        # récup section depuis la ligne
        section = detect_section_from_line(old_line)

        if not section:
            messagebox.showerror("Erreur", "Section introuvable")
            return

        # recalcul points
        new_points = get_points(section, level_clean)

        parts = old_line.split(" - ")

        if len(parts) >= 3:
            parts[-2] = new_level
            parts[-1] = f"{new_points} points"
            new_line = " - ".join(parts)
        else:
            new_line = old_line

        history_lines[index] = new_line
        print("SECTION =", section)
        print("LEVEL =", level_clean)
        print("POINTS =", new_points)
        recalc_totals()
        refresh_center()
        popup.destroy()

    tk.Button(
        popup,
        text="Valider",
        bg="#7ED957",
        command=apply_edit
    ).pack(pady=10)
def calcul_medaille_danse(pattern_seq, artistic_seq, footwork_seq, travelling_seq):
    score = -1 if pattern_seq == 0 else 1

    score += {
        0: -1,
        1: 0, 2: 0, 3: 0, 4: 0, 6: 0,
        8: 1
    }.get(footwork_seq, 0)

    score += {
        0: -1,
        1: 0, 2: 0, 3: 0,
        4: 1, 6: 1, 8: 1
    }.get(artistic_seq, 0)

    score += {
        0: -1,
        1: 0, 2: 0, 3: 0, 4: 0, 6: 0,
        8: 1
    }.get(travelling_seq, 0)

    if score >= 2:
        return "Argent Danse"
    elif score == 1:
        return "Bronze Danse"
    elif score == 0:
        return "Préliminaire Danse"
    else:
        return ""
        
def get_sequences_points(resultat_id, cursor):
    seq_points = {
        "Pattern Seq.": 0,
        "Artistic Seq.": 0,
        "Footwork Seq.": 0,
        "Travelling Seq.": 0
    }

    cursor.execute("""
        SELECT element_label, points
        FROM details_resultats
        WHERE resultat_id = ?
          AND type = 'technique'
    """, (resultat_id,))

    for label, points in cursor.fetchall():
        if label in seq_points:
            seq_points[label] = points

    return (
        seq_points["Pattern Seq."],
        seq_points["Artistic Seq."],
        seq_points["Footwork Seq."],
        seq_points["Travelling Seq."]
    )
# ================== HISTORIQUE ==================
history_lines = []
current_combo = None
counter = 1


def get_points(section, level):
    try:
        return POINTS[section][level][0]
    except KeyError:
        return 0


# ================== CHRONOMETRE ==================
class Chronometre:
    def __init__(self, parent):
        self.running = False
        self.start_time = 0
        self.elapsed = 0

        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=0, sticky="w", padx=20)

        self.time_label = tk.Label(
            frame, text="00:00:00",
            font=("Arial", 14, "bold"),
            fg="white", bg=BG
        )
        self.time_label.grid(row=0, column=1, padx=15)

        btn_frame = tk.Frame(frame, width=80, height=30)
        btn_frame.grid(row=0, column=0)
        btn_frame.grid_propagate(False)

        self.start_btn = tk.Button(
            btn_frame, text="START",
            font=("Arial", 14, "bold"),
            bg="purple", fg="white",
            command=self.start
        )
        self.stop_btn = tk.Button(
            btn_frame, text="STOP",
            font=("Arial", 14, "bold"),
            bg="orange",
            command=self.stop
        )

        for b in (self.start_btn, self.stop_btn):
            b.place(relwidth=1, relheight=1)

        self.stop_btn.lower()
        self.update()

    def start(self):
        if not self.running:
            self.start_time = time.time() - self.elapsed
            self.running = True
            self.start_btn.lower()
            self.stop_btn.lift()

    def stop(self):
        if self.running:
            self.elapsed = time.time() - self.start_time
            self.running = False
            self.stop_btn.lower()
            self.start_btn.lift()

    def update(self):
        if self.running:
            t = int(time.time() - self.start_time)
            self.time_label.config(
                text=f"{t//3600:02}:{(t%3600)//60:02}:{t%60:02}"
            )
        self.time_label.after(500, self.update)


# ================== UI UTILS ==================
BTN_STYLE = {
    "width": 3,
    "font": ("Arial", 11, "bold"),
    "fg": "white"
}

def section(parent, title):
    tk.Label(
        parent, text=title,
        font=("Arial", 16, "bold"),
        fg="white", bg=BG
    ).pack(anchor="w", pady=(20, 5))

def section_with_new(parent, title, command_new):
    row = tk.Frame(parent, bg=BG)
    row.pack(anchor="w", pady=(20, 5))

    tk.Label(
        row,
        text=title,
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(side="left")

    tk.Button(
        row,
        text="New",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=command_new
    ).pack(side="left", padx=10)


def on_button_click(section_name, level, element):
    global counter, total_technique

    SEQUENCES = {
        "Footwork Seq.",
        "Pattern Seq.",
        "Artistic Seq.",
        "Travelling Seq."
    }
    if section_name == "Pattern Seq.":
        state.pattern_kp_engine.level = level
        state.pattern_kp_engine.selected.clear()
        
    if section_name == "Artistic Seq.":
        state.pattern_arts_engine.level = level
        state.pattern_arts_engine.selected.clear()
    
    if section_name == "Footwork Seq.":
        state.pattern_foots_engine.level = level
        state.pattern_foots_engine.selected.clear()
        
    if section_name == "Travelling Seq.":
        state.pattern_tras_engine.level = level
        state.pattern_tras_engine.selected.clear()
        
    # Séquence déjà utilisée
    if section_name in SEQUENCES and section_name in state.sequence_engine.used:
        messagebox.showerror(
            "Règle",
            f"{section_name} ne peut être présentée qu'une seule fois."
        )
        return

    points = get_points(section_name, level)

    # Ajout séquence
    if section_name in SEQUENCES:
        state.sequence_engine.used.add(section_name)
        if level == "NL":
            NLevel = "No Level"
        elif level == "B":
            NLevel = "Level Base"
        else:
            NLevel = f"Level {level}"

        history_lines.append(
            f"{counter}. {section_name} - {NLevel} - {points} points"
        )
        counter += 1
        total_technique += points
        refresh_center()



def on_penalty_click(label, points):
    global total_penalites

    total_penalites += points
    history_lines.append(f"{label} {points} points")
    refresh_center()


def rows_buttons(parent, section_name, rows, labels):
    for level, color in rows:
        row = tk.Frame(parent, bg=BG)
        row.pack(anchor="w", pady=6)

        for txt in [level] + labels:
            tk.Button(
                row,
                text=txt,
                bg=color,
                **BTN_STYLE,
                command=lambda s=section_name, l=level, e=txt:
                    on_button_click(s, l, e)
            ).pack(side="left", padx=10)

def one_row_buttons(parent, section_name, buttons):
    row = tk.Frame(parent, bg=BG)
    row.pack(anchor="w", pady=6)

    for level, color in buttons:
        tk.Button(
            row,
            text=level,
            bg=color,
            **BTN_STYLE,
            command=lambda s=section_name, l=level, e=level:
                on_button_click(s, l, e)
        ).pack(side="left", padx=7)

def on_confirm():
    show_validation_popup()

def set_composante(name, value, refresh_callback):
    state.composantes_engine.values = [
        c for c in state.composantes_engine.values
        if c["name"] != name
    ]

    state.composantes_engine.values.append({
        "name": name,
        "value": value
    })

    refresh_callback()

def generate_pdf(resultat_id):
    # Dossier de sortie
    output_dir = os.path.join(os.getcwd(), f"result\\temp")
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(
        output_dir,
        f"Resultat_{LEVEL}_DANSE_{CATEGORIE}_{GENRE}_{root.nom}_{root.prenom}_{root.club}.pdf"
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    # =====================================================
    # TITRE
    # =====================================================
    story.append(Paragraph("<b>Notation Danse Régional</b>", styles["Title"]))
    story.append(Spacer(1, 5))

    story.append(Paragraph(
        f"<b>Patineur :</b> {root.nom} {root.prenom} - {root.club}<br/>"
        f"<b>Niveau :</b> {LEVEL} {CATEGORIE} {GENRE}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 10))

    # =====================================================
    # RÉCUP DETAILS DEPUIS DB
    # =====================================================
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT name, value
        FROM assessment_details
        WHERE resultat_id = ?
    """, (resultat_id,))

    rows = cur.fetchall()
    conn.close()

    # Regroupement KP
    kp_dict = {}
    for name, value in rows:
        kp_dict.setdefault(name, []).append(value)

    # Tri des KP (optionnel mais propre)
    for key in kp_dict:
        kp_dict[key].sort()

    # Mapping si noms différents entre UI et DB
    mapping = {
        "Pattern Seq.": "Pattern Sequence",
        "Artistic Seq.": "Artistic Sequence",
        "Footwork Seq.": "Footwork Sequence",
        "Travelling Seq.": "Travelling Sequence"
    }

    # =====================================================
    # ÉLÉMENTS TECHNIQUES
    # =====================================================
    story.append(Paragraph("<b>Éléments techniques</b>", styles["Heading2"]))
    story.append(Spacer(1, 5))

    elements_data = [["#", "Élément", "Niveau", "Points"]]

    for line in history_lines:
        if "points" not in line:
            continue

        try:
            clean = line.strip()
            parts = clean.split(" - ")

            if len(parts) != 3:
                continue

            label_section = parts[0]
            level_text = parts[1].replace("Level ", "")
            points = parts[2].replace(" points", "")

            # Séparation numéro / élément
            if ". " in label_section:
                label, element = label_section.split(". ", 1)
            else:
                label = ""
                element = label_section

            # Mapping nom pour correspondance DB
            lookup_name = mapping.get(element, element)

            # Injection KP
            if lookup_name in kp_dict:
                kp_text = ", ".join(kp_dict[lookup_name])
                element_display = f"{element} ({kp_text})"
            else:
                element_display = element

            elements_data.append([
                label,
                element_display,
                level_text,
                points
            ])

        except Exception as e:
            print("PDF PARSE ERROR:", e, clean)

    # TABLE
    table = Table(elements_data, colWidths=[40, 280, 60, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (2,1), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))

    story.append(table)
    story.append(Spacer(1, 10))

    # =====================================================
    # COMPOSANTES
    # =====================================================
    story.append(Paragraph("<b>Composantes</b>", styles["Heading2"]))
    story.append(Spacer(1, 5))

    comp_data = [["Composante", "Point"]]

    # Récupérer les valeurs des attitudes (pattern_composantes_engine)
    pattern_values_dict = {
        c["name"]: c["value"]
        for c in state.pattern_composantes_engine.values
    }

    for c in state.composantes_engine.values:
        # Cas spécifique Attitudes
        if c["name"] == "Attitudes":
            attitudes_list = pattern_values_dict.get("Attitudes", [])
            if isinstance(attitudes_list, list) and attitudes_list:
                attitudes_display = ", ".join(attitudes_list)
                name_display = f"Attitudes ({attitudes_display})"
            else:
                name_display = c["name"]
                value_display = str(c["value"])  # points uniquement
        else:
            name_display = c["name"]
            value_display = str(c["value"])

        comp_data.append([name_display, value_display])

    comp_table = Table(comp_data, colWidths=[300, 80])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))

    story.append(comp_table)
    story.append(Spacer(1, 10))

    # =====================================================
    # DÉDUCTIONS
    # =====================================================
    story.append(Paragraph("<b>Déductions</b>", styles["Heading2"]))
    story.append(Spacer(1, 5))

    penalties_data = [["Motif", "Points"]]

    for line in history_lines:
        if "points" in line:
            try:
                value = float(line.split()[-2])
                if value < 0:
                    label = " ".join(line.split()[:-2])
                    penalties_data.append([label, f"{value:.1f}"])
            except Exception:
                pass

    if len(penalties_data) == 1:
        penalties_data.append(["Aucune pénalité", "0.0"])

    pen_table = Table(penalties_data, colWidths=[300, 80])
    pen_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))

    story.append(pen_table)
    story.append(Spacer(1, 10))

    # =====================================================
    # TOTAUX
    # =====================================================
    total_composantes = calcul_total_composantes()
    score_total = total_technique + total_penalites + total_composantes

    story.append(Paragraph(
        f"<b>Score technique :</b> {total_technique:.1f} points<br/>"
        f"<b>Score composantes :</b> {total_composantes:.1f} points<br/>"
        f"<b>Déductions :</b> {total_penalites:.1f} points<br/><br/>"
        f"<b>Score Total :</b> {score_total:.1f} points",
        styles["Normal"]
    ))

    # =====================================================
    # BUILD PDF
    # =====================================================
    doc.build(story)

    if get("message_box_pdf"):
        messagebox.showinfo(
            "PDF généré",
            f"Le fichier PDF a été créé :\n{filename}"
        )

def sauvegarder_resultat():
    total_composantes = calcul_total_composantes()
    score_total = total_technique + total_penalites + total_composantes

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # ===== CALCUL MEDAILLE DANSE =====
    pattern = 0
    artistic = 0
    footwork = 0
    travelling = 0

    for line in history_lines:
        if "points" not in line:
            continue

        clean = line.strip()
        parts = clean.split(" - ")

        if len(parts) != 3:
            continue

        label_part = parts[0]
        niveau = parts[1]
        points = float(parts[2].replace(" points", ""))

        # ===== DETECTION SEQUENCES =====
        if "Pattern Seq." in label_part:
            pattern = points
        elif "Artistic Seq." in label_part:
            artistic = points
        elif "Footwork Seq." in label_part:
            footwork = points
        elif "Travelling Seq." in label_part:
            travelling = points

    medal = calcul_medaille_danse(pattern, artistic, footwork, travelling)
    # ================== INSERT RESULTAT ==================
    cur.execute("""
        INSERT INTO resultats (
            categorie_id, nom, prenom, club, ordre,
            score_technique, score_composantes,
            penalites, score_total, medal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        current_categorie_id,
        root.nom,
        root.prenom,
        root.club,
        current_ordre,
        total_technique,
        total_composantes,
        total_penalites,
        score_total,
        medal
    ))

    resultat_id = cur.lastrowid   # IMPORTANT

    # ================== DÉTAILS TECHNIQUES ==================
    ordre_local = 1
    for line in history_lines:
        if "points" not in line:
            continue

        clean = line.strip()
        parts = clean.split(" - ")

        if len(parts) != 3:
            continue

        label_part = parts[0]
        niveau = parts[1]
        points = float(parts[2].replace(" points", ""))

        # Séparer numéro / élément
        if ". " in label_part:
            _, label = label_part.split(". ", 1)
        else:
            label = label_part
        cur.execute("""
            INSERT INTO details_resultats (
                resultat_id, discipline, type,
                ordre, parent_ordre,
                element_type, element_code, element_label,
                niveau, points
            )
            VALUES (?, 'DANSE', 'technique',
                    ?, NULL,
                    NULL, NULL, ?,
                    ?, ?)
        """, (
            resultat_id,
            ordre_local,
            label,
            niveau,
            points
        ))
        ordre_local += 1

    # ==================================================
    # 3️ COMPOSANTES
    # ==================================================
    for c in state.composantes_engine.values:
        cur.execute("""
            INSERT INTO details_resultats (
                resultat_id, discipline, type,
                ordre, parent_ordre,
                element_type, element_code, element_label,
                niveau, points
            )
            VALUES (?, 'FREE', 'composante',
                    NULL, NULL,
                    NULL, NULL, ?,
                    NULL, ?)
        """, (
            resultat_id,
            c["name"],
            c["value"]
        ))

    # ==================================================
    # 4️ PÉNALITÉS
    # ==================================================
    for line in history_lines:
        clean = line.strip()

        if clean[:1].isdigit():
            continue
        if not clean.endswith("points"):
            continue

        try:
            label, value, _ = clean.rsplit(" ", 2)
            points = float(value)
        except ValueError:
            continue

        if points >= 0:
            continue

        cur.execute("""
            INSERT INTO details_resultats (
                resultat_id, discipline, type,
                ordre, parent_ordre,
                element_type, element_code, element_label,
                niveau, points
            )
            VALUES (?, 'FREE', 'penalite',
                    NULL, NULL,
                    NULL, NULL, ?,
                    NULL, ?)
        """, (
            resultat_id,
            label,
            points
        ))
    
    # ================== Assesment details ==================
    for kp in state.pattern_kp_engine.selected:
        cur.execute("""
            INSERT INTO assessment_details (resultat_id, name, value)
            VALUES (?, ?, ?)
        """, (
            resultat_id,
            "Pattern Sequence",
            kp
        ))
        
    for arts in state.pattern_arts_engine.selected:
        cur.execute("""
            INSERT INTO assessment_details (resultat_id, name, value)
            VALUES (?, ?, ?)
        """, (
            resultat_id,
            "Artistic Sequence",
            arts
        ))
        
    for foots in state.pattern_foots_engine.selected:
        cur.execute("""
            INSERT INTO assessment_details (resultat_id, name, value)
            VALUES (?, ?, ?)
        """, (
            resultat_id,
            "Footwork Sequence",
            foots
        ))
    
    for tras in state.pattern_tras_engine.selected:
        cur.execute("""
            INSERT INTO assessment_details (resultat_id, name, value)
            VALUES (?, ?, ?)
        """, (
            resultat_id,
            "Travelling Sequence",
            tras
        ))
        
    for attitude in state.pattern_composantes_engine.values:
        if attitude["name"] == "Attitudes":
            cur.execute("""
                INSERT INTO assessment_details (resultat_id, name, value)
                VALUES (?, ?, ?)
            """, (
                resultat_id,
                attitude["name"],
                json.dumps(attitude["value"])  # Convertit la liste en JSON
            ))
    
    conn.commit()
    conn.close()
    return resultat_id 

def generate_classement_pdf():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            r.id,
            r.nom,
            r.prenom,
            r.club,
            r.ordre,
            r.score_technique,
            r.score_composantes,
            r.penalites,
            r.score_total,
            r.medal
        FROM resultats r
        WHERE r.categorie_id = ?
        ORDER BY r.score_total DESC, r.score_composantes DESC
    """, (current_categorie_id,))

    rows = cur.fetchall()

    output_dir = os.path.join(os.getcwd(), f"result\\DANSE")
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(
        output_dir,
        f"Classement_DANSE_{LEVEL}_{CATEGORIE}_{GENRE}.pdf"
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    # =====================================================
    # PAGE 1 – CLASSEMENT
    # =====================================================
    story.append(Paragraph(
        f"<b>Classement – Danse {LEVEL} {CATEGORIE} {GENRE}</b>",
        styles["Title"]
    ))
    story.append(Spacer(1, 20))

    table_data = [[
        "Place", "Nom", "Prénom", "Club",
        "Score technique", "Score composantes",
        "Déductions", "Score total", "Médaille"
    ]]

    last_total = None
    last_sc = None
    current_rank = 0

    for (_, nom, prenom, club, _, st, sc, pen, total, medal) in rows:

        # Nouveau rang si scores différents
        if total != last_total or sc != last_sc:
            current_rank += 1

        # Sauvegarde pour comparaison
        last_total = total
        last_sc = sc

        table_data.append([
            current_rank,  
            nom,
            prenom,
            club,
            f"{st:.1f}",
            f"{sc:.1f}",
            f"{pen:.1f}",
            f"{total:.1f}",
            f"{medal}"
        ])

    table = Table(table_data, colWidths=[25, 85, 85, 125, 55, 60, 40, 40, 55])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("ALIGN", (0,1), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 6),
    ]))

    story.append(table)

    # =====================================================
    # PAGES SUIVANTES – DÉTAIL PAR PATINEUR
    # =====================================================
    last_total = None
    last_sc = None
    current_rank = 0

    for row in rows:
        resultat_id, nom, prenom, club, ordre, st, sc, pen, total, medal = row

        # Nouveau rang si scores différents
        if total != last_total or sc != last_sc:
            current_rank += 1

        # Sauvegarde
        last_total = total
        last_sc = sc

        place = current_rank  

        story.append(PageBreak())
        
        # ----- TITRE -----
        story.append(Paragraph(
            f"<b>Rang {place}</b>",
            styles["Title"]
        ))
        story.append(Spacer(1, 10))

        story.append(Paragraph(
            f"<b>Nom :</b> {nom} {prenom}- {club}<br/>"
            f"<b>Niveau :</b> {LEVEL} {CATEGORIE} {GENRE}",
            styles["Normal"]
        ))
        story.append(Spacer(1, 15))
        
        # =====================================================
        # RÉCUP DETAILS DEPUIS DB
        # =====================================================
        cur.execute("""
            SELECT name, value
            FROM assessment_details
            WHERE resultat_id = ?
        """, (resultat_id,))

        rows = cur.fetchall()

        # Regroupement KP
        kp_dict = {}
        for name, value in rows:
            kp_dict.setdefault(name, []).append(value)

        # Tri des KP (optionnel mais propre)
        for key in kp_dict:
            kp_dict[key].sort()

        # Mapping si noms différents entre UI et DB
        mapping = {
            "Pattern Seq.": "Pattern Sequence",
            "Artistic Seq.": "Artistic Sequence",
            "Footwork Seq.": "Footwork Sequence",
            "Travelling Seq.": "Travelling Sequence"
        }

        # ================== ÉLÉMENTS TECHNIQUES ==================
        story.append(Paragraph("<b>Éléments techniques</b>", styles["Heading2"]))
        story.append(Spacer(1, 5))
        tech_data = [["#", "Élément", "Niveau", "Points"]]

        cur.execute("""
            SELECT element_label, niveau, points
            FROM details_resultats
            WHERE resultat_id = ? AND type = 'technique'
        """, (resultat_id,))
        counter_local = 1
        for label, niveau, points in cur.fetchall():
            # Mapping nom pour correspondance DB
            lookup_name = mapping.get(label, label)

            # Injection KP
            if lookup_name in kp_dict:
                kp_text = ", ".join(kp_dict[lookup_name])
                element_display = f"{label} ({kp_text})"
            else:
                element_display = f"{label}"
                    
            tech_data.append([f"{counter_local}.", element_display, niveau, f"{points:.1f}"])
            counter_local += 1
        tech_table = Table(tech_data, colWidths=[40, 280, 60, 60])
        tech_table.setStyle(TableStyle([
		 ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (2,1), (-1,-1), "CENTER"),

        ]))

        story.append(tech_table)
        story.append(Spacer(1, 10))

        # =====================================================
        # COMPOSANTES
        # =====================================================
        story.append(Paragraph("<b>Composantes</b>", styles["Heading2"]))
        story.append(Spacer(1, 5))

        comp_data = [["Composante", "Points"]]
        #
        cur.execute("""
            SELECT element_label, points
            FROM details_resultats
            WHERE resultat_id = ?
              AND type = 'composante'
        """, (resultat_id,))

        for label, points in cur.fetchall():
            lookup_name = mapping.get(label, label)

            if lookup_name in kp_dict:
                kp_values = kp_dict[lookup_name]

                if len(kp_values) == 1 and isinstance(kp_values[0], str):
                    try:
                        kp_values = json.loads(kp_values[0])
                    except:
                        pass  

                kp_text = ", ".join(kp_values)
                if kp_values is not None:
                    name_display = f"{label} ({kp_text})"
                else:
                    name_display = f"{label}"
            else:
                name_display = f"{label}"

            comp_data.append([name_display, f"{points:.1f}"])

        comp_table = Table(comp_data, colWidths=[300, 80])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ]))

        story.append(comp_table)
        story.append(Spacer(1, 12))
        #
   
        # =====================================================
        # DÉDUCTIONS / PÉNALITÉS
        # =====================================================
        story.append(Paragraph("<b>Déductions</b>", styles["Heading2"]))
        story.append(Spacer(1, 5))

        pen_data = [["Motif", "Points"]]

        cur.execute("""
            SELECT element_label, points
            FROM details_resultats
            WHERE resultat_id = ?
              AND type = 'penalite'
        """, (resultat_id,))


        penalties = cur.fetchall()
        if penalties:
            for label, points in penalties:
                pen_data.append([label, f"{points:.1f}"])
        else:
            pen_data.append(["Aucune pénalité", "0.0"])

        pen_table = Table(pen_data, colWidths=[300, 80])
        pen_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ]))

        story.append(pen_table)
        story.append(Spacer(1, 15))

        # =====================================================
        # TOTAUX
        # =====================================================
        story.append(Paragraph(
            f"<b>Score technique :</b> {st:.1f} points<br/>"
            f"<b>Score composantes :</b> {sc:.1f} points<br/>"
            f"<b>Déductions :</b> {pen:.1f} points<br/><br/>"
            f"<b>Score Total :</b> {total:.1f} points",
            styles["Normal"]
        ))

    conn.close()
    doc.build(story)

    if get("message_box_all_pdf"):
        messagebox.showinfo(
            "Classement généré",
            f"Classement détaillé PDF créé :\n{filename}"
        )


def show_result_popup():
    popup = tk.Toplevel(root)
    popup.title("Validation")
    popup.configure(bg=BG)

    # Taille de la popup
    popup_width = 500
    popup_height = 600

    # Taille de l'écran
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()

    # Calcul position centrée
    x = (screen_width // 2) - (popup_width // 2)
    y = (screen_height // 2) - (popup_height // 2)

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    # ===== TITRE =====
    tk.Label(
        popup,
        text=f" {root.prenom} {root.nom}",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

    # ===== TECHNIQUE =====
    tk.Label(
        popup,
        text=f"Score technique : {total_technique:.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack()

    # ===== PENALITES =====
    tk.Label(
        popup,
        text=f"Déductions : {total_penalites:.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

    # ===== COMPOSANTES =====
    total_composantes = calcul_total_composantes()
    tk.Label(
        popup,
        text=f"Score composantes : {total_composantes:.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

     # ===== SCORE TOTAL=====
    tk.Label(
        popup,
        text=f"Score Total : {(total_technique + total_penalites + total_composantes):.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

    # ===== CLASSEMENT=====
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            nom,
            prenom,
            club,
            ordre,
            score_total,
            score_composantes
        FROM resultats
        WHERE categorie_id = ?
        ORDER BY score_total DESC, score_composantes DESC
    """, (current_categorie_id,))

    rows = cur.fetchall()
    conn.close()
    classement = None

    last_total = None
    last_sc = None
    current_rank = 0
    classement = None

    for (nom, prenom, club, ordre, score_total, score_composantes) in rows:

        # Nouveau rang si différent
        if score_total != last_total or score_composantes != last_sc:
            current_rank += 1

        # Sauvegarde
        last_total = score_total
        last_sc = score_composantes

        # Trouver le patineur
        if nom == root.nom and prenom == root.prenom and ordre == current_ordre:
            classement = current_rank  
            break


    tk.Label(
        popup,
        text=f"Classement provisoire : {classement}",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)
    # ===== ACTIONS =====
    def display():
        if get("DISPLAY_SERVER_BOUTON"):
            send_button.destroy()  
        status_label = tk.Label(
            popup,
            text=f"⏳ En attente d'un écran distant ({get('DISPLAY_SERVER_TIMEOUT')}s max)...",
            fg="white",
            bg=get("background_color"),
            font=("Arial", 14)
        )
        status_label.pack(pady=5)

        popup.update_idletasks()  #  affichage immédiat

        # ================== SOCKET ==================
        SERVER_IP = get("DISPLAY_SERVER_IP")
        SERVER_PORT = int(get("DISPLAY_SERVER_PORT"))
        SERVER_TIMEOUT = int(get("DISPLAY_SERVER_TIMEOUT"))

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((SERVER_IP, SERVER_PORT))
            server.listen(1)
            server.setblocking(False)  # NON BLOQUANT

        except OSError as e:
            server.close()
            return

        start_time = time.time()

        # ================== POLLING ==================
        def check_connection():
            elapsed = int(time.time() - start_time)
            remaining = SERVER_TIMEOUT - elapsed

            if remaining <= 0:
                status_label.config(
                    text="Impossible de se connecter à un écran distant"
                )

                tk.Label(
                    popup,
                    text=f"⏱️ Délai d’attente dépassé ({SERVER_TIMEOUT} secondes)",
                    fg="#f40000",
                    bg=get("background_color"),
                    font=("Arial", 14)
                ).pack(pady=5)
                server.close()
                return

            try:
                conn, addr = server.accept()
                status_label.config(
                    text=" Écran connecté"
                )
                server.setblocking(True)
                total = total_technique + total_penalites + total_composantes
                data = {
                    "nom": root.nom,
                    "prenom": root.prenom,
                    "tech": total_technique,
                    "comp": total_composantes,
                    "pen": total_penalites,
                    "total": total,
                    "classement": classement
                }
                message = json.dumps(data).encode("utf-8") + b"\n"
                conn.sendall(message)
                tk.Label(
                    popup,
                    text=f"Données envoyées à l'écran distant",
                    fg="white",
                    bg=get("background_color"),
                    font=("Arial", 14)
                ).pack(pady=5)
                conn.close()
                server.close()

            except BlockingIOError:
                status_label.config(
                    text=f"⏳ En attente d'un écran distant ({remaining}s restantes)..."
                )
                popup.after(500, check_connection)
        popup.after(100, check_connection)
    # ===== BOUTONS =====
    btns2 = tk.Frame(popup, bg=BG)
    btns2.pack(pady=20)
    if get("DISPLAY_SERVER"):
        if get("DISPLAY_SERVER_BOUTON"):
                btns = tk.Frame(popup, bg=get("background_color"))
                btns.pack(pady=30)

                send_button = tk.Button(
                    btns,
                    text="Envoyer les données",
                    font=("Arial", 12, "bold"),
                    bg="#7ED957",
                    width=30,
                    command=display
                )
                send_button.pack(side="left", padx=10)
        else:
            display()

    btn_ok = tk.Button(
        btns2,
        text="Evaluer un nouveau patineur",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=25,
        command=lambda: (popup.destroy(), evaluer_patineur_suivant())
    )
    btn_ok.pack(side="left", padx=10)


def show_validation_popup():
    popup = tk.Toplevel(root)
    popup.title("Composantes")
    popup.configure(bg=BG)

    # Taille de la popup
    popup_width = 800
    popup_height = 500

    # Taille de l'écran
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()

    # Calcul position centrée
    x = (screen_width // 2) - (popup_width // 2)
    y = (screen_height // 2) - (popup_height // 2)

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    #popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    # ===== TITRE =====
    tk.Label(
        popup,
        text=f" {root.prenom} {root.nom}",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

    # ===== TECHNIQUE =====
    tk.Label(
        popup,
        text=f"Score technique : {total_technique:.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack()

    # ===== PENALITES =====
    tk.Label(
        popup,
        text=f"Déductions : {total_penalites:.1f} points",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)

    # ===== COMPOSANTES =====
    score_label = tk.Label(popup, fg="white", bg=BG, font=("Arial", 12, "bold"))
    score_label.pack()

    # ===== SCORE TOTAL=====
    total_label = tk.Label(popup, fg="white", bg=BG, font=("Arial", 12, "bold"))
    total_label.pack(pady=10)

    # ===== FRAME COMPOSANTES =====
    composantes_frame = tk.Frame(popup, bg=BG)
    composantes_frame.pack(pady=10)

    btn_ok = tk.Button(
        popup,
        text="Confirm",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=10
    )
    btn_ok.pack(pady=20)

    # ================== REFRESH ==================
    def refresh():
        # Scores
        total_composantes = calcul_total_composantes()

        score_label.config(
            text=f"Score composantes : {total_composantes:.1f} points"
        )

        total_label.config(
            text=f"Score Total : {(total_technique + total_penalites + total_composantes):.1f} points"
        )

        # Nettoyage UI
        for widget in composantes_frame.winfo_children():
            widget.destroy()

        composantes = {
            c["name"]: c["value"]
            for c in state.composantes_engine.values
        }
        labels_map = {
            0.5: "Pauvre",
            1: "Faible",
            1.5: "Faible",
            2: "Correcte",
            2.5: "Correcte",
            3: "Bonne"
        }

        names = [
            "Posture / Qualité de patinage",
            "Vitesse",
            "Chorégraphie / Implication",
            "Attitudes"
        ]

        # ================== HEADER ==================
        for col, val in enumerate([""] + list(labels_map.values())):
            tk.Label(
                composantes_frame,
                text=val,
                font=("Arial", 10, "bold"),
                fg="#cfd6e6",
                bg=BG,
                width=6,
                anchor="center"
            ).grid(row=0, column=col, padx=2, pady=(0, 5))


        # ================== LIGNES ==================
        for r, name in enumerate(names, start=1):

            tk.Label(
                composantes_frame,
                text=name,
                font=("Arial", 12, "bold"),
                fg="white",
                bg=BG,
                width=25,
                anchor="w"
            ).grid(row=r, column=0, padx=2, pady=6)

            for c, val in enumerate(labels_map, start=1):

                selected = composantes.get(name) == val

                tk.Button(
                    composantes_frame,
                    text=str(val),
                    width=6,
                    font=("Arial", 11, "bold"),
                    bg="#7ED957" if selected else "#4e5a73",
                    fg="black" if selected else "white",
                    command=lambda n=name, v=val: set_composante(n, v, refresh)
                ).grid(row=r, column=c, padx=2, pady=6)

        # Activation bouton confirm
        noms_attendus = {
            "Posture / Qualité de patinage", "Vitesse",
            "Chorégraphie / Implication", "Attitudes"
        }

        noms_renseignes = {
            c["name"] for c in state.composantes_engine.values
        }

        btn_ok.config(
            state="normal" if noms_attendus.issubset(noms_renseignes) else "disabled"
        )

    # ===== ACTION CONFIRM =====
    def confirm_action():
        if get("assessment_details"):
            popup.destroy()
            show_assessment_details_popup()
        else:
            resultat_id = sauvegarder_resultat()
            generate_pdf(resultat_id)
            popup.destroy()
            show_result_popup()

    btn_ok.config(command=confirm_action)

    # Premier affichage
    refresh()

def show_assessment_details_popup():
    popup = tk.Toplevel(root)
    popup.title("Détails de l'évaluation")
    popup.configure(bg=BG)

    # Taille de la popup
    popup_width = 940
    popup_height = 350

    # Taille de l'écran
    screen_width = popup.winfo_screenwidth()
    screen_height = popup.winfo_screenheight()

    # Calcul position centrée
    x = (screen_width // 2) - (popup_width // 2)
    y = (screen_height // 2) - (popup_height // 2)

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    #popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    # ===== TITRE =====
    tk.Label(
        popup,
        text=f" {root.prenom} {root.nom}",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(pady=10)
    
    
    def create_sequence_ui(parent, title, engine, options):
        row = tk.Frame(parent, bg=BG)
        row.pack(anchor="w", padx=30, pady=6)

        tk.Label(
            row,
            text=title,
            font=("Arial", 12, "bold"),
            fg="white",
            bg=BG,
            width=22,
            anchor="w"
        ).pack(side="left")

        frame = tk.Frame(row, bg=BG)
        frame.pack(side="left")

        def refresh():
            for widget in frame.winfo_children():
                widget.destroy()

            if (
                (title in ("Footwork Sequence", "Travelling Sequence") and engine.level == "NL")
                or
                (title not in ("Footwork Sequence", "Travelling Sequence") and engine.level in ("NL", "B"))
            ):
                tk.Label(
                    frame,
                    text="Aucun choix possible",
                    font=("Arial", 11, "italic"),
                    fg="red",
                    bg=BG
                ).pack(side="left", padx=4)
                return

            for opt in options:
                selected = opt in engine.selected

                tk.Button(
                    frame,
                    text=opt,
                    width=10,
                    font=("Arial", 11, "bold"),
                    bg="#7ED957" if selected else "#4e5a73",
                    fg="black" if selected else "white",
                    command=lambda o=opt: on_click(o)
                ).pack(side="left", padx=4)

        def on_click(value):
            engine.toggle(value)
            refresh()

        refresh()
    
    # Pattern Sequence
    create_sequence_ui(
        popup,
        "Pattern Sequence",
        state.pattern_kp_engine,
        ["KP1", "KP2", "KP3", "KP4"]
    )

    # Artistic Sequence
    create_sequence_ui(
        popup,
        "Artistic Sequence",
        state.pattern_arts_engine,
        ["Aigle", "Saut", "Chgt Carre", "Toupie"]
    )
    
    # Footwork Sequence
    create_sequence_ui(
        popup,
        "Footwork Sequence",
        state.pattern_foots_engine,
        ["BM1", "BM2", "3t H/D", "Mk", "XB/XF", "R/C/BK/Lo"]
    )
    
    # Travelling Sequence
    create_sequence_ui(
        popup,
        "Travelling Sequence",
        state.pattern_tras_engine,
        ["1 set", "2 sets", "Bras", "Jambes", "3 tours"]
    )
               
    # --- Frame pour les attitudes ---
    attitudes_frame = tk.Frame(popup, bg=BG)
    attitudes_frame.pack(anchor="w", padx=60, pady=6)

    tk.Label(
        attitudes_frame,
        text="Attitudes",
        font=("Arial", 12, "bold"),
        fg="white",
        bg=BG,
        width=22,
        anchor="w"
    ).pack(side="left")

    # Liste des attitudes
    attitudes = ["2 pieds", "Low", "Middle", "High"]

    # Dictionnaire pour les boutons
    attitudes_buttons = {}

    # Fonction pour récupérer la valeur actuelle des attitudes dans state
    def get_selected_attitudes():
        for comp in state.pattern_composantes_engine.values:
            if comp["name"] == "Attitudes":
                return comp["value"]
        return []

    # Fonction pour ajouter/enlever une attitude
    def toggle_attitude(value):
        selected = set(get_selected_attitudes())
        if value in selected:
            selected.remove(value)
        else:
            selected.add(value)
        # Mise à jour dans state
        state.pattern_composantes_engine.values = [
            c for c in state.pattern_composantes_engine.values if c["name"] != "Attitudes"
        ]
        state.pattern_composantes_engine.values.append({
            "name": "Attitudes",
            "value": list(selected)
        })
        # Mise à jour visuelle
        for att, btn in attitudes_buttons.items():
            btn.config(bg="#7ED957" if att in selected else "#4e5a73",
                       fg="black" if att in selected else "white")

    # Création des boutons
    for att in attitudes:
        btn = tk.Button(
            attitudes_frame,
            text=att,
            width=10,
            font=("Arial", 11, "bold"),
            bg="#4e5a73",
            fg="white",
            command=lambda a=att: toggle_attitude(a)
        )
        btn.pack(side="left", padx=4)
        attitudes_buttons[att] = btn

    # --- Initialisation visuelle des boutons selon l'état déjà sauvegardé ---
    initial_selected = set(get_selected_attitudes())
    for att in attitudes:
        if att in initial_selected:
            attitudes_buttons[att].config(bg="#7ED957", fg="black")
    
    def confirm_action():
            resultat_id = sauvegarder_resultat()   # ✅ autorisé ici
            generate_pdf(resultat_id)
            popup.destroy()
            show_result_popup()
    
    # ===== BOUTONS =====
    btns = tk.Frame(popup, bg=BG)
    btns.pack(pady=20)
    btn_ok = tk.Button(
        btns,
        text="Confirm",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=10,
        command= confirm_action
    )
    btn_ok.pack(side="left", padx=10)

def extract_points(line):
    try:
        return float(line.split()[-2])
    except Exception:
        return 0

def calcul_total_composantes():
    return sum(c["value"] for c in state.composantes_engine.values)

def evaluer_patineur_suivant():
    global current_ordre

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT nom, prenom, club, ordre
        FROM patineurs
        WHERE categorie_id = ?
          AND ordre > ?
        ORDER BY ordre ASC
        LIMIT 1
    """, (current_categorie_id, current_ordre))

    suivant = cur.fetchone()
    conn.close()

    if not suivant:
        generate_classement_pdf()
        root.destroy()
        return

    nom, prenom, club, ordre = suivant

    # Mise à jour CONTEXTE
    root.nom = nom
    root.prenom = prenom
    root.club = club
    current_ordre = ordre

    # Relance propre SANS TOUCHER current_ordre
    reset_evaluation()


# ================== APP ==================
def start_app():
    global center_label
    global rules, state
    global current_categorie_id, current_ordre

     # Retrouver l'id de la catégorie en base
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT ca.id
        FROM categories ca
        JOIN competitions co ON ca.competition_id = co.id
        WHERE co.name = ?
          AND ca.categorie = ?
          AND ca.genre = ?
          AND ca.niveau = ?
    """, (COMPETITION, CATEGORIE, GENRE, LEVEL))

    row = cur.fetchone()
    conn.close()

    if not row:
        messagebox.showerror(
            "Erreur",
            "Catégorie introuvable en base de données."
        )
        root.destroy()
        return

    current_categorie_id = row[0]


    state = SessionState()
    root.title("Notation Danse Régional")
    icon_path = Path(resource_path("icon.png"))
    if sys.platform.startswith("win"):  # Windows
        try:
            root.iconbitmap(resource_path("icon.ico"))  # Utilise le .ico sur Windows
        except tk.TclError:
            # Si problème, fallback vers le .png
            root.iconphoto(True, tk.PhotoImage(file=icon_path))
    else:  # Linux / Mac
        root.iconphoto(True, tk.PhotoImage(file=icon_path))
    root.attributes("-fullscreen", True)
    root.configure(bg=BG)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    # Header
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", pady=15)

    def quitter():
        popup = tk.Toplevel(root)
        popup.title("Quitter")
        popup.configure(bg=get("background_color"))
        popup_width = 750
        popup_height = 200

        x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
        y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        popup.transient(root)
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix
        tk.Label(
            popup,
            text="Voulez vous quitter ?",
            bg=get("background_color"),
            fg="white",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        tk.Label(
            popup,
            text="Les données en cours de saisie ne seront pas enregistrées.",
            fg="#f40000",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)

        btns = tk.Frame(popup, bg=get("background_color"))
        btns.pack(pady=30)
        tk.Button(
            btns,
            text="Oui",
            font=("Arial", 13, "bold"),
            bg="#7ED957",
            width=15,
            command=lambda: (popup.destroy(), root.destroy())
        ).pack(side="left", padx=10)

        tk.Button(
            btns,
            text="Non",
            font=("Arial", 13, "bold"),
            bg="#fc6c6c",
            width=15,
            command=lambda: (popup.destroy())
        ).pack(side="left", padx=10)
    
    def skip():
        popup = tk.Toplevel(root)
        popup.title("Skip")
        popup.configure(bg=get("background_color"))
        popup_width = 750
        popup_height = 200

        x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
        y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        popup.transient(root)
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix
        tk.Label(
            popup,
            text="Voulez vous passer au patineur suivant ?",
            bg=get("background_color"),
            fg="white",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        tk.Label(
            popup,
            text="Le patineur sera supprimé.",
            fg="#f40000",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)

        btns = tk.Frame(popup, bg=get("background_color"))
        btns.pack(pady=30)
        tk.Button(
            btns,
            text="Oui",
            font=("Arial", 13, "bold"),
            bg="#7ED957",
            width=15,
            command=skip_skater
        ).pack(side="left", padx=10)

        tk.Button(
            btns,
            text="Non",
            font=("Arial", 13, "bold"),
            bg="#fc6c6c",
            width=15,
            command=lambda: (popup.destroy())
        ).pack(side="left", padx=10)
        
    Chronometre(header)

    tk.Label(
        header,
        text=f"{current_ordre}. {LEVEL} {CATEGORIE} - {GENRE}- {root.prenom} {root.nom}",
        font=("Arial", 20, "bold"),
        fg="white",
        bg=BG
    ).grid(row=0, column=1, sticky="w", padx=200)
    
    # Skip
    tk.Button(
        header,
        text="Skip",
        font=("Arial", 12, "bold"),
        bg="#FFA500",
        fg="black",
        width=8,
        height=1,
        command=skip
    ).grid(row=0, column=1, sticky="e", padx=20)

    # Main layout
    content = tk.Frame(root, bg=BG)
    content.pack(expand=True, fill="both")

    # PRIORITÉ AU CENTRE
    content.grid_columnconfigure(0, weight=0)   # gauche = taille minimale
    content.grid_columnconfigure(1, weight=10)  # centre = prend TOUT
    content.grid_columnconfigure(2, weight=0)   # droite = taille minimale

    content.grid_rowconfigure(0, weight=1)

    left  = tk.Frame(content, bg=BG)
    center = tk.Frame(content, bg=get("color_display"))
    right = tk.Frame(content, bg=BG)

    left.grid(row=0, column=0, sticky="n", padx=(20, 10), pady=10)
    center.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    right.grid(row=0, column=2, sticky="n", padx=(10, 20), pady=10)

    # CENTER DISPLAY (HISTORIQUE)
    center_label = tk.Listbox(
        center,
        font=("Arial", 14, "bold"),
        bg=get("color_display"),
        fg="white",
        selectbackground="#4e5a73",
        activestyle="none"
    )


    center_label.place(relx=0.01, rely=0.01, relwidth=0.98, relheight=0.98)
    center_label.bind("<Double-Button-1>", lambda e: edit_selected_line())
    def resize_center(event):
        center_label.config(wraplength=event.width - 40)

    center.bind("<Configure>", resize_center)

    # ===== LEFT =====
    sequence_buttons(left, "Pattern Seq.")
    sequence_buttons(left, "Artistic Seq.")

    row = tk.Frame(left, bg=BG)
    row.pack(anchor="w", pady=(20, 5))

    tk.Label(
        row,
        text="Penalties",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(side="left", padx=(0, 15))
    tk.Button(
        row,
        text="Time violation",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Time violation", -0.5)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Lyrics",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Lyrics", -1)
    ).pack(side="left", padx=5)

    tk.Button(
        row,
        text="Entry and exit",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Entry and exit", -0.5)
    ).pack(side="left", padx=5)

    tk.Button(
        row,
        text="Costume",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Costume", -1)
    ).pack(side="left", padx=5)

    row = tk.Frame(left, bg=BG)
    row.pack(anchor="w", pady=(20, 5))
    tk.Button(
        row,
        text="Floor",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Floor", -1)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Outside the rink",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Outside the rink", -0.5)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Fall",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        command=lambda: on_penalty_click("Fall", -1)
    ).pack(side="left", padx=5)


    # ===== RIGHT =====
    sequence_buttons(right, "Travelling Seq.")  
    sequence_buttons(right, "Footwork Seq.")  

    # Bottom
    bottom = tk.Frame(root, bg=BG)
    bottom.pack(fill="x", pady=20)

    # Delete Last SOUS le rectangle bleu (centré)
    delete_frame = tk.Frame(content, bg=BG)
    delete_frame.grid(row=1, column=1, pady=10)

    def delete_last():
        global counter, total_technique, total_penalites

        if not history_lines:
            return

        removed = history_lines.pop()
        points = extract_points(removed)

        # Totaux
        if points < 0:
            total_penalites -= points
        else:
            total_technique -= points
            counter -= 1

        # Libération séquence
        SEQUENCES = {
            "Footwork Seq.",
            "Pattern Seq.",
            "Artistic Seq.",
            "Travelling Seq."
        }

        for seq in SEQUENCES:
            if seq in removed:
                state.sequence_engine.used.discard(seq)

        refresh_center()


    tk.Button(
        delete_frame,
        text="Delete Last",
        bg="darkred",
        fg="white",
        width=10,
        height=1,
        font=("Arial", 12, "bold"),
        command=delete_last
    ).pack()


    tk.Label(
        bottom,
        text=get('VERSION'),
        font=("Arial", 12),
        fg="white",
        bg=BG
    ).pack(side="left", padx=20)

    # ===== Quitter =====
    tk.Button(
        bottom,
        text="Exit",
        font=("Arial", 12, "bold"),
        bg="#fcfdff",
        fg="black",
        width=8,
        height=1,
        command=quitter
    ).pack(side="left", padx=20)


    tk.Button(
    bottom,
    text="Confirm",
    bg="#7ED957",
    width=8,
    height=1,
    font=("Arial", 12, "bold"),
    command=on_confirm
    ).pack(side="right", padx=40)

current_ordre = int(ORDRE_PASSAGE)
start_app()
root.mainloop()
