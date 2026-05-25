# Modules standard
import os
import sys
import time
import json
import errno
import socket
import sqlite3
import csv
import subprocess
from pathlib import Path

# Tkinter
import tkinter as tk
from tkinter import messagebox, filedialog

# ReportLab pour les PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# Modules externes
from PIL import Image, ImageTk

# Modules personnalisés
from config import get, set

DB_FILE = "competitions.db"

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

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # TABLE : compétition
    cur.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)

    # TABLE : catégorie
    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER NOT NULL,
            discipline TEXT NOT NULL,
            niveau TEXT NOT NULL,
            categorie TEXT NOT NULL,
            genre TEXT NOT NULL,
            UNIQUE (competition_id, discipline, niveau, categorie, genre),
            FOREIGN KEY (competition_id) REFERENCES competitions(id)
        )
    """)

    # TABLE : patineur
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patineurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categorie_id INTEGER NOT NULL,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL,
        club TEXT NOT NULL,
        ordre INTEGER NOT NULL,
        UNIQUE (categorie_id, nom, prenom, club),
        UNIQUE (categorie_id, ordre),
        FOREIGN KEY (categorie_id) REFERENCES categories(id)
    )
    """)

    # TABLE : resultat
    cur.execute("""
    CREATE TABLE IF NOT EXISTS resultats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categorie_id INTEGER,
    nom TEXT,
    prenom TEXT,
    club TEXT,
    ordre INTEGER,
    score_technique REAL,
    score_composantes REAL,
    penalites REAL,
    score_total REAL,
    medal TEXT,
    FOREIGN KEY (categorie_id) REFERENCES categories(id)
    )
    """)

    # TABLE : détail par patineur
    cur.execute("""
        CREATE TABLE IF NOT EXISTS details_resultats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            resultat_id INTEGER NOT NULL,

            discipline TEXT NOT NULL,          -- 'FREE' ou 'DANSE'
            type TEXT NOT NULL,                -- 'technique', 'composante', 'penalite'

            ordre INTEGER,                     -- ordre d’affichage
            parent_ordre INTEGER,              -- pour combo (NULL sinon)

            element_type TEXT,                 -- 'Solo Jump', 'Combo Jump', 'Footwork Seq.', 'Spin'
            element_code TEXT,                 -- 'Wo', 'T', 'S', 'Footwork', NULL en danse
            element_label TEXT,                -- 'Waltz Outside', 'Toe Loop', 'Footwork Sequence'

            niveau INTEGER,                    -- 0,1,2,3… (NULL si non applicable)
            points REAL NOT NULL,

            FOREIGN KEY(resultat_id) REFERENCES resultats(id)
        )
    """)
    
    # TABLE : détail de l'evaluation
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessment_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resultat_id INTEGER,
            name TEXT,
            value TEXT,
            FOREIGN KEY(resultat_id) REFERENCES resultats(id)
        )
    """)

    conn.commit()
    conn.close()

init_db()

def ouvrir_competition(comp_id, comp_name):
    refresh_display()
    popup = tk.Toplevel(root)
    popup.title(comp_name)
    popup.configure(bg=get("background_color"))

    popup_width = 500
    popup_height = 300

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Vérifie si la compétition a des catégories
    cur.execute("""
        SELECT COUNT(*)
        FROM categories
        WHERE competition_id = ?
    """, (comp_id,))
    nb_categories = cur.fetchone()[0]

    tk.Label(
        popup,
        text=comp_name,
        font=("Arial", 18, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=20)

    # ===== SUPPRESSION UNIQUEMENT SI AUCUNE CATÉGORIE =====
    if nb_categories == 0:
        def supprimer_competition():
            cur.execute("DELETE FROM competitions WHERE id = ?", (comp_id,))
            conn.commit()
            conn.close()
            popup.destroy()
            refresh_display()

        tk.Label(
            popup,
            text="Aucune catégorie liée → suppression possible",
            fg="#7ED957",
            bg=get("background_color"),
            font=("Arial", 12)
        ).pack(pady=10)

        tk.Button(
            popup,
            text="Supprimer la compétition",
            bg="#fc6c6c",
            font=("Arial", 12, "bold"),
            command=supprimer_competition
        ).pack(pady=20)

    else:
        tk.Label(
            popup,
            text=f"{nb_categories} catégorie(s) associée(s)\nSuppression impossible",
            fg="#fc6c6c",
            bg=get("background_color"),
            font=("Arial", 12)
        ).pack(pady=20)

        conn.close()
    tk.Button(
        popup,
        text="Annuler",
        font=("Arial", 12, "bold"),
        bg="#fcfdff",
        fg="black",
        command=lambda: popup.destroy()
    ).pack(pady=10)

def ouvrir_categorie(cat_id, texte_categorie):
    refresh_display()
    popup = tk.Toplevel(root)
    popup.title("Catégorie")
    popup.configure(bg=get("background_color"))

    popup_width = 500
    popup_height = 320

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # récupérer le nom de la compétition via la catégorie
    cur.execute("""
        SELECT competitions.name
        FROM categories
        JOIN competitions
            ON categories.competition_id = competitions.id
        WHERE categories.id = ?
    """, (cat_id,))

    result = cur.fetchone()

    competition_name = result[0] if result else "Compétition inconnue"

    # Titre
    tk.Label(
        popup,
        text=competition_name,
        font=("Arial", 18, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack()
   
    # Vérifie le nombre de patineurs
    cur.execute("""
        SELECT COUNT(*)
        FROM patineurs
        WHERE categorie_id = ?
    """, (cat_id,))

    nb_patineurs = cur.fetchone()[0]

    tk.Label(
        popup,
        text=texte_categorie,
        font=("Arial", 14, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=10)

    # ===== SUPPRESSION SI 0 PATINEUR =====
    if nb_patineurs == 0:

        def supprimer_categorie():
            cur.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
            conn.commit()
            conn.close()
            popup.destroy()
            refresh_display()

        tk.Label(
            popup,
            text="0 patineur → suppression possible",
            fg="#7ED957",
            bg=get("background_color"),
            font=("Arial", 12)
        ).pack(pady=10)

        tk.Button(
            popup,
            text="Supprimer la catégorie",
            bg="#fc6c6c",
            fg="black",
            font=("Arial", 12, "bold"),
            command=supprimer_categorie
        ).pack(pady=20)

    else:

        # Vérifie le nombre de résultats
        cur.execute("""
            SELECT COUNT(DISTINCT nom || prenom || club || ordre)
            FROM resultats
            WHERE categorie_id = ?
        """, (cat_id,))

        nb_resultats = cur.fetchone()[0]

        # ===============================
        # IMPRESSION POSSIBLE SI 0 RESULTAT
        # ===============================
        if nb_resultats == 0:

            # Infos catégorie
            cur.execute("""
                SELECT discipline, niveau, categorie, genre
                FROM categories
                WHERE id = ?
            """, (cat_id,))

            DISCIPLINE, LEVEL, CATEGORIE, GENRE = cur.fetchone()

            # Liste des patineurs
            cur.execute("""
                SELECT ordre, nom, prenom, club
                FROM patineurs
                WHERE categorie_id = ?
                ORDER BY ordre ASC
            """, (cat_id,))

            patineurs = cur.fetchall()

            # ========= PDF =========
            def imprimer_pdf():

                output_dir = filedialog.askdirectory(
                    title="Choisir le dossier du PDF"
                )

                if not output_dir:
                    return

                filename = os.path.join(
                    output_dir,
                    f"Ordre de passage_{DISCIPLINE}_{LEVEL}_{CATEGORIE}_{GENRE}.pdf"
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

                story.append(Paragraph(
                    f"<b>Ordre de passage – "
                    f"{DISCIPLINE} {LEVEL} {CATEGORIE} {GENRE}</b>",
                    styles["Title"]
                ))

                story.append(Spacer(1, 20))

                table_data = [[
                    "Rang",
                    "Nom",
                    "Prénom",
                    "Club"
                ]]

                for ordre, nom, prenom, club in patineurs:
                    table_data.append([
                        ordre,
                        nom,
                        prenom,
                        club
                    ])

                table = Table(table_data, colWidths=[60, 140, 140, 140])

                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                    ("ALIGN", (2,1), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ]))

                story.append(table)

                doc.build(story)

                messagebox.showinfo(
                    "PDF",
                    "PDF généré avec succès"
                )

            # ========= CSV =========
            def exporter_csv():

                output_dir = filedialog.askdirectory(
                    title="Choisir le dossier du CSV"
                )

                if not output_dir:
                    return

                filename = os.path.join(
                    output_dir,
                    f"Ordre de passage_{DISCIPLINE}_{LEVEL}_{CATEGORIE}_{GENRE}.csv"
                )

                with open(filename, mode="w", newline="", encoding="utf-8") as file:

                    writer = csv.writer(file, delimiter=",")

                    writer.writerow([
                        "Rang",
                        "Nom",
                        "Prénom",
                        "Club"
                    ])

                    for ordre, nom, prenom, club in patineurs:
                        writer.writerow([
                            ordre,
                            nom,
                            prenom,
                            club
                        ])

                messagebox.showinfo(
                    "CSV",
                    "CSV généré avec succès"
                )

            tk.Label(
                popup,
                text="Aucun résultat enregistré\nImpression autorisée",
                fg="#7ED957",
                bg=get("background_color"),
                font=("Arial", 12)
            ).pack(pady=10)

            tk.Button(
                popup,
                text="Exporter l'ordre de passage en PDF",
                bg="#7ED957",
                fg="black",
                font=("Arial", 12, "bold"),
                command=imprimer_pdf
            ).pack(pady=10)

            tk.Button(
                popup,
                text="Exporter l'ordre de passage en CSV",
                bg="#58a6ff",
                fg="black",
                font=("Arial", 12, "bold"),
                command=exporter_csv
            ).pack(pady=10)

        # ===============================
        # RESULTATS TERMINÉS
        # ===============================
        elif nb_resultats == nb_patineurs:

            # Infos catégorie
            cur.execute("""
                SELECT discipline, niveau, categorie, genre
                FROM categories
                WHERE id = ?
            """, (cat_id,))

            DISCIPLINE, LEVEL, CATEGORIE, GENRE = cur.fetchone()

            tk.Label(
                popup,
                text="Tous les résultats sont enregistrés",
                fg="#7ED957",
                bg=get("background_color"),
                font=("Arial", 12, "bold")
            ).pack(pady=10)

            # ==========================================
            # PDF CLASSEMENT
            # ==========================================
            def exporter_resultats_pdf():

                output_dir = filedialog.askdirectory(
                    title="Choisir le dossier du PDF"
                )

                if not output_dir:
                    return

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
                    ORDER BY r.score_total DESC,
                            r.score_composantes DESC
                """, (cat_id,))

                rows = cur.fetchall()

                filename = os.path.join(
                    output_dir,
                    f"Classement_{DISCIPLINE}_{LEVEL}_{CATEGORIE}_{GENRE}.pdf"
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

                # ==========================================
                # PAGE CLASSEMENT
                # ==========================================
                story.append(Paragraph(
                    f"<b>Classement – "
                    f"{DISCIPLINE} {LEVEL} {CATEGORIE} {GENRE}</b>",
                    styles["Title"]
                ))

                story.append(Spacer(1, 20))

                table_data = [[
                    "Place",
                    "Nom",
                    "Prénom",
                    "Club",
                    "Technique",
                    "Composantes",
                    "Pénalités",
                    "Total",
                    "Médaille"
                ]]

                last_total = None
                last_sc = None
                current_rank = 0

                for (
                    _,
                    nom,
                    prenom,
                    club,
                    ordre,
                    st,
                    sc,
                    pen,
                    total,
                    medal
                ) in rows:

                    if total != last_total or sc != last_sc:
                        current_rank += 1

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
                        medal
                    ])

                table = Table(
                    table_data,
                    colWidths=[30, 70, 70, 100, 50, 55, 45, 45, 55]
                )

                table.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
                    ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                    ("ALIGN", (0,1), (-1,-1), "CENTER"),
                    ("FONTSIZE", (0,0), (-1,-1), 6),
                ]))

                story.append(table)

                 # ================= PAGES DÉTAILLÉES =================                
                last_total = None
                last_sc = None
                current_rank = 0

                for row in rows:

                    (
                        resultat_id,
                        nom,
                        prenom,
                        club,
                        ordre,
                        st,
                        sc,
                        pen,
                        total,
                        medal
                    ) = row

                    if total != last_total or sc != last_sc:
                        current_rank += 1

                    last_total = total
                    last_sc = sc

                    place = current_rank

                    story.append(PageBreak())

                    # ==========================================
                    # TITRE
                    # ==========================================
                    story.append(Paragraph(
                        f"<b>Rang {place}</b>",
                        styles["Title"]
                    ))

                    story.append(Spacer(1, 10))

                    story.append(Paragraph(
                        f"<b>Patineur :</b> "
                        f"{nom} {prenom} - {club}<br/>"
                        f"<b>Niveau :</b> "
                        f"{LEVEL} {CATEGORIE} {GENRE}",
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

                    if DISCIPLINE == "Freeskating":
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
                    
                    else :
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

                doc.build(story)

                conn.close()

                messagebox.showinfo(
                    "PDF",
                    f"Classement PDF généré :\n{filename}"
                )

            # ==========================================
            # CSV MÉDAILLES
            # ==========================================
            def exporter_medailles_csv():

                output_dir = filedialog.askdirectory(
                    title="Choisir le dossier du CSV"
                )

                if not output_dir:
                    return

                filename = os.path.join(
                    output_dir,
                    f"médailles techniques_"
                    f"{DISCIPLINE}_{LEVEL}_{CATEGORIE}_{GENRE}.csv"
                )

                cur.execute("""
                    SELECT
                        nom,
                        prenom,
                        club,
                        medal
                    FROM resultats
                    WHERE categorie_id = ?
                    AND medal IS NOT NULL
                    AND medal != ' '
                    ORDER BY score_total DESC
                """, (cat_id,))

                rows = cur.fetchall()

                with open(
                    filename,
                    mode="w",
                    newline="",
                    encoding="utf-8"
                ) as file:

                    writer = csv.writer(file, delimiter=",")

                    writer.writerow([
                        "Nom",
                        "Prénom",
                        "Club",
                        "Médaille"
                    ])

                    for nom, prenom, club, medal in rows:
                        if medal is not None and medal != "":

                            writer.writerow([
                                nom,
                                prenom,
                                club,
                                medal
                            ])

                messagebox.showinfo(
                    "CSV",
                    "CSV des médailles généré avec succès"
                )

            tk.Button(
                popup,
                text="Exporter le classement en PDF",
                bg="#7ED957",
                fg="black",
                font=("Arial", 12, "bold"),
                command=exporter_resultats_pdf
            ).pack(pady=10)

            tk.Button(
                popup,
                text="Exporter les médailles en CSV",
                bg="#58a6ff",
                fg="black",
                font=("Arial", 12, "bold"),
                command=exporter_medailles_csv
            ).pack(pady=10)

        # ===============================
        # EVALUATION EN COURS
        # ===============================
        else:

            tk.Label(
                popup,
                text="Impression impossible\nCatégorie en cours d'évaluation",
                fg="#fc6c6c",
                bg=get("background_color"),
                font=("Arial", 12, "bold")
            ).pack(pady=20)

            conn.close()

    tk.Button(
        popup,
        text="Annuler",
        font=("Arial", 12, "bold"),
        bg="#fcfdff",
        fg="black",
        command=popup.destroy
    ).pack(pady=10)

def apply_theme_selective(widget, old_bg, new_bg):
    """Change le bg seulement si l'ancien bg correspond"""
    try:
        current_bg = widget.cget("bg")
        if current_bg == old_bg:
            widget.configure(bg=new_bg)
    except tk.TclError:
        pass

    for child in widget.winfo_children():
        apply_theme_selective(child, old_bg, new_bg)

def exe_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# ================== UTILS ==================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ================== CONFIG ==================
BG = get("background_color")

root = tk.Tk()
root.title("Système de Notation Roller Artistique – Menu")
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
root.configure(bg=get("background_color"))
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))


# ================== ACTIONS (STUBS) ==================
def creer_competition():
    popup = tk.Toplevel(root)
    popup.title("Créer une compétition")
    popup.configure(bg=get("background_color"))

    popup_width = 600
    popup_height = 310

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    def importer_csv_categories():
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return

        # ===== NOM COMPETITION = NOM DU FICHIER =====
        competition_name = os.path.splitext(os.path.basename(path))[0]

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        try:
            # ===== CREER / RECUP COMPETITION =====
            cur.execute("SELECT id FROM competitions WHERE name = ?", (competition_name,))
            comp = cur.fetchone()

            if not comp:
                cur.execute("INSERT INTO competitions (name) VALUES (?)", (competition_name,))
                competition_id = cur.lastrowid
            else:
                competition_id = comp[0]

            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)

                for row in reader:
                    # ===== IGNORE LIGNES VIDES =====
                    if not row or all(not cell.strip() for cell in row):
                        continue

                    if len(row) < 7:
                        continue

                    try:
                        ordre = int(row[0].strip())
                        discipline_raw = row[1].strip().upper()
                        categorie = row[2].strip().capitalize()
                        nom = row[3].strip()
                        prenom = row[4].strip().capitalize()
                        genre = row[5].strip().upper()
                        club = club = " ".join(m.capitalize() for m in row[6].strip().split())

                        # ===== PARSE DISCIPLINE + NIVEAU =====
                        discipline = ""
                        niveau = ""

                        if "FREE" in discipline_raw:
                            discipline = "Freeskating"
                            if "R1" in discipline_raw:
                                niveau = "R1"
                            elif "R2" in discipline_raw:
                                niveau = "R2"

                        elif "DANSE" in discipline_raw:
                            discipline = "Danse"
                            niveau = "R"

                        else:
                            continue  # discipline inconnue

                        # ===== CATEGORIE =====
                        cur.execute("""
                            SELECT id FROM categories
                            WHERE competition_id=? AND discipline=? AND niveau=? AND categorie=? AND genre=?
                        """, (competition_id, discipline, niveau, categorie, genre))

                        cat = cur.fetchone()

                        if not cat:
                            cur.execute("""
                                INSERT INTO categories (competition_id, discipline, niveau, categorie, genre)
                                VALUES (?, ?, ?, ?, ?)
                            """, (competition_id, discipline, niveau, categorie, genre))
                            categorie_id = cur.lastrowid
                        else:
                            categorie_id = cat[0]

                        # ===== PATINEUR =====
                        try:
                            cur.execute("""
                                INSERT INTO patineurs (categorie_id, nom, prenom, club, ordre)
                                VALUES (?, ?, ?, ?, ?)
                            """, (categorie_id, nom, prenom, club, ordre))
                        except sqlite3.IntegrityError:
                            pass  # ignore doublons

                    except Exception as e:
                        print("Erreur ligne :", row, e)

            conn.commit()
            messagebox.showinfo("Succès", "Import terminé avec succès")
            refresh_display()

        except Exception as e:
            messagebox.showerror("Erreur", str(e))

        finally:
            conn.close()
   
    # ===== TITRE =====
    tk.Label(
        popup,
        text="Créer une compétition",
        font=("Arial", 18, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=20)

    # ===== FORMULAIRE =====
    form = tk.Frame(popup, bg=get("background_color"))
    form.pack(pady=20)

    tk.Label(
        form,
        text="Nom de la compétition :",
        font=("Arial", 14),
        fg="white",
        bg=get("background_color")
    ).grid(row=0, column=0, padx=10, pady=5)

    entry_name = tk.Entry(form, font=("Arial", 14), width=25)
    entry_name.grid(row=0, column=1, pady=5)

    # ===== ACTIONS =====
    def valider():
        name = entry_name.get().strip()

        if not name:
            messagebox.showerror("Erreur", "Veuillez renseigner un nom.")
            return

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("INSERT INTO competitions (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()

        popup.destroy()
        refresh_display()

    def annuler():
        popup.destroy()

    btns = tk.Frame(popup, bg=get("background_color"))
    btns.pack(pady=30)

    tk.Button(
        btns,
        text="Valider",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=12,
        command=valider
    ).pack(side="left", padx=10)

    tk.Button(
        btns,
        text="Annuler",
        font=("Arial", 12, "bold"),
        bg="#fc6c6c",
        width=12,
        command=annuler
    ).pack(side="left", padx=10)

    
    tk.Button(
        popup,
        text="Importer un CSV",
        font=("Arial", 12, "bold"),
        bg="#4e5a73",
        fg="white",
        width=25,
        command=importer_csv_categories
    ).pack(pady=10)

def creer_categorie():
    popup = tk.Toplevel(root)
    popup.title("Créer une catégorie")
    popup.configure(bg=get("background_color"))

    popup_width = 520
    popup_height = 480

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    # ===== TITRE =====
    tk.Label(
        popup,
        text="Créer une catégorie",
        font=("Arial", 18, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=15)

    form = tk.Frame(popup, bg=get("background_color"))
    form.pack(pady=10)

    # ===== DONNÉES =====
    disciplines = ["Freeskating", "Danse"]

    niveaux_free = ["R1", "R2"]
    niveaux_danse = ["R"]

    categories = ["Avenir", "Poussin", "Mini", "Espoir", "Cadet", "Jeunesse", "Junior", "Senior"]
    genres = ["F", "M"]


    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM competitions")
    competitions = cur.fetchall()
    conn.close()

    if not competitions:
        messagebox.showerror("Erreur", "Aucune compétition disponible.")
        popup.destroy()
        return

    comp_var = tk.StringVar(value=competitions[0][1])
    disc_var = tk.StringVar(value=disciplines[0])
    niv_var = tk.StringVar()
    cat_var = tk.StringVar(value=categories[0])
    gen_var = tk.StringVar(value=genres[0])

    # ===== FORMULAIRE =====
    tk.Label(form, text="Compétition", font=("Arial", 13, "bold"),
             fg="white", bg=get("background_color")).grid(row=0, column=0, sticky="e", padx=10, pady=6)

    tk.OptionMenu(form, comp_var, *[c[1] for c in competitions]).grid(
        row=0, column=1, sticky="w", pady=6
    )

    # Discipline
    tk.Label(form, text="Discipline", font=("Arial", 13, "bold"),
             fg="white", bg=get("background_color")).grid(row=1, column=0, sticky="e", padx=10, pady=6)

    disc_menu = tk.OptionMenu(form, disc_var, *disciplines)
    disc_menu.grid(row=1, column=1, sticky="w", pady=6)

    # Niveau (dynamique)
    tk.Label(form, text="Niveau", font=("Arial", 13, "bold"),
             fg="white", bg=get("background_color")).grid(row=2, column=0, sticky="e", padx=10, pady=6)

    niv_menu = tk.OptionMenu(form, niv_var, "")
    niv_menu.grid(row=2, column=1, sticky="w", pady=6)

    # Catégorie
    tk.Label(form, text="Catégorie", font=("Arial", 13, "bold"),
             fg="white", bg=get("background_color")).grid(row=3, column=0, sticky="e", padx=10, pady=6)

    tk.OptionMenu(form, cat_var, *categories).grid(
        row=3, column=1, sticky="w", pady=6
    )

    # Genre
    tk.Label(form, text="Genre", font=("Arial", 13, "bold"),
             fg="white", bg=get("background_color")).grid(row=4, column=0, sticky="e", padx=10, pady=6)

    tk.OptionMenu(form, gen_var, *genres).grid(
        row=4, column=1, sticky="w", pady=6
    )

    def update_niveaux(*_):
        menu = niv_menu["menu"]
        menu.delete(0, "end")

        if disc_var.get() == "Danse":
            niveaux = niveaux_danse
        else:
            niveaux = niveaux_free

        for n in niveaux:
            menu.add_command(label=n, command=lambda v=n: niv_var.set(v))

        niv_var.set(niveaux[0])  # valeur par défaut

    disc_var.trace_add("write", update_niveaux)
    update_niveaux()  # initialisation

    # ===== ACTIONS =====
    def valider():
        comp_name = comp_var.get()
        discipline = disc_var.get()
        niveau = niv_var.get()
        categorie = cat_var.get()
        genre = gen_var.get()

        comp_id = next(c[0] for c in competitions if c[1] == comp_name)

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        # Vérification doublon
        cur.execute("""
            SELECT 1 FROM categories
            WHERE competition_id = ?
              AND discipline = ?
              AND niveau = ?
              AND categorie = ?
              AND genre = ?
        """, (comp_id, discipline, niveau, categorie, genre))

        exists = cur.fetchone()

        if exists:
            conn.close()
            messagebox.showerror(
                "Doublon",
                "Cette catégorie existe déjà pour cette compétition."
            )
            return

        # Insertion
        cur.execute("""
            INSERT INTO categories
            (competition_id, discipline, niveau, categorie, genre)
            VALUES (?, ?, ?, ?, ?)
        """, (comp_id, discipline, niveau, categorie, genre))

        conn.commit()
        conn.close()

        popup.destroy()
        refresh_display()


    def annuler():
        popup.destroy()

    btns = tk.Frame(popup, bg=get("background_color"))
    btns.pack(pady=25)

    tk.Button(
        btns,
        text="Valider",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=12,
        command=valider
    ).pack(side="left", padx=10)

    tk.Button(
        btns,
        text="Annuler",
        font=("Arial", 12, "bold"),
        bg="#fc6c6c",
        width=12,
        command=annuler
    ).pack(side="left", padx=10)

def gerer_patineurs():
    popup = tk.Toplevel(root)
    popup.title("Gestion des patineurs")
    popup.configure(bg=get("background_color"))
    popup_width = 900
    popup_height = 650

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    # ================== DATA ==================
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            ca.id,
            comp.name || " – " || ca.discipline || " " || ca.niveau || " " || ca.categorie || " " || ca.genre
        FROM categories ca
        JOIN competitions comp ON ca.competition_id = comp.id
        WHERE NOT EXISTS (
            SELECT 1
            FROM resultats r
            WHERE r.categorie_id = ca.id
        )
        ORDER BY comp.name
    """)
    categories = cur.fetchall()
    if not categories:
        tk.Label(
            popup,
            text="Toutes les catégories ont déjà commencé à être évaluées",
            font=("Arial", 14, "italic"),
            fg="#fc6c6c",
            bg=get("background_color")
        ).pack(pady=30)
        # ===== FERMER =====
        tk.Button(
            popup,
            text="Fermer",
            font=("Arial", 12, "bold"),
            bg="#fc6c6c",
            width=20,
            command=lambda: (conn.close(), refresh_display(), popup.destroy())
        ).pack(pady=15)
        return

    # ================== VARIABLES ==================
    patineurs_map = {}  # index_listbox -> patineur_id
    cat_var = tk.StringVar()
    nom_var = tk.StringVar()
    prenom_var = tk.StringVar()
    club_var = tk.StringVar()
    ordre_var = tk.StringVar()

    selected_patineur_id = {"id": None}

    # ================== UI ==================
    tk.Label(
        popup,
        text="Sélectionner une catégorie",
        bg=get("background_color"), fg="white",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    cat_menu = tk.OptionMenu(
        popup, cat_var,
        *[c[1] for c in categories]
    )
    cat_menu.config(font=("Arial", 12))
    cat_menu.pack()

    # ===== LISTE PATINEURS =====
    list_frame = tk.Frame(popup, bg=get("background_color"))
    list_frame.pack(pady=15)

    scrollbar = tk.Scrollbar(list_frame, orient="vertical")

    listbox = tk.Listbox(
        list_frame,
        font=("Arial", 12),
        width=80,
        height=10,  # 👈 limite visible (≈ 10 lignes)
        yscrollcommand=scrollbar.set
    )

    scrollbar.config(command=listbox.yview)

    listbox.pack(side="left")
    scrollbar.pack(side="right", fill="y")

    def refresh_list():
        listbox.delete(0, tk.END)
        patineurs_map.clear()
        selected_patineur_id["id"] = None
        if not cat_var.get():
            return

        cat_id = next(c[0] for c in categories if c[1] == cat_var.get())

        cur.execute("""
            SELECT id, nom, prenom, club, ordre
            FROM patineurs
            WHERE categorie_id = ?
            ORDER BY ordre
        """, (cat_id,))

        for pid, nom, prenom, club, ordre in cur.fetchall():
            index = listbox.size()
            listbox.insert(tk.END, f"{ordre}. {nom} {prenom} {club}")
            patineurs_map[index] = pid

    cat_var.trace_add("write", lambda *_: refresh_list())

    # ===== SELECTION LISTBOX =====
    def on_select(event):
        sel = listbox.curselection()
        if not sel:
            return

        index = sel[0]
        pat_id = patineurs_map.get(index)

        if not pat_id:
            return

        cur.execute("""
            SELECT nom, prenom, club, ordre
            FROM patineurs
            WHERE id = ?
        """, (pat_id,))
        row = cur.fetchone()

        if row:
            nom, prenom, club, ordre = row
            selected_patineur_id["id"] = pat_id
            nom_var.set(nom)
            prenom_var.set(prenom)
            club_var.set(club)
            ordre_var.set(str(ordre))

    listbox.bind("<<ListboxSelect>>", on_select)

    # ===== FORMULAIRE =====
    form = tk.Frame(popup, bg=get("background_color"))
    form.pack(pady=10)

    for i, (label, var) in enumerate([
        ("Nom", nom_var),
        ("Prénom", prenom_var),
        ("Club", club_var),
        ("Ordre", ordre_var)
    ]):
        tk.Label(
            form, text=label,
            bg=get("background_color"), fg="white",
            font=("Arial", 12, "bold")
        ).grid(row=i, column=0, padx=10, pady=5)

        tk.Entry(form, textvariable=var, width=40, font=("Arial", 12)).grid(
            row=i, column=1, padx=10, pady=5
        )

    # ===== ACTIONS =====
    def ajouter():
        if not cat_var.get() or not nom_var.get() or not prenom_var.get() or not club_var.get() or not ordre_var.get():
            messagebox.showerror("Erreur", "Tous les champs sont obligatoires")
            return

        cat_id = next(c[0] for c in categories if c[1] == cat_var.get())

        try:
            cur.execute("""
                INSERT INTO patineurs (categorie_id, nom, prenom, club, ordre)
                VALUES (?, ?, ?, ?, ?)
            """, (cat_id, nom_var.get(), prenom_var.get(), club_var.get(), int(ordre_var.get())))
            conn.commit()
            refresh_list()
        except sqlite3.IntegrityError:
            messagebox.showerror("Doublon", "Patineur ou ordre déjà existant")

    def modifier():
        if not selected_patineur_id["id"]:
            messagebox.showerror("Erreur", "Aucun patineur sélectionné")
            return

        try:
            cur.execute("""
                UPDATE patineurs
                SET nom = ?, prenom = ?, club = ?, ordre = ?
                WHERE id = ?
            """, (
                nom_var.get(),
                prenom_var.get(),
                club_var.get(),
                int(ordre_var.get()),
                selected_patineur_id["id"]
            ))
            conn.commit()
            refresh_list()
        except sqlite3.IntegrityError:
            messagebox.showerror("Doublon", "Ordre ou patineur déjà existant")

    def supprimer():
        if not selected_patineur_id["id"]:
            return

        cur.execute(
            "DELETE FROM patineurs WHERE id = ?",
            (selected_patineur_id["id"],)
        )
        conn.commit()
        refresh_list()

    # ===== IMPORT CSV =====
    def importer_csv():
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return

        if not cat_var.get():
            messagebox.showerror("Erreur", "Veuillez sélectionner une catégorie")
            return

        cat_id = next(c[0] for c in categories if c[1] == cat_var.get())

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=",")  #  adapte si besoin il faudra modifier (, ou ;)
            next(reader, None)  #  ignore l'en-tête

            for row in reader:
                # ignore lignes vides ou incorrectes
                if len(row) != 4:
                    continue

                nom, prenom, club, ordre = row
                club = " ".join(m.capitalize() for m in club.strip().split())
                try:
                    cur.execute("""
                        INSERT INTO patineurs (categorie_id, nom, prenom, club, ordre)
                        VALUES (?, ?, ?, ?, ?)
                    """, (cat_id, nom.strip(), prenom.strip().capitalize(), club, int(ordre)))
                except sqlite3.IntegrityError:
                    pass  # ignore doublons
                except ValueError:
                    pass  # ordre non numérique

        conn.commit()
        refresh_list()


    # ===== BOUTONS =====
    btns = tk.Frame(popup, bg=get("background_color"))
    btns.pack(pady=20)

    tk.Button(btns, text="Ajouter", width=15, command=ajouter).pack(side="left", padx=5)
    tk.Button(btns, text="Modifier", width=15, command=modifier).pack(side="left", padx=5)
    tk.Button(btns, text="Supprimer", width=15, command=supprimer).pack(side="left", padx=5)
    tk.Button(btns, text="Importer CSV", width=15, command=importer_csv).pack(side="left", padx=5)

    # ===== FERMER =====
    tk.Button(
        popup,
        text="Fermer",
        font=("Arial", 12, "bold"),
        bg="#fc6c6c",
        width=20,
        command=lambda: (conn.close(), refresh_display(), popup.destroy())
    ).pack(pady=15)


def evaluer_categorie():
    popup = tk.Toplevel(root)
    popup.title("Évaluer une catégorie")
    popup.configure(bg=get("background_color"))
    popup_width = 750
    popup_height = 420

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    tk.Label(
        popup,
        text="Sélectionner une catégorie à évaluer",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=15)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Catégories PARTIELLEMENT évaluées uniquement
    cur.execute("""
        SELECT
            ca.id,
            ca.discipline,
            ca.niveau,
            ca.categorie,
            ca.genre,
            comp.name,
            COUNT(DISTINCT p.id) AS nb_patineurs,
            COUNT(DISTINCT r.id) AS nb_resultats
        FROM categories ca
        JOIN competitions comp ON ca.competition_id = comp.id
        JOIN patineurs p ON p.categorie_id = ca.id
        LEFT JOIN resultats r ON r.categorie_id = ca.id
        GROUP BY ca.id
        HAVING nb_resultats < nb_patineurs
        ORDER BY comp.name
    """)

    rows = cur.fetchall()

    if not rows:
        conn.close()
        messagebox.showinfo(
            "Aucune catégorie",
            "Toutes les catégories ont déjà été entièrement évaluées."
        )
        popup.destroy()
        return

    choices = []
    mapping = {}

    for cid, discipline, niveau, cat, genre, comp, nb_p, nb_r in rows:
        label = f"{comp} – {discipline} | {niveau} | {cat} | {genre} ({nb_r}/{nb_p})"
        choices.append(label)
        mapping[label] = (cid, discipline, niveau, cat, genre, comp)

    cat_var = tk.StringVar(value=choices[0])
    tk.OptionMenu(popup, cat_var, *choices).pack(pady=20)

    def lancer():
        cid, discipline, niveau, categorie, genre, competition = mapping[cat_var.get()]

        cur.execute("""
            SELECT p.nom, p.prenom, p.club, p.ordre
            FROM patineurs p
            WHERE p.categorie_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM resultats r
                  WHERE r.categorie_id = p.categorie_id
                  AND r.ordre = p.ordre
              )
            ORDER BY p.ordre ASC
            LIMIT 1
        """, (cid,))

        patineur = cur.fetchone()
        if not patineur:
            messagebox.showinfo(
                "Catégorie terminée",
                "Tous les patineurs ont été évalués."
            )
            return

        nom, prenom, club, ordre = patineur
        conn.close()
        popup.destroy()

        # ===== CHOIX DU SCRIPT =====
        if discipline == "Freeskating":
            script = "FREE_REG"
        else:
            script = "DANSE_REG"

        base_dir = exe_dir()

        if getattr(sys, "frozen", False):
            # MODE EXE → on lance l'exe DIRECTEMENT
            exe_path = os.path.join(base_dir, f"{script}.exe")

            subprocess.Popen([
                exe_path,
                niveau,
                categorie,
                genre,
                competition,
                nom,
                prenom,
                club,
                str(ordre)
            ], shell=False)

        else:
            # MODE PY → on passe PAR PYTHON
            py_path = os.path.join(base_dir, f"{script}.py")

            subprocess.Popen([
                sys.executable,
                py_path,
                niveau,
                categorie,
                genre,
                competition,
                nom,
                prenom,
                club,
                str(ordre)
            ], shell=False)

    if get("DISPLAY_SERVER"):
        tk.Label(
            popup,
            text="✅ L'écran distant est activé pour l'évaluation.",
            fg="#00853a",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
        tk.Label(
            popup,
            text="⚠️ Vérifier que le serveur fonctionne bien sinon l'application va planter.",
            fg="#F58B27",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
        if get("DISPLAY_SERVER_BOUTON"):
            tk.Label(
            popup,
            text="❌ Un bouton est affichée pour envoyer les données à l'écran distant.",
            fg="#f40000",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
        else :
            tk.Label(
            popup,
            text="✅ Les données sont envoyée automatiquement à l'écran distant.",
            fg="#00853a",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
    else:
        tk.Label(
            popup,
            text="❌ L'écran distant n'est pas activé pour l'évaluation.",
            fg="#f40000",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
    if get("assessment_details"):
        tk.Label(
            popup,
            text="✅ L'évaluation en détail de ce qui a été évalué est activé.",
            fg="#00853a",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)
    else:
        tk.Label(
            popup,
            text="❌ L'évaluation en détail de ce qui a été évalué est désactivé.",
            fg="#f40000",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)

    btns = tk.Frame(popup, bg=get("background_color"))
    btns.pack(pady=30)
    tk.Button(
        btns,
        text="Lancer l’évaluation",
        font=("Arial", 13, "bold"),
        bg="#7ED957",
        width=20,
        command=lancer
    ).pack(side="left", padx=10)

    tk.Button(
        btns,
        text="Annuler",
        font=("Arial", 13, "bold"),
        bg="#fc6c6c",
        width=20,
        command=lambda: (conn.close(), popup.destroy())
    ).pack(side="left", padx=10)


def parametres():
    popup = tk.Toplevel(root)
    popup.title("Paramètres")
    popup.configure(bg=get("background_color"))
    popup_width = 900
    popup_height = 720

    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)  # bloque la croix

    tk.Label(
        popup,
        text="Paramètres",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14, "bold")
    ).pack(pady=10)

    tk.Label(
        popup,
        text="Les valeurs [ ] sont les valeurs de base du logiciel.",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(pady=10)

    # ================== BACKGROUND COLOR ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=20)
    tk.Label(
        line,
        text="Changer la couleur de fond (hex) : [#223A5E]",
        font=("Arial", 14),
        fg="white",
        bg=get("background_color")
    ).pack(side="left", padx=10)
    entry_bg = tk.Entry(line, font=("Arial", 14), width=15)
    entry_bg.insert(0, get("background_color"))
    entry_bg.pack(side="left", padx=10)

    # ================== COLOR DISPLAY ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=20)
    tk.Label(
        line,
        text="Changer la couleur du menu d'affichage (hex) : [#4472C4]",
        font=("Arial", 14),
        fg="white",
        bg=get("background_color")
    ).pack(side="left", padx=10)
    entry_dp = tk.Entry(line, font=("Arial", 14), width=15)
    entry_dp.insert(0, get("color_display"))
    entry_dp.pack(side="left", padx=10)

    # ================== ECRAN DISPLAY ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=10)
    tk.Label(
        line,
        text="Activer l'affichage de l'écran distant : [Non]",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(side="left", padx=10)
    display_var = tk.StringVar(
        value="Oui" if get("DISPLAY_SERVER") else "Non"
    )
    # Liste déroulante
    tk.OptionMenu(
        line,
        display_var,
        "Oui",
        "Non"
    ).pack(side="left", padx=20)

    # ================== BOUTON DISPLAY ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=10)
    tk.Label(
        line,
        text="Ajouter un bouton pour envoyer les données à l'écran distant : [Non]",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(side="left", padx=10)
    display_bouton = tk.StringVar(
        value="Oui" if get("DISPLAY_SERVER_BOUTON") else "Non"
    )
    # Liste déroulante
    tk.OptionMenu(
        line,
        display_bouton,
        "Oui",
        "Non"
    ).pack(side="left", padx=20)

    # ================== DISPLAY_SERVER_IP ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=20)
    tk.Label(
        line,
        text="Changer l'adresse IP du serveur : [192.168.1.50]",
        font=("Arial", 14),
        fg="white",
        bg=get("background_color")
    ).pack(side="left", padx=10)
    entry_ip = tk.Entry(line, font=("Arial", 14), width=15)
    entry_ip.insert(0, get("DISPLAY_SERVER_IP"))
    entry_ip.pack(side="left", padx=10)

    # ================== DISPLAY_SERVER_PORT ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=20)
    tk.Label(
        line,
        text="Changer l'adresse du port du serveur : [5000]",
        font=("Arial", 14),
        fg="white",
        bg=get("background_color")
    ).pack(side="left", padx=10)
    entry_port = tk.Entry(line, font=("Arial", 14), width=15)
    entry_port.insert(0, get("DISPLAY_SERVER_PORT"))
    entry_port.pack(side="left", padx=10)

    # ================== MESSAGE BOX PATINEUR ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=10)
    tk.Label(
        line,
        text="Affichage du message de génération du PDF à chaque patineur : [Non]",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(side="left", padx=10)
    # Variable texte (Oui / Non)
    pdf_message_var = tk.StringVar(
        value="Oui" if get("message_box_pdf") else "Non"
    )
    # Liste déroulante
    tk.OptionMenu(
        line,
        pdf_message_var,
        "Oui",
        "Non"
    ).pack(side="left", padx=20)

    # ================== MESSAGE BOX CLASSEMENT ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=10)
    tk.Label(
        line,
        text="Affichage du message de génération du PDF à la fin de la catégorie : [Oui]",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(side="left", padx=10)
    pdf_message_all_var = tk.StringVar(
        value="Oui" if get("message_box_all_pdf") else "Non"
    )
    # Liste déroulante
    tk.OptionMenu(
        line,
        pdf_message_all_var,
        "Oui",
        "Non"
    ).pack(side="left", padx=20)

    # ================== ASSESSMENT DETAILS ==================
    line = tk.Frame(popup, bg=get("background_color"))
    line.pack(pady=10)
    tk.Label(
        line,
        text="Permet de noter et d'afficher en détail ce qui a été validé : [Non]",
        bg=get("background_color"),
        fg="white",
        font=("Arial", 14)
    ).pack(side="left", padx=10)
    assessment_details_var = tk.StringVar(
        value="Oui" if get("assessment_details") else "Non"
    )
    # Liste déroulante
    tk.OptionMenu(
        line,
        assessment_details_var,
        "Oui",
        "Non"
    ).pack(side="left", padx=20)


    # ===== BOUTON VALIDER =====
    def validate():
        new_color_bg = entry_bg.get()
        new_color_dp = entry_dp.get()

        try:
            root.configure(bg=new_color_bg)  # test couleur
            old_bg = get("background_color")
            set("background_color", new_color_bg)
            apply_theme_selective(root, old_bg, new_color_bg)
            old_dp = get("color_display")
            set("color_display", new_color_dp)
            apply_theme_selective(root, old_dp, new_color_dp)
            set("DISPLAY_SERVER", display_var.get() == "Oui")
            set("DISPLAY_SERVER_BOUTON", display_bouton.get() == "Oui")
            set("DISPLAY_SERVER_IP", entry_ip.get())
            set("DISPLAY_SERVER_PORT", entry_port.get())
            set("message_box_pdf", pdf_message_var.get() == "Oui")
            set("message_box_all_pdf", pdf_message_all_var.get() == "Oui")
            set("assessment_details", assessment_details_var.get() == "Oui")
            update_footer()
            popup.destroy()

        except tk.TclError:
            messagebox.showerror("Erreur", "Couleur invalide ou nombre de caractère manquant")

    btns = tk.Frame(popup, bg=get("background_color"))
    btns.pack(pady=30)

    tk.Button(
        btns,
        text="Valider",
        font=("Arial", 12, "bold"),
        bg="#7ED957",
        width=12,
        command=validate
    ).pack(side="left", padx=10)

    tk.Button(
        btns,
        text="Annuler",
        font=("Arial", 12, "bold"),
        bg="#fc6c6c",
        width=12,
        command=lambda: (popup.destroy())
    ).pack(side="left", padx=10)

def display():
    popup = tk.Toplevel(root)
    popup.title("Ecran distant")
    popup.configure(bg=get("background_color"))

    popup_width = 1120
    popup_height = 700
    x = (popup.winfo_screenwidth() // 2) - (popup_width // 2)
    y = (popup.winfo_screenheight() // 2) - (popup_height // 2)
    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    popup.transient(root)
    popup.grab_set()
    popup.protocol("WM_DELETE_WINDOW", lambda: None)

    # ================== UI ==================
    tk.Label(
        popup,
        text="Se connecter à l'écran distant",
        font=("Arial", 16, "bold"),
        fg="white",
        bg=get("background_color")
    ).pack(pady=15)


    if get("DISPLAY_SERVER"):
        tk.Label(
            popup,
            text=f"Adresse IP du serveur : {get('DISPLAY_SERVER_IP')}",
            fg="white",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)

        tk.Label(
            popup,
            text=f"Adresse du port du serveur : {get('DISPLAY_SERVER_PORT')}",
            fg="white",
            bg=get("background_color"),
            font=("Arial", 14)
        ).pack(pady=5)

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
            if getattr(e, "winerror", None) == 10049:
                messagebox.showerror(
                    "Adresse IP invalide",
                    "Impossible de démarrer le serveur.\n\n"
                    "L'adresse IP indiquée n'est pas valide sur ce PC.\n\n"
                    "Vérifiez :\n"
                    "• l'adresse IP du serveur\n"
                    "• l'adresse IP du PC"
                )
            else:
                messagebox.showerror("Erreur réseau", str(e))

            server.close()
            popup.destroy()
            return

        start_time = time.time()

        # ================== POLLING ==================
        def check_connection():
            elapsed = int(time.time() - start_time)
            remaining = SERVER_TIMEOUT - elapsed

            if remaining <= 0:
                status_label.config(
                    text="❌ Impossible de se connecter à un écran distant"
                )

                tk.Label(
                    popup,
                    text=f"⏱️ Délai d’attente dépassé ({SERVER_TIMEOUT} secondes)",
                    fg="#f40000",
                    bg=get("background_color"),
                    font=("Arial", 14)
                ).pack(pady=5)

                tk.Label(
                    popup,
                    text="🛑 Serveur arrêté",
                    fg="#f40000",
                    bg=get("background_color"),
                    font=("Arial", 14)
                ).pack(pady=5)

                server.close()

                tk.Button(
                    popup,
                    text="Fermer",
                    font=("Arial", 12, "bold"),
                    bg="#fc6c6c",
                    width=20,
                    command=lambda: popup.destroy()
                ).pack(pady=20)
                return

            try:
                conn, addr = server.accept()
                status_label.config(
                    text=f"✅ Écran connecté depuis {addr[0]}"
                )
                server.setblocking(True)
                nom_var = tk.StringVar()
                prenom_var = tk.StringVar()
                tech_var = tk.StringVar()
                comp_var = tk.StringVar()
                pen_var = tk.StringVar()
                classement_var = tk.StringVar()

                nom_var.set("MARTIN")
                prenom_var.set("Hortense")
                tech_var.set("16.5")
                comp_var.set("5")
                pen_var.set("-1.5")
                classement_var.set("7")

                for label, var in [
                    ("Nom", nom_var),
                    ("Prénom", prenom_var),
                    ("Score technique", tech_var),
                    ("Score composantes", comp_var),
                    ("Déductions", pen_var),
                    ("Classement provisoire", classement_var)
                ]:
                    line = tk.Frame(popup, bg=get("background_color"))
                    line.pack(pady=10)

                    tk.Label(
                        line,
                        text=label,
                        font=("Arial", 14),
                        fg="white",
                        bg=get("background_color")
                    ).pack(side="left", padx=10)

                    entry = tk.Entry(
                        line,
                        textvariable=var,
                        font=("Arial", 14),
                        width=15
                    )
                    entry.pack(side="left", padx=10)

                # ===== ACTIONS =====
                def send():
                    try:
                        tech = float(tech_var.get().strip())
                    except ValueError:
                        messagebox.showerror(
                            "Erreur",
                            "Le score technique doit être un nombre."
                        )
                        return
                    try:
                        comp = float(comp_var.get().strip())
                    except ValueError:
                        messagebox.showerror(
                            "Erreur",
                            "Le score composantes doit être un nombre."
                        )
                        return
                    try:
                        pen = float(pen_var.get().strip())
                    except ValueError:
                        messagebox.showerror(
                            "Erreur",
                            "La déduction doit être un nombre."
                        )
                        return
                    total = tech + comp + pen
                    data = {
                    "nom": nom_var.get().strip(),
                    "prenom": prenom_var.get().strip(),
                    "tech": tech,
                    "comp": comp,
                    "pen": pen,
                    "total": total,
                    "classement": classement_var.get().strip()
                    }
                    message = json.dumps(data).encode("utf-8") + b"\n"
                    conn.sendall(message)
                    tk.Label(
                        popup,
                        text=f"➡️ Données envoyées : {data}",
                        fg="white",
                        bg=get("background_color"),
                        font=("Arial", 14)
                    ).pack(pady=5)

                #Valider
                btns = tk.Frame(popup, bg=get("background_color"))
                btns.pack(pady=30)

                tk.Button(
                    btns,
                    text="Envoyer les données",
                    font=("Arial", 12, "bold"),
                    bg="#7ED957",
                    width=30,
                    command=send
                ).pack(side="left", padx=10)

                tk.Button(
                    btns,
                    text="Fermer",
                    font=("Arial", 12, "bold"),
                    bg="#fc6c6c",
                    width=20,
                    command=lambda: (conn.close(),server.close(), popup.destroy())
                ).pack(side="left", padx=10)


            except BlockingIOError:
                status_label.config(
                    text=f"⏳ En attente d'un écran distant ({remaining}s restantes)..."
                )
                popup.after(500, check_connection)

        popup.after(100, check_connection)
    else:
        tk.Label(
                    popup,
                    text="❌ L'écran distant n'a pas été activé dans la page de paramètres.",
                    fg="#f40000",
                    bg=get("background_color"),
                    font=("Arial", 14)
                ).pack(pady=5)

        tk.Button(
                    popup,
                    text="Fermer",
                    font=("Arial", 12, "bold"),
                    bg="#fc6c6c",
                    width=20,
                    command=lambda: popup.destroy()
                ).pack(pady=20)
def quitter():
    root.destroy()

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # pas de connexion réelle
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "IP inconnue"

def load_image(path, max_size=(220, 220)):
    img = Image.open(resource_path(path))

    # Conserve les proportions
    img.thumbnail(max_size, Image.LANCZOS)

    return ImageTk.PhotoImage(img)

def refresh_display():
    BG = get("background_color")
    for w in display_zone.winfo_children():
        w.destroy()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM competitions")
    competitions = cur.fetchall()

    if not competitions:
        tk.Label(
            display_zone,
            text="Aucune compétition créée",
            font=("Arial", 16, "italic"),
            fg="white",
            bg=get("color_display")
        ).pack()
        conn.close()
        return

    for comp_id, comp_name in competitions:
        btn = tk.Button(
            display_zone,
            text=comp_name,
            font=("Arial", 18, "bold"),
            fg="white",
            bg=get("color_display"),
            relief="flat",
            activebackground=get("color_display"),
            cursor="hand2",
            command=lambda c_id=comp_id, c_name=comp_name: ouvrir_competition(c_id, c_name)
        )
        btn.pack(anchor="w", pady=(0, 0))
        cur.execute("""
            SELECT id, discipline, niveau, categorie, genre
            FROM categories
            WHERE competition_id = ?
        """, (comp_id,))
        cats = cur.fetchall()

        if not cats:
            tk.Label(
                display_zone,
                text="  • Aucune catégorie",
                font=("Arial", 12, "italic"),
                fg="white",
                bg=get("color_display")
            ).pack(anchor="w")
        else:
            cur.execute("""
                SELECT ca.id, ca.discipline, ca.niveau, ca.categorie, ca.genre
                FROM categories ca
                WHERE ca.competition_id = ?
            """, (comp_id,))
            cats = cur.fetchall()

            for cat_id, d, n, c, g in cats:

                # nombre de patineurs
                cur.execute("""
                    SELECT COUNT(*) FROM patineurs
                    WHERE categorie_id = ?
                """, (cat_id,))
                nb_patineurs = cur.fetchone()[0]

                # nombre de résultats
                cur.execute("""
                    SELECT COUNT(DISTINCT nom || prenom || club || ordre)
                    FROM resultats
                    WHERE categorie_id = ?
                """, (cat_id,))
                nb_resultats = cur.fetchone()[0]


                # COULEUR
                if nb_patineurs == 0:
                    color = "red"
                elif nb_resultats == nb_patineurs:
                    color = "#7ED957"  # catégorie entièrement évaluée
                else:
                    color = "white"

                texte_cat = f"  • {d} | {n} | {c} | {g} ({nb_patineurs})"

                tk.Button(
                    display_zone,
                    text=texte_cat,
                    font=("Arial", 13, "bold"),
                    fg=color,
                    bg=get("color_display"),
                    relief="flat",
                    activebackground=get("color_display"),
                    activeforeground=color,
                    bd=0,
                    cursor="hand2",
                    command=lambda c_id=cat_id, txt=texte_cat: ouvrir_categorie(c_id, txt)
                ).pack(anchor="w")
    conn.close()

def update_footer():
    footer_text.set(
        f"{get('VERSION')} – "
        f"Écran : {get_ip_address()} -> "
        f"Serveur : {get('DISPLAY_SERVER_IP')}:{get('DISPLAY_SERVER_PORT')}"
    )

# ================== UI ==================
def build_menu():
    global display_zone

    main = tk.Frame(root, bg=get("background_color"))
    main.pack(expand=True, fill="both", padx=40, pady=40)

    # ===== ZONE GAUCHE (BOUTONS) =====
    left = tk.Frame(main, bg=get("background_color"))
    left.pack(side="left", fill="y")

    def menu_button(text, command):
        return tk.Button(
            left,
            text=text,
            font=("Arial", 16, "bold"),
            bg="#4e5a73",
            fg="white",
            width=32,
            height=2,
            command=command
        )

    menu_button("Créer une compétition", creer_competition).pack(pady=10)
    menu_button("Créer une catégorie", creer_categorie).pack(pady=10)
    menu_button("Sélectionner ou modifier\nles patineurs d’une catégorie", gerer_patineurs).pack(pady=10)
    menu_button("Évaluer une catégorie", evaluer_categorie).pack(pady=10)

    # Espacement
    tk.Frame(left, bg=get("background_color"), height=20).pack()
    menu_button("Ecran distant", display).pack(pady=10)
    menu_button("Paramètres", parametres).pack(pady=10)

    # ===== LOGO =====
    logo_img = load_image("logo.png", max_size=(220, 220))

    logo_label = tk.Label(
        left,
        image=logo_img,
        bg=get("background_color")
    )
    logo_label.image = logo_img  # IMPORTANT
    logo_label.pack(pady=(20, 20))

    # ===== Quitter =====
    tk.Button(
        left,
        text="Quitter",
        font=("Arial", 16, "bold"),
        bg="#fcfdff",
        fg="black",
        width=32,
        height=2,
        command=quitter
    ).pack(pady=10)

    # ===== ZONE DROITE (PANNEAU VIDE / FUTUR CONTENU) =====
    right = tk.Frame(main, bg=get("color_display"))
    right.pack(side="right", expand=True, fill="both", padx=(40, 0))

    canvas = tk.Canvas(right, bg=get("color_display"), highlightthickness=0)
    scrollbar = tk.Scrollbar(right, orient="vertical", command=canvas.yview)

    scrollable_frame = tk.Frame(canvas, bg=get("color_display"))

    # Lier la taille du frame au canvas
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    display_zone = scrollable_frame

    refresh_display()

    # ===== FOOTER =====
    footer = tk.Frame(root, bg=get("background_color"))
    footer.pack(fill="x", pady=10)
    update_footer()

    tk.Label(
        footer,
        textvariable=footer_text,
        font=("Arial", 12),
        fg="white",
        bg=get("background_color")
    ).pack(side="left", padx=20)


footer_text = tk.StringVar()
build_menu()
root.mainloop()
