"""
mock_rezgrp.py

Mock-Maske "Rezeptgruppen-Zuordnung" (Lookup).
Bildet die Lookup-Transaktion nach, mit der zu einem Artikel die
Rezeptgruppe ermittelt wird - der Wert, den die Sperr-Transaktion
(Maske 3) als Eingabe braucht.

Realer Ablauf, den der Bot hier faehrt:
1. Rezeptgruppe von 1 bis 9999 eintragen (= alle Gruppen beruecksichtigen)
2. Artikelnummer eintragen (der Teil vor dem Bindestrich, z.B. 1234)
3. F8 = Ausfuehren
4. Ergebnis: GENAU EINE Zeile mit Gruppennummer und Bezeichnung
   (jeder Artikel gehoert zu genau einer Gruppe, gepflegt im PLC).
   Der Bot liest die Nummer aus und speichert sie als Variable.

Bewusst nachgebaute Eigenheiten:
- F8 fuehrt aus, wie im Original - zusaetzlich gibt es einen Button.
- Die Selektion dauert spuerbar und unterschiedlich lange (Wartepunkt:
  der Bot wartet elementbasiert auf die Ergebniszeile, nicht stumpf).
- Leeres Ergebnis ist moeglich (Artikel ohne Zuordnung) und erscheint
  als rote Statusmeldung - fuer den Bot eine Business Exception:
  Stammdaten unvollstaendig, Key-User informieren. Das PLC sollte den
  Fall eigentlich ausschliessen; der Bot behandelt ihn trotzdem.
- Bleibt das Bis-Feld leer, gilt das Von-Feld als Exakt-Suche
  (SAP-Selektionslogik).

Alle Werte sind synthetisch und dienen nur der Demonstration.
"""

import random
import tkinter as tk
from tkinter import ttk

import state_manager

SUCHZEIT_MIN_MS = 800    # Selektion dauert zufaellig zwischen
SUCHZEIT_MAX_MS = 2500   # 0,8 und 2,5 Sekunden


class MockRezGrp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock-System - Rezeptgruppen-Zuordnung (Demo)")
        self.root.resizable(False, False)

        self._build_selektion()
        self._build_aktionen()
        self._build_ergebnis()
        self._build_statusleiste()

        # F8 = Ausfuehren, unabhaengig davon, welches Feld den Fokus hat
        self.root.bind("<F8>", self._ausfuehren)

    # ------------------------------------------------------------------ #
    # Aufbau der Maske
    # ------------------------------------------------------------------ #
    def _build_selektion(self):
        frame = ttk.LabelFrame(self.root, text="Selektionskriterien", padding=10)
        frame.pack(fill="x", padx=12, pady=(12, 0))

        ttk.Label(frame, text="Rezeptgruppe:").grid(row=0, column=0, sticky="w", pady=3)
        self.gruppe_von_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.gruppe_von_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(6, 4), pady=3
        )
        ttk.Label(frame, text="bis").grid(row=0, column=2, sticky="w")
        self.gruppe_bis_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.gruppe_bis_var, width=8).grid(
            row=0, column=3, sticky="w", padx=(4, 0), pady=3
        )

        ttk.Label(frame, text="Artikelnummer:").grid(row=1, column=0, sticky="w", pady=3)
        self.artikel_von_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.artikel_von_var, width=14).grid(
            row=1, column=1, sticky="w", padx=(6, 4), pady=3
        )
        ttk.Label(frame, text="bis").grid(row=1, column=2, sticky="w")
        self.artikel_bis_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.artikel_bis_var, width=14).grid(
            row=1, column=3, sticky="w", padx=(4, 0), pady=3
        )

    def _build_aktionen(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Button(frame, text="Ausfuehren (F8)", command=self._ausfuehren).pack(side="left")

    def _build_ergebnis(self):
        frame = ttk.LabelFrame(self.root, text="Ergebnis", padding=(10, 6, 10, 8))
        frame.pack(fill="both", padx=12, pady=(10, 8))

        spalten = ("gruppe", "bezeichnung")
        self.grid = ttk.Treeview(frame, columns=spalten, show="headings", height=6)
        self.grid.heading("gruppe", text="Rezeptgruppe")
        self.grid.heading("bezeichnung", text="Bezeichnung")
        self.grid.column("gruppe", width=110, anchor="w")
        self.grid.column("bezeichnung", width=240, anchor="w")

        rollen = ttk.Scrollbar(frame, orient="vertical", command=self.grid.yview)
        self.grid.configure(yscrollcommand=rollen.set)
        self.grid.pack(side="left", fill="both", expand=True)
        rollen.pack(side="right", fill="y")

    def _build_statusleiste(self):
        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var,
            relief="sunken", anchor="w", padx=6,
        )
        self.status_label.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------ #
    # Hilfsfunktionen
    # ------------------------------------------------------------------ #
    def _status(self, text, fehler=False):
        self.status_var.set(text)
        self.status_label.config(fg="#b00020" if fehler else "#000000")

    @staticmethod
    def _im_bereich(wert, von, bis):
        """SAP-Selektionslogik: beide Felder leer = keine Einschraenkung,
        nur Von gefuellt = Exakt-Suche, beide gefuellt = Bereich.
        Numerische Werte werden als Zahlen verglichen."""
        if not von and not bis:
            return True
        if von and not bis:
            return wert == von
        try:
            return int(von) <= int(wert) <= int(bis)
        except ValueError:
            return von <= wert <= bis

    # ------------------------------------------------------------------ #
    # Ausfuehren (F8)
    # ------------------------------------------------------------------ #
    def _ausfuehren(self, _event=None):
        # Ergebnis erst leeren: der Bot bekommt einen sauberen
        # Uebergang leer -> gefuellt, auf den er warten kann.
        self.grid.delete(*self.grid.get_children())
        self._status("Selektion laeuft...")
        dauer = random.randint(SUCHZEIT_MIN_MS, SUCHZEIT_MAX_MS)
        kriterien = (
            self.gruppe_von_var.get().strip(),
            self.gruppe_bis_var.get().strip(),
            self.artikel_von_var.get().strip().upper(),
            self.artikel_bis_var.get().strip().upper(),
        )
        self.root.after(dauer, lambda: self._ergebnis_anzeigen(*kriterien))

    def _ergebnis_anzeigen(self, gruppe_von, gruppe_bis, artikel_von, artikel_bis):
        state = state_manager.load_state()
        katalog = state["rezeptgruppen_katalog"]

        treffer = []
        for artikel, gruppe in state["artikel_rezeptgruppe"].items():
            if not self._im_bereich(artikel, artikel_von, artikel_bis):
                continue
            if not self._im_bereich(gruppe, gruppe_von, gruppe_bis):
                continue
            eintrag = (gruppe, katalog.get(gruppe, ""))
            if eintrag not in treffer:
                treffer.append(eintrag)

        for gruppe, bezeichnung in treffer:
            self.grid.insert("", "end", values=(gruppe, bezeichnung))

        if treffer:
            self._status(f"{len(treffer)} Rezeptgruppe(n) gefunden.")
        else:
            self._status(
                "Keine Zuordnung gefunden - Artikel ohne Rezeptgruppe?",
                fehler=True,
            )


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MockRezGrp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
