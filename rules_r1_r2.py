"""
Règles officielles R1 / R2 – Freeskating régional
Toutes les règles validées sont centralisées ici.
Aucune logique UI dans ce fichier.
"""

class RulesError(Exception):
    pass


class RulesR1R2:
    def __init__(self, niveau: str):
        if niveau not in ("R1", "R2"):
            raise ValueError("Niveau invalide (R1 ou R2 attendu)")
        self.niveau = niveau

    # ----------------------------
    # VALIDATION GLOBALE
    # ----------------------------
    def validate(self, state, history_lines, totals):
        """Valide l'ensemble du programme avant Confirmer."""
        self._check_jumps(state, history_lines, totals)
        self._check_spins(state, history_lines, totals)
        self._check_footwork(state)

        #self._check_composantes(state)

    # ----------------------------
    # SAUTS / COMBOS
    # ----------------------------
    def _check_jumps(self, state, history_lines, totals):
        jumps = state.scoring_engine.jumps
        combos = state.combo_engine.jump_combos
        def invalidate_jump(jump):
            jump["level"] = "*"

            index = jump.get("history_index")

            if index is not None and 0 <= index < len(history_lines):
                line = history_lines[index]

                totals["technique"] -= float(line.split()[-2])
                parts = line.split(" - ")

                if not line.startswith("    "):
                    history_lines[index] = (
                        f"{parts[0]} - {parts[1]} - Level * - 0 points"
                    )
                else:
                    history_lines[index] = (
                        f"    {parts[0]} - Level * - 0 points"
                    )

        if self.niveau == "R2":
            if len(jumps) > 5:
                # on invalide les sauts en trop
                for j in jumps[5:]:
                    invalidate_jump(j)
                #raise RulesError("R2 : maximum 5 sauts autorisés.")

            if len(combos) > 1:
                raise RulesError("R2 : une seule combinaison de sauts autorisée.")

            types = [j['code'] for j in jumps]

            if "F" in types and "Lo" in types:
                for j in jumps:
                    if j["code"] in ("F", "Lo"):
                        invalidate_jump(j)
                #raise RulesError("R2 : F et Lo ne peuvent pas être tous les deux présents.")

            if "Th" in types:
                for j in jumps:
                    if j["code"] == "Th":
                        invalidate_jump(j)
                #raise RulesError("R2 : Th n'est pas autorisé.")

            if "Lz" in types or "Lz!" in types:
                for j in jumps:
                    if j["code"].startswith("Lz"):
                        invalidate_jump(j)
                #raise RulesError("R2 : Lz n'est pas autorisé.")

        if self.niveau == "R1":
            if len(jumps) > 8:
                for j in jumps[8:]:
                    invalidate_jump(j)
                #raise RulesError("R1 : maximum 8 sauts autorisés.")

            if len(combos) > 2:
                raise RulesError("R1 : maximum 2 combinaisons de sauts.")

        # -------- répétitions --------
        def normalize_jump(code: str) -> str:
            if code.startswith("Lz"):
                return "Lz"
            return code

        counts = {}
        for j in jumps:
            normalized = normalize_jump(j["code"])
            counts[normalized] = counts.get(normalized, 0) + 1

        repeated_more = [code for code, c in counts.items() if c > 2]

        if repeated_more:
            faulty_code = repeated_more[0]
            occurrences = 0
            for j in jumps:
                if normalize_jump(j["code"]) == faulty_code:
                    occurrences += 1
                    if occurrences > 2:
                        if j.get("level") == "*":
                            continue
                        invalidate_jump(j)
            #raise RulesError(f"Le saut {faulty_code} est présenté plus de 2 fois.")

        seen_counts = {}
        double_used = False  # indique si un saut a déjà été doublé

        for j in jumps:
            code = normalize_jump(j["code"])

            if j.get("level") == "*":
                continue

            count = seen_counts.get(code, 0) + 1
            seen_counts[code] = count

            # 3ème occurrence → toujours invalide
            if count > 2:
                invalidate_jump(j)
                continue

            # 2ème occurrence
            if count == 2:
                if not double_used:
                    # premier saut doublé → autorisé
                    double_used = True
                else:
                    # un autre saut est déjà doublé → celui-ci est interdit
                    invalidate_jump(j)
            #raise RulesError("Un seul saut peut être présenté deux fois.\n" f"Sauts répétés : {', '.join(repeated_twice)}")


    # ----------------------------
    # PIROUETTES
    # ----------------------------
    def _check_spins(self, state, history_lines, totals):
        spins = state.scoring_engine.spins
        combospin = state.combo_engine.has_spin_combo

        def invalidate_spin(spin):
            spin["level"] = "*"

            index = spin.get("history_index")
            if index is not None and 0 <= index < len(history_lines):
                line = history_lines[index]
                points = float(line.split()[-2])  # récupère les points avant modification
                totals["technique"] -= points
                parts = line.split(" - ")

                if not line.startswith("    "):
                    history_lines[index] = (
                        f"{parts[0]} - {parts[1]} - Level * - 0 points"
                    )
                else:
                    history_lines[index] = (
                        f"    {parts[0]} - Level * - 0 points"
                    )

        if len(spins) > 3:
            for s in spins[3:]:
                invalidate_spin(s)
            #raise RulesError("Maximum 3 pirouettes autorisées.")

        names = [s['code'] for s in spins]

        if len(names) != len(set(names)):
            seen = set()
            for s in spins:
                if s["code"] in seen:
                    invalidate_spin(s)
                else:
                    seen.add(s["code"])
            #raise RulesError("Chaque pirouette ne peut être présentée qu’une seule fois.")

        if self.niveau == "R1" and len(spins) == 3:
            if not combospin:
                invalidate_spin(spins[-1])
                #raise RulesError("R1 : une combinaison de pirouettes est obligatoire.")

        if self.niveau == "R2":
            for s in spins:
                if s["code"] in ("Sbi", "Sbo", "Sfo"):
                    invalidate_spin(s)
                    #raise RulesError("R2 : La pirouette assise n'est pas autorisée.")
                if s["code"] in ("Cbi", "Cbo", "Cfo"):
                    invalidate_spin(s)
                    #raise RulesError("R2 : La pirouette arabesque n'est pas autorisée.")

            if combospin:
                invalidate_spin(spins[-1])
                #raise RulesError("R2 : Les combinaisons de pirouettes ne sont pas autorisées.")


    # ----------------------------
    # FOOTWORK
    # ----------------------------
    def _check_footwork(self, state):
        if state.footwork_engine.current is None:
            raise RulesError("La Footwork Séquence est obligatoire.")

    # ----------------------------
    # COMPOSANTES
    # ----------------------------
    def _check_composantes(self, state):
        if len(state.composantes_engine.values) != 6:
           raise RulesError("Toutes les composantes doivent être évaluées.")
