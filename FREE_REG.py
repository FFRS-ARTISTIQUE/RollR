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
from rules_r1_r2 import RulesR1R2, RulesError
from config import get

active_buttons_frame = None
combo_no_combo_mode = False

class PatternKPEngine:
    def __init__(self):
        self.selected = []
        self.level = None

    def max_allowed(self):
        if self.level in ("0"):
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
            
selected_element = None
level_frame = None
DB_FILE = "competitions.db"
if len(sys.argv) < 9:
    messagebox.showerror(
        "Erreur de lancement",
        "FREE_REG ne peut pas être lancé directement.\n\nVeuillez passer par le fichier RollR."
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
confirm_popup = False

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

def resource_path(relative_path):
    """ Permet de retrouver les fichiers avec PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

BG = get("background_color")
history_lines = []
current_combo = None
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
        text="R1",
        font=("Arial", 18, "bold"),
        width=10,
        bg="#7ED957",
        command=lambda: choose("R1")
    ).pack(side="left", padx=20)

    tk.Button(
        btns,
        text="R2",
        font=("Arial", 18, "bold"),
        width=10,
        bg="#08ace6",
        command=lambda: choose("R2")
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
        command=root.destroy   # ⬅ ferme l’application
    ).pack(side="right", padx=40)


class ScoringEngine:
    def __init__(self):
        self.jumps = []
        self.spins = []


class ComboEngine:
    def __init__(self):
        self.jump_combos = []
        self.has_spin_combo = False


class FootworkEngine:
    def __init__(self):
        self.current = None


class ComposantesEngine:
    def __init__(self):
        self.values = []


class SessionState:
    def __init__(self):
        self.scoring_engine = ScoringEngine()
        self.combo_engine = ComboEngine()
        self.footwork_engine = FootworkEngine()
        self.composantes_engine = ComposantesEngine()
        self.pattern_foots_engine = PatternKPEngine()
        self.pattern_composantes_engine = type('', (), {})()  # crée un objet vide
        self.pattern_composantes_engine.values = []



LEVEL = sys.argv[1] if len(sys.argv) > 1 else "R?"

# ================== TABLE DES POINTS ==================
POINTS = {
    "Solo Jump": {
        "Wo":  [0, 0.5, 1, 2],
        "T":  [0, 0.5, 1, 2],
        "S":  [0, 0.5, 1, 2],
        "Th": [0, 1, 2, 3],
        "F":  [0, 1, 2, 3],
        "Lo": [0, 1, 2, 3],
        "Lz!":[0, 1, 2, 3],
        "Lz": [0, 2, 3, 4],
    },
    "Combo Jump": {
        "Wo":  [0, 1, 1.5, 2.5],
        "T":  [0, 1, 1.5, 2.5],
        "S":  [0, 1, 1.5, 2.5],
        "Th": [0, 1.5, 2.5, 3.5],
        "F":  [0, 1.5, 2.5, 3.5],
        "Lo": [0, 1.5, 2.5, 3.5],
        "Lz!":[0, 1.5, 2.5, 3.5],
        "Lz": [0, 2.5, 3.5, 4.5],
    },
    "Solo Spin": {
        "Ufo": [0, 2, 4, 6, 8],
        "Ubi": [0, 2, 4, 6, 8],
        "Ubo": [0, 2, 4, 6, 8],
        "Sfo": [0, 5, 7, 9, 11],
        "Sbi": [0, 5, 7, 9, 11],
        "Sbo": [0, 5, 7, 9, 11],
        "Cfo": [0, 5, 7, 9, 11],
        "Cbi": [0, 5, 7, 9, 11],
        "Cbo": [0, 5, 7, 9, 11],
    },
    "Combo Spin": {
        "Ufo": [0, 2, 4, 6, 8],
        "Ubi": [0, 2, 4, 6, 8],
        "Ubo": [0, 2, 4, 6, 8],
        "Sfo": [0, 5, 7, 9, 11],
        "Sbi": [0, 5, 7, 9, 11],
        "Sbo": [0, 5, 7, 9, 11],
        "Cfo": [0, 5, 7, 9, 11],
        "Cbi": [0, 5, 7, 9, 11],
        "Cbo": [0, 5, 7, 9, 11],
    },
    "Footwork Seq.": {
        "0": [0],
        "1": [2],
        "2": [4],
        "3": [6],
        "4": [8],
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

ELEMENT_NAMES = {
    "Wo": "Waltz Outside",
    "T": "Toe Loop",
    "S": "Salchow",
    "Th": "Thoren",
    "F": "Flip",
    "Lo": "Loop",
    "Lz!": "Lutz (!)",
    "Lz": "Lutz",
    "Ufo": "Upright Forward Outside",
    "Ubi": "Upright Backward Inside",
    "Ubo": "Upright Backward Outside",
    "Sfo": "Sit Forward Outside",
    "Sbi": "Sit Backward Inside",
    "Sbo": "Sit Backward Outside",
    "Cfo": "Camel Forward Outside",
    "Cbi": "Camel Backward Inside",
    "Cbo": "Camel Backward Outside",
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

def normalize_for_scoring(section, element, level):
    if section == "Footwork Seq.":
        # on force la clé attendue par POINTS
        return section, str(level), str(level)

    return section, element, level

def get_element_type(line):
    clean = line.strip()
    parts = clean.split(" - ")

    if line.startswith("    "):
        # sous élément → hérite du parent (simplification)
        return "Combo Jump" if any(j in line for j in ["Wo","T","S","Th","F","Lo","Lz"]) else "Combo Spin"

    if len(parts) > 0:
        return parts[0].split(". ", 1)[1]

    return None

def refresh_center():
        center_label.delete(0, tk.END)
        for line in history_lines:
            center_label.insert(tk.END, line)

def parse_line(line):
    clean = line.strip()
    parts = clean.split(" - ")

    if len(parts) < 3:
        return "", ""
    elif len(parts) == 3:
        element_label = parts[0]
        if "Level" in parts[1]:
            level = parts[1].replace("Level ", "").strip()
        else:
            level = ""
    else:
        element_label = parts[1]
        if "Level" in parts[2]:
            level = parts[2].replace("Level ", "").strip()
        else:
            level = ""

    return element_label, level

def rebuild_line(old_line, new_element, new_level, new_points):
    is_child = old_line.startswith("    ")
    indent = "    " if is_child else ""

    clean = old_line.strip()
    parts = clean.split(" - ")

    # CAS FOOTWORK
    if "Footwork Seq." in clean:
        parts[1] = f"Level {new_level}"

    else:
        if not is_child:
            # ligne principale
            parts[1] = new_element
            parts[2] = f"Level {new_level}"
        else:
            # sous élément combo
            parts[0] = new_element
            parts[1] = f"Level {new_level}"

    # points toujours à la fin
    parts[-1] = f"{new_points} points"

    return indent + " - ".join(parts)

def detect_element_type(line):
    JUMP_SET = {"Wo", "T", "S", "Th", "F", "Lo", "Lz!", "Lz"}
    SPIN_SET = {"Ufo", "Ubi", "Ubo", "Sfo", "Sbi", "Sbo", "Cfo", "Cbi", "Cbo"}
    clean = line.strip()

    if "Footwork Seq." in clean:
        return "footwork"

    words = set(clean.replace("-", " ").replace("(", " ").replace(")", " ").split())

    if words & SPIN_SET:
        return "spin"

    if words & JUMP_SET:
        return "jump"

    return "jump"

def get_section(line):
    clean = line.strip()
    JUMP_SET = {"Wo", "T", "S", "Th", "F", "Lo", "Lz!", "Lz"}
    SPIN_SET = {"Ufo", "Ubi", "Ubo", "Sfo", "Sbi", "Sbo", "Cfo", "Cbi", "Cbo"}
    clean = clean.strip()

    # priorité absolue : texte explicite
    if "Footwork Seq." in clean:
        return "Footwork Seq."

    if "Solo Jump" in clean:
        return "Solo Jump"

    if "Solo Spin" in clean:
        return "Solo Spin"

    # sinon détection automatique (combo implicite)
    words = set(clean.replace("-", " ").replace("(", " ").replace(")", " ").split())

    if words & JUMP_SET:
        return "Combo Jump"

    if words & SPIN_SET:
        return "Combo Spin"

    return None

def recalc_totals():
    global total_technique, total_penalites

    total_technique = 0
    total_penalites = 0

    for line in history_lines:
        pts = extract_points(line)

        # pénalités (négatif)
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

    # BLOQUAGE PENALTY
    if is_penalty_line(old_line):
        return
        
    jump_labels = ["Wo", "T", "S", "Th", "F", "Lo", "Lz!", "Lz"]
    spin_labels = ["Ufo", "Ubi", "Ubo", "Sfo", "Sbi", "Sbo", "Cfo", "Cbi", "Cbo"]

    index = selection[0]
    old_line = history_lines[index]
    section = get_section(old_line)
    popup = tk.Toplevel(root)
    popup.title("Modifier un élément")
    popup.configure(bg=get("background_color"))

    popup_width = 500
    popup_height = 210

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()

    tk.Label(popup, text="Element :", bg=get("background_color"), fg="white").pack(pady=5)

    element_var = tk.StringVar()

    #  détecter type
    etype = detect_element_type(old_line)

    if etype == "spin":
        values_list = spin_labels
    elif etype == "footwork":
        values_list = ["Footwork Seq."]  # ou liste vide si non modifiable
    else:
        values_list = jump_labels

    element_combo = ttk.Combobox(
        popup,
        textvariable=element_var,
        values=values_list,
        state="readonly"
    )
    element_combo.pack(pady=5)

    tk.Label(popup, text="Level :", bg=get("background_color"), fg="white").pack(pady=5)

    level_var = tk.StringVar()
    if section in ["Solo Jump", "Combo Jump"]:
        level_values = ["*", "0", "1", "2", "3"]  # jumps

    elif section == "Footwork Seq.":
        level_values = ["0", "1", "2", "3", "4"]  # footwork

    else:  # spins
        level_values = ["*", "0", "1", "2", "3", "4"]  # spins
    level_combo = ttk.Combobox(
        popup,
        textvariable=level_var,
        values=level_values,
        state="readonly"
    )
    level_combo.pack(pady=5)

    # pré-remplissage
    jump, level = parse_line(old_line)
    if section == "Footwork Seq.":
        element_var.set("Footwork Seq.")
        level_var.set(level)
    else:
        element_var.set(jump)
        level_var.set(level)

    def apply_edit():
        new_element = element_var.get()
        new_level = level_var.get()

        section = get_section(old_line)
        new_element = element_var.get()
        new_level = level_var.get()

        # NORMALISATION
        section, element, level = normalize_for_scoring(section, new_element, new_level)

        new_points = get_points(section, element, level)

        new_line = rebuild_line(old_line, new_element, new_level, new_points)

        history_lines[index] = new_line

        recalc_totals()
        refresh_center()
        popup.destroy()

    tk.Button(
        popup,
        text="Valider",
        bg="#7ED957",
        command=apply_edit
    ).pack(pady=10)
    
# ================== HISTORIQUE ==================
history_lines = []
current_combo = None
counter = 1


def get_points(section, element, level):
    try:
        # Cas spécial Footwork Seq.
        if section == "Footwork Seq.":
            return POINTS[section][element][0]

        return POINTS[section][element][int(level)]
    except Exception:
        return 0

def apply_penalty_to_combo(combo_indices):
    global total_technique

    for idx in combo_indices:
        current = history_lines[idx]

        if "(no combo)" in current:
            continue

        if "Level *" in current:
            continue

        parts = current.split(" - ")

        try:
            old_points = float(parts[-1].split()[0])
        except Exception:
            continue

        new_points = max(0, old_points - 0.5)

        total_technique -= 0.5

        parts[-1] = f"{new_points} points (no combo)"

        history_lines[idx] = " - ".join(parts)

    refresh_center()

def apply_no_combo_penalty():
    global total_technique

    def get_combo_indices(start_index):
        """Récupère une combo complète à partir d'un index"""
        indices = [start_index]
        i = start_index + 1

        while i < len(history_lines) and history_lines[i].startswith("    "):
            indices.append(i)
            i += 1

        return indices

    def combo_already_penalized(combo_indices):
        for idx in combo_indices:
            if "(no combo)" in history_lines[idx]:
                return True
        return False

    # ================== DERNIÈRE COMBO ==================
    last_combo_start = None

    for i, line in enumerate(history_lines):
        if "Combo Jump" in line:
            last_combo_start = i

    if last_combo_start is None:
        return

    last_combo = get_combo_indices(last_combo_start)

    # ================== SI DÉJÀ PÉNALISÉ ==================
    if combo_already_penalized(last_combo):

        # chercher la première combo
        first_combo_start = None

        for i, line in enumerate(history_lines):
            if "Combo Jump" in line:
                first_combo_start = i
                break

        if first_combo_start is None:
            return

        first_combo = get_combo_indices(first_combo_start)

        popup = tk.Toplevel(root)
        popup.title("Confirmer")
        popup.configure(bg=get("background_color"))

        popup_width = 750
        popup_height = 200

        x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
        y = (popup.winfo_screenheight() // 2) - (popup_height // 2)

        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        popup.transient(root)
        popup.grab_set()
        popup.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(
            popup,
            text="La No Combo a déjà été appliquée sur cette combinaison.\nVoulez-vous l'appliquer sur la première combinaison ?",
            bg=get("background_color"),
            fg="white",
            font=("Arial", 14, "bold")
        ).pack(pady=10)

        btns = tk.Frame(popup, bg=get("background_color"))
        btns.pack(pady=30)

        tk.Button(
            btns,
            text="Oui",
            font=("Arial", 13, "bold"),
            bg="#7ED957",
            width=15,
            command=lambda: (
                popup.destroy(),
                apply_penalty_to_combo(first_combo)
            )
        ).pack(side="left", padx=10)

        tk.Button(
            btns,
            text="Non",
            font=("Arial", 13, "bold"),
            bg="#fc6c6c",
            width=15,
            command=popup.destroy
        ).pack(side="left", padx=10)

        return

    # ================== APPLICATION NORMALE ==================
    combo_indices = last_combo

    for idx in combo_indices:
        current = history_lines[idx]

        if "Level *" in current:
            continue

        if "(no combo)" in current:
            continue

        parts = current.split(" - ")

        try:
            old_points = float(parts[-1].split()[0])
        except Exception:
            continue

        new_points = max(0, old_points - 0.5)

        total_technique -= 0.5

        parts[-1] = f"{new_points} points (no combo)"
        history_lines[idx] = " - ".join(parts)

    refresh_center()

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
BTN_JUMP_STYLE = {
    "width": 3,
    "font": ("Arial", 10, "bold"),
    "bg": "#4e5a73",
    "fg": "white",
    "padx": 6,
    "pady": 6
}
def section(parent, title):
    tk.Label(
        parent, text=title,
        font=("Arial", 16, "bold"),
        fg="white", bg=BG
    ).pack(anchor="w", pady=(20, 5))

def section_with_new(parent, title, command_new, command_no_combo=None):
    row = tk.Frame(parent, bg=BG)
    row.pack(anchor="w", pady=(20, 5), fill="x")

    tk.Label(
        row,
        text=title,
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(side="left")

    # Bouton NEW
    tk.Button(
        row,
        text="New",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady=6,
        command=command_new
    ).pack(side="left", padx=(10, 5))

    # Bouton NO COMBO
    if command_no_combo is not None:
        tk.Button(
            row,
            text="No Combo",
            font=("Arial", 10, "bold"),
            bg="#b22222",
            fg="white",
            padx=6,
            pady=6,
            command=command_no_combo
        ).pack(side="left", padx=5)
        
def new_combo_jump():
    global current_combo
    current_combo = None

def new_combo_spin():
    global current_combo
    current_combo = None

def on_button_click(section_name, level, element):
    global current_combo, counter
    global total_technique
    
    if section_name == "Footwork Seq.":
        state.pattern_foots_engine.level = level
        state.pattern_foots_engine.selected.clear()
      
    # Ignore clics sur niveaux
    if section_name != "Footwork Seq." and element.isdigit():
        return

    # ❌ FOOTWORK DÉJÀ SAISIE
    if section_name == "Footwork Seq." and state.footwork_engine.current is not None:
        messagebox.showerror(
            "Règle",
            "La Footwork Séquence ne peut être présentée qu'une seule fois."
        )
        return

    points = get_points(section_name, element, level)
    #element_name = ELEMENT_NAMES.get(element, element)
    element_name = element

    # =====================================================
    # ====================== SAUTS ========================
    # =====================================================
    if section_name in ("Solo Jump", "Combo Jump"):

        jump_data = {
            "code": element,
            "level": level,
            "points": points,
            "type": "combo" if section_name == "Combo Jump" else "solo",
            "history_index": None
        }

        state.scoring_engine.jumps.append(jump_data)

        # -------- COMBO JUMP --------
        if section_name == "Combo Jump":

            if current_combo != "Combo Jump":
                state.combo_engine.jump_combos.append([])

                history_lines.append(
                    f"{counter}. Combo Jump - {element_name} - Level {level} - {points} points"
                )

                jump_data["history_index"] = len(history_lines) - 1

                counter += 1
                current_combo = "Combo Jump"

            else:
                history_lines.append(
                    f"    {element_name} - Level {level} - {points} points"
                )

                jump_data["history_index"] = len(history_lines) - 1

            state.combo_engine.jump_combos[-1].append(jump_data)

        # -------- SOLO JUMP --------
        else:
            history_lines.append(
                f"{counter}. Solo Jump - {element_name} - Level {level} - {points} points"
            )

            jump_data["history_index"] = len(history_lines) - 1

            counter += 1
            current_combo = None

        total_technique += points
        refresh_center()
        return

    # =====================================================
    # ==================== PIROUETTES =====================
    # =====================================================
    if section_name in ("Solo Spin", "Combo Spin"):

        spin_data = {
            "code": element,
            "level": level,
            "points": points,
            "type": "combo" if section_name == "Combo Spin" else "solo",
            "history_index": None
        }

        state.scoring_engine.spins.append(spin_data)

        # -------- COMBO SPIN --------
        if section_name == "Combo Spin":

            state.combo_engine.has_spin_combo = True

            if current_combo != "Combo Spin":

                history_lines.append(
                    f"{counter}. Combo Spin - {element_name} - Level {level} - {points} points"
                )

                spin_data["history_index"] = len(history_lines) - 1

                counter += 1
                current_combo = "Combo Spin"

            else:
                history_lines.append(
                    f"    {element_name} - Level {level} - {points} points"
                )

                spin_data["history_index"] = len(history_lines) - 1

        # -------- SOLO SPIN --------
        else:
            history_lines.append(
                f"{counter}. Solo Spin - {element_name} - Level {level} - {points} points"
            )

            spin_data["history_index"] = len(history_lines) - 1

            counter += 1
            current_combo = None

        total_technique += points
        refresh_center()
        return

    # =====================================================
    # ====================== FOOTWORK =====================
    # =====================================================
    if section_name == "Footwork Seq.":
        state.footwork_engine.current = level
        state.footwork_engine.current_points = points

        history_lines.append(
            f"{counter}. Footwork Seq. - Level {level} - {points} points"
        )

        counter += 1
        current_combo = None
        total_technique += points

        refresh_center()
        return


def on_penalty_click(label, points):
    global current_combo
    global total_penalites

    current_combo = None  # coupe une combo en cours

    total_penalites += points
    history_lines.append(f"{label} {points} points")
    refresh_center()
    recalc_totals()
            
def rows_buttons(parent, section_name, labels, level_colors):
    level_frame = tk.Frame(parent, bg=BG)
    level_frame.pack(anchor="w", pady=5)

    # Ligne contenant "Level" + boutons
    row = tk.Frame(level_frame, bg=BG)
    row.pack(anchor="w")

    tk.Label(
        row,
        text="Level",
        bg=BG,
        fg="white",
        font=("Arial", 14, "bold")
    ).pack(side="left", padx=(0, 1), pady=(0, 6))

    # Frame qui contiendra uniquement les boutons (IMPORTANT)
    buttons_frame = tk.Frame(row, bg=BG)
    buttons_frame.pack(side="left")

    row_buttons = tk.Frame(parent, bg=BG)
    row_buttons.pack(anchor="w", pady=10)

    for lbl in labels:
        tk.Button(
            row_buttons,
            text=lbl,
            **BTN_JUMP_STYLE,
            command=lambda e=lbl, bf=buttons_frame:
                on_element_click(section_name, e, bf, level_colors)
        ).pack(side="left", padx=5)
        
def on_element_click(section, element, buttons_frame, level_colors):
    global selected_element
    global active_buttons_frame
    selected_element = element

    #  Supprimer les anciens levels affichés ailleurs
    if active_buttons_frame and active_buttons_frame != buttons_frame:
        for widget in active_buttons_frame.winfo_children():
            widget.destroy()

    # Mettre à jour le frame actif
    active_buttons_frame = buttons_frame

    # Nettoyer le frame actuel (au cas où)
    for widget in buttons_frame.winfo_children():
        widget.destroy()

    for lv, color in level_colors.items():
        try:
            pts = get_points(section, element, lv)
        except Exception:
            pts = 0

        tk.Button(
            buttons_frame,
            text=f"{lv} ({pts})",
            bg=color,
            fg="white",
            font=("Arial", 10, "bold"),
            padx=6,
            pady=4,
            width=7,
            command=lambda l=lv, bf=buttons_frame:
                on_level_click(section, l, bf)
        ).pack(side="left", padx=5)

    # FORCER RAFRAÎCHISSEMENT
    buttons_frame.update_idletasks()
        
def on_level_click(section, level, buttons_frame):
    global selected_element
    global active_buttons_frame

    on_button_click(section, level, selected_element)

    # Supprimer les boutons après clic
    for widget in buttons_frame.winfo_children():
        widget.destroy()

    # Reset
    active_buttons_frame = None
    
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
    try:
        recalc_totals()
        global total_technique
        global confirm_popup
        totals = {"technique": total_technique}
        rules.validate(state, history_lines, totals)
        # mettre à jour la variable globale après validation
        total_technique = totals["technique"]
        refresh_center()
        if confirm_popup:
            show_validation_popup()
        confirm_popup = True
    except RulesError as e:
        messagebox.showerror("Erreur de règle", str(e))

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
        f"Resultat_{LEVEL}_FREE_{CATEGORIE}_{GENRE}_{root.nom}_{root.prenom}_{root.club}.pdf"
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
    story.append(Paragraph("<b>Notation Freeskating Régional</b>", styles["Title"]))
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
        "Footwork Seq.": "Footwork Sequence",
    }
    
    # =====================================================
    # ÉLÉMENTS TECHNIQUES
    # =====================================================
    story.append(Paragraph("<b>Éléments techniques</b>", styles["Heading2"]))
    story.append(Spacer(1, 5))

    elements_data = [["#", "Élément", "Niveau", "Points"]]

    last_label = ""        # ex: "1. Combo Jump"
    last_section = ""      # ex: "Combo Jump"

    for line in history_lines:
        if "points" not in line:
            continue

        try:
            is_child = line.startswith("    ")
            clean = line.strip()
            parts = clean.split(" - ")

            # ================= FOOTWORK =================
            if "Footwork Seq." in clean:
                label = parts[0]
                element = "Footwork Sequence"
                # Mapping nom pour correspondance DB
                lookup_name = mapping.get(element, element)

                # Injection KP
                if lookup_name in kp_dict:
                    kp_text = ", ".join(kp_dict[lookup_name])
                    element_display = f"{element} ({kp_text})"
                else:
                    element_display = element
                level = parts[1].replace("Level ", "").strip()
                points = parts[2].replace(" points", "").strip()

                elements_data.append([
                    label,
                    element_display,
                    level,    # ✅ niveau propre (1, 2, 3…)
                    points    # ✅ points seuls
                ])
                continue


            # ================= LIGNE PRINCIPALE =================
            if not is_child:
                element_name = ELEMENT_NAMES.get(parts[1], parts[1])
                element = f"{element_name} ({parts[1]})"
                label = parts[0]
                raw_points = parts[3]
                no_combo = "(no combo)" in raw_points

                # extraction propre du nombre
                points = re.search(r"-?\d+(\.\d+)?", raw_points).group()
                points = float(points)

                if no_combo:
                    element = f"{element} No combo"

                level = parts[2].replace("Level ", "")
                elements_data.append([
                    label,
                    element,
                    level,
                    points
                ])

            # ================= LIGNE COMBO =================
            else:
                element_name = ELEMENT_NAMES.get(parts[0], parts[0])
                element = f"{element_name} ({parts[0]})"
                level = parts[1].replace("Level ", "")
                raw_points = parts[2]
                no_combo = "(no combo)" in raw_points

                # extraction propre du nombre
                points = re.search(r"-?\d+(\.\d+)?", raw_points).group()
                points = float(points)
                if no_combo:
                    element = f"{element} No combo"
                
                elements_data.append([
                    "",
                    element,
                    level,
                    points
                ])

        except Exception as e:
            print("PDF PARSE ERROR:", e, clean)

    # ===== TABLE DES ÉLÉMENTS TECHNIQUES =====
    table = Table(elements_data, colWidths=[90, 230, 60, 60])
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
    # DÉDUCTIONS / PÉNALITÉS
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

    doc.build(story)
    if get("message_box_pdf"):
        messagebox.showinfo(
            "PDF généré",
            f"Le fichier PDF a été créé :\n{filename}"
        )
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

    output_dir = os.path.join(os.getcwd(), f"result\\FREE\\{LEVEL}")
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(
        output_dir,
        f"Classement_FREE_{LEVEL}_{CATEGORIE}_{GENRE}.pdf"
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

    # ================= PAGE 1 : CLASSEMENT =================
    story.append(Paragraph(
        f"<b>Classement – Freeskating {LEVEL} {CATEGORIE} {GENRE}</b>",
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

        # Si différent → nouveau rang
        if total != last_total or sc != last_sc:
            current_rank += 1

        # Sauvegarde pour comparaison
        last_total = total
        last_sc = sc

        table_data.append([
            current_rank,  
            nom, prenom, club,
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
        ("FONTSIZE", (0,0), (-1,-1), 6), #taille 6 petit
    ]))

    story.append(table)

    # ================= PAGES DÉTAILLÉES =================
    last_total = None
    last_sc = None
    current_rank = 0

    for row in rows:
        resultat_id, nom, prenom, club, ordre, st, sc, pen, total, medal = row

        # Nouveau rang si différent
        if total != last_total or sc != last_sc:
            current_rank += 1

        # Sauvegarde
        last_total = total
        last_sc = sc

        place = current_rank

        story.append(PageBreak())

        # =====================================================
        # TITRE
        # =====================================================
        story.append(Paragraph(
            f"<b>Rang {place}</b>",
            styles["Title"]
        ))
        story.append(Spacer(1, 10))

        story.append(Paragraph(
            f"<b>Patineur :</b> {nom} {prenom} - {club}<br/>"
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
            "Footwork Seq.": "Footwork Sequence",
        }
        # =====================================================
        # ÉLÉMENTS TECHNIQUES
        # =====================================================
        story.append(Paragraph("<b>Éléments techniques</b>", styles["Heading2"]))
        story.append(Spacer(1, 5))

        elements_data = [["#", "Élément", "Niveau", "Points"]]

        cur.execute("""
            SELECT
                element_type,
                element_label,
                niveau,
                points,
                parent_ordre
            FROM details_resultats
            WHERE resultat_id = ?
              AND type = 'technique'
            ORDER BY ordre
        """, (resultat_id,))

        rows_tech = cur.fetchall()

        counter_local = 1
        for element_type, label, niveau, points, parent in rows_tech:
            def parse_label(label):
                no_combo = False
                # détecte le flag
                if label.endswith(" B"):
                    no_combo = True
                    label = label[:-2]  # enlève " B"

                return label, no_combo
            if parent is None:
                # Mapping nom pour correspondance DB
                lookup_name = mapping.get(element_type, element_type)

                # Injection KP
                if lookup_name in kp_dict:
                    kp_text = ", ".join(kp_dict[lookup_name])
                    element_display = f"{kp_text}"
                elif element_type == "Footwork Seq.":
                    element_display = "Footwork Seq."
                else:
                    label, no_combo = parse_label(label)
                    element_name = ELEMENT_NAMES.get(label, label)
                    element_display = f"{element_name} ({label})"
                    if no_combo:
                        element_display = f"{element_display} No combo"
                elements_data.append([
                    f"{counter_local}. {element_type}",
                    element_display,
                    "" if niveau is None else niveau,
                    f"{points:.1f}".rstrip("0").rstrip(".")
                ])
                counter_local += 1
            else:
                label, no_combo = parse_label(label)
                element_name = ELEMENT_NAMES.get(label, label)
                element_display = f"{element_name} ({label})"

                if no_combo:
                    element_display = f"{element_display} No combo"
                elements_data.append([
                    "",
                    element_display,
                    niveau,
                    f"{points:.1f}".rstrip("0").rstrip(".")
                ])

        tech_table = Table(elements_data, colWidths=[90, 230, 60, 60])
        tech_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("GRID", (0,0), (-1,-1), 0.5, colors.black),
            ("ALIGN", (2,1), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))

        story.append(tech_table)
        story.append(Spacer(1, 12))

        # =====================================================
        # COMPOSANTES
        # =====================================================
        story.append(Paragraph("<b>Composantes</b>", styles["Heading2"]))
        story.append(Spacer(1, 5))

        comp_data = [["Composante", "Points"]]


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

    last_score_total = None
    last_score_comp = None
    current_rank = 0

    for (nom, prenom, club, ordre, score_total, score_composantes) in rows:

        # Si différent du précédent → on incrémente
        if score_total != last_score_total or score_composantes != last_score_comp:
            current_rank += 1

        # Sinon → même rank (ex aequo)

        # Sauvegarde pour comparaison
        last_score_total = score_total
        last_score_comp = score_composantes

        # Trouver le patineur actuel
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
            2: "Correcte",
            3: "Bonne"
        }

        names = [
            "Posture",
            "Vitesse",
            "Qualité de patinage",
            "Chorégraphie",
            "Implication",
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
                width=18,
                anchor="w"
            ).grid(row=r, column=0, padx=2, pady=6)

            for c, val in enumerate((0.5, 1, 2, 3), start=1):

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
            "Posture", "Vitesse", "Qualité de patinage",
            "Chorégraphie", "Implication", "Attitudes"
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
    popup_width = 840
    popup_height = 220

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
            width=16,
            anchor="w"
        ).pack(side="left")

        frame = tk.Frame(row, bg=BG)
        frame.pack(side="left")

        def refresh():
            for widget in frame.winfo_children():
                widget.destroy()

            if (engine.level == "0") :
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
                    width=15,
                    font=("Arial", 11, "bold"),
                    bg="#7ED957" if selected else "#4e5a73",
                    fg="black" if selected else "white",
                    command=lambda o=opt: on_click(o)
                ).pack(side="left", padx=4)

        def on_click(value):
            engine.toggle(value)
            refresh()

        refresh()
    if (LEVEL == "R2"):
        # Footwork Sequence R2
        create_sequence_ui(
            popup,
            "Footwork Sequence",
            state.pattern_foots_engine,
            ["Trois dehors", "Trois dedans", "Mk dehors", "Mk dedans"]
        )
    if (LEVEL == "R1"):
        # Footwork Sequence R1
        create_sequence_ui(
            popup,
            "Footwork Sequence",
            state.pattern_foots_engine,
            ["TrG", "TrD", "Mk", "Trois"]
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
            resultat_id = sauvegarder_resultat()  
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
        # récupère le nombre avant "points"
        match = re.search(r"(-?\d+(\.\d+)?)\s*points", line)
        if match:
            return float(match.group(1))
        return 0
    except:
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

    # ✅ Mise à jour CONTEXTE
    root.nom = nom
    root.prenom = prenom
    root.club = club
    current_ordre = ordre

    # ✅ Relance propre SANS TOUCHER current_ordre
    reset_evaluation()

def sauvegarder_resultat():
    global current_categorie_id, current_ordre

    total_composantes = calcul_total_composantes()
    score_total = total_technique + total_penalites + total_composantes

    # ----- JUMPS -----
    jumps = state.scoring_engine.jumps
    jump_points = sum(j.get("points", 0) for j in jumps if j.get("level") != "*")

    valid_jumps = [
        j for j in jumps
        if j.get("points", 0) > 0 and j.get("level") != "*"
    ]

    # ----- SPINS -----
    spins = state.scoring_engine.spins
    spin_points = [
        s.get("points", 0)
        for s in spins
        if s.get("level") != "*"
    ]

    best_spin = max(spin_points) if spin_points else 0

    # ----- FOOTWORK -----
    footwork = getattr(state.footwork_engine, "current_points", 0)
    medal=" "
    # ----------------------------
    # MÉDAILLE BRONZE (la plus haute en premier)
    # ----------------------------
    if (
        jump_points >= 5
        and len(valid_jumps) >= 4
        and best_spin >= 4
        and footwork >= 4
    ):
        medal = "Bronze Free"

    # ----------------------------
    # MÉDAILLE PRÉLIMINAIRE
    # ----------------------------
    elif (
        jump_points >= 2
        and best_spin >= 4
        and footwork >= 2
    ):
        medal = "Préliminaire Free"

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # ==================================================
    # 1️ RÉSULTAT PRINCIPAL
    # ==================================================
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

    resultat_id = cur.lastrowid

    # ==================================================
    # 2️ DÉTAILS TECHNIQUES (AVEC COMBOS COMPLETS)
    # ==================================================
    ordre_local = 1
    parent_stack = []

    for line in history_lines:

        # ignorer pénalités
        if not line[:1].isdigit() and not line.startswith("    "):
            continue

        is_child = line.startswith("    ")
        clean = line.strip()
        parts = clean.split(" - ")

        points = float(re.search(r"-?\d+(\.\d+)?", parts[-1]).group())

        if not is_child:
            # LIGNE PRINCIPALE
            element_type = parts[0].split(". ", 1)[1]
            element_label = parts[1]

            # AJOUT NO COMBO
            if "(no combo)" in clean:
                element_label = f"{element_label} B"

            if element_type == "Footwork Seq.":
                niveau = int(parts[1].replace("Level ", "").strip())
            else:
                raw = parts[2].replace("Level ", "").strip()
                if raw.isdigit():
                    niveau = int(raw)
                else:
                    niveau="*"

            cur.execute("""
                INSERT INTO details_resultats (
                    resultat_id, discipline, type,
                    ordre, parent_ordre,
                    element_type, element_code, element_label,
                    niveau, points
                )
                VALUES (?, 'FREE', 'technique',
                        ?, NULL,
                        ?, NULL, ?,
                        ?, ?)
            """, (
                resultat_id,
                ordre_local,
                element_type,
                element_label,
                niveau,
                points
            ))

            parent_stack.append(ordre_local)
            ordre_local += 1

        else:
            # SOUS-ÉLÉMENT DE COMBO
            element_label = parts[0]

            # AJOUT NO COMBO
            if "(no combo)" in clean:
                element_label = f"{element_label} B"
                
            raw = parts[1].replace("Level ", "").strip()
            if raw.isdigit():
                niveau = int(raw)
            else:
                niveau="*"

            parent = parent_stack[-1]

            cur.execute("""
                INSERT INTO details_resultats (
                    resultat_id, discipline, type,
                    ordre, parent_ordre,
                    element_type, element_code, element_label,
                    niveau, points
                )
                VALUES (?, 'FREE', 'technique',
                        ?, ?,
                        NULL, NULL, ?,
                        ?, ?)
            """, (
                resultat_id,
                ordre_local,
                parent,
                element_label,
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
    for foots in state.pattern_foots_engine.selected:
        cur.execute("""
            INSERT INTO assessment_details (resultat_id, name, value)
            VALUES (?, ?, ?)
        """, (
            resultat_id,
            "Footwork Sequence",
            foots
        ))
        
    for attitude in state.pattern_composantes_engine.values:
        if attitude["name"] == "Attitudes":
            cur.execute("""
                INSERT INTO assessment_details (resultat_id, name, value)
                VALUES (?, ?, ?)
            """, (
                resultat_id,
                attitude["name"],
                json.dumps(attitude["value"])  
            ))
            
    conn.commit()
    conn.close()
    return resultat_id




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

    rules = RulesR1R2(LEVEL)
    state = SessionState()
    root.title("Notation Freeskating Régional")
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
    # Couleurs des levels
    level_colors = {
        "0": "#ea4747",
        "1": "#08ace6",
        "2": "#91d153",
        "3": "#0dac50",
    }
    jump_labels = ["Wo", "T", "S", "Th", "F", "Lo", "Lz!", "Lz"]

    section(left, "Solo Jump")
    rows_buttons(left, "Solo Jump", jump_labels, level_colors)

    section_with_new(left, "Combo Jump", new_combo_jump, apply_no_combo_penalty)
    rows_buttons(left, "Combo Jump", jump_labels, level_colors)

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
        pady= 6,
        command=lambda: on_penalty_click("Time violation", -0.5)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Lyrics",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Lyrics", -1)
    ).pack(side="left", padx=5)

    tk.Button(
        row,
        text="Entry and exit",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Entry and exit", -0.5)
    ).pack(side="left", padx=5)

    row = tk.Frame(left, bg=BG)
    row.pack(anchor="w", pady=(20, 5))
    tk.Button(
        row,
        text="Costume",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Costume", -1)
    ).pack(side="left", padx=5)
    
    tk.Button(
        row,
        text="Floor",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Floor", -1)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Outside the rink",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Outside the rink", -0.5)
    ).pack(side="left", padx=5)
    tk.Button(
        row,
        text="Fall",
        font=("Arial", 10, "bold"),
        bg="#4e5a73",
        fg="white",
        padx=6,
        pady= 6,
        command=lambda: on_penalty_click("Fall", -1)
    ).pack(side="left", padx=5)


    # ===== RIGHT =====
    level_colors = {
        "0": "#ea4747",
        "1": "#08ace6",
        "2": "#91d153",
        "3": "#0dac50",
        "4": "#00853a",
    }
    spin_labels = ["Ufo", "Ubi", "Ubo", "Sfo", "Sbi", "Sbo", "Cfo", "Cbi", "Cbo"]

    section(right, "Solo Spin")
    rows_buttons(right, "Solo Spin", spin_labels, level_colors)

    section_with_new(right, "Combo Spin", new_combo_spin)
    rows_buttons(right, "Combo Spin", spin_labels, level_colors)

    # === FOOTWORK SUR UNE SEULE LIGNE ===
    row = tk.Frame(right, bg=BG)
    row.pack(anchor="w", pady=(20, 5))

    tk.Label(
        row,
        text="Footwork Seq.",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=BG
    ).pack(side="left", padx=(0, 15))

    level_rows = [
        ("0", "#ea4747"),
        ("1", "#08ace6"),
        ("2", "#91d153"),
        ("3", "#0dac50"),
        ("4", "#00853a"),
    ]

    for level, color in level_rows:
        tk.Button(
            row,
            text=level,
            bg=color,
            pady= 6,
            **BTN_STYLE,
            command=lambda l=level: on_button_click("Footwork Seq.", l, l)
        ).pack(side="left", padx=7)


    # Bottom
    bottom = tk.Frame(root, bg=BG)
    bottom.pack(fill="x", pady=20)

    # Delete Last SOUS le rectangle bleu (centré)
    delete_frame = tk.Frame(content, bg=BG)
    delete_frame.grid(row=1, column=1, pady=10)

    def delete_last():
        global counter, current_combo
        global total_technique, total_penalites

        if not history_lines:
            return

        removed = history_lines.pop()

        # mise à jour des totaux
        points = extract_points(removed)
        if points < 0:
            total_penalites -= points
        else:
            total_technique -= points

        # --- LIGNE INDENTÉE (élément de combo) ---
        if removed.startswith("    "):
            if "Spin" in removed:
                if state.scoring_engine.spins:
                    state.scoring_engine.spins.pop()

            elif "Jump" in removed:
                if state.scoring_engine.jumps:
                    state.scoring_engine.jumps.pop()

        # --- LIGNE PRINCIPALE ---
        else:
            counter -= 1
            current_combo = None

            if "Solo Spin" in removed:
                if state.scoring_engine.spins:
                    state.scoring_engine.spins.pop()

            elif "Combo Spin" in removed:
                while state.scoring_engine.spins and \
                      state.scoring_engine.spins[-1]["type"] == "combo":
                    state.scoring_engine.spins.pop()
                state.combo_engine.has_spin_combo = False

            elif "Solo Jump" in removed:
                if state.scoring_engine.jumps:
                    state.scoring_engine.jumps.pop()

            elif "Combo Jump" in removed:
                if state.combo_engine.jump_combos:
                    combo = state.combo_engine.jump_combos.pop()
                    for _ in combo:
                        if state.scoring_engine.jumps:
                            state.scoring_engine.jumps.pop()

            elif "Footwork Seq." in removed:
                state.footwork_engine.current = None

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
