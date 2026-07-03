"""
mock_report.py

Mock-Maske "Rezeptgruppen-Report" (Auswahlbild + Trefferliste).
Bildet die Report-Transaktion nach, mit der VOR der Anlage geprueft
wird, wo eine Farbe innerhalb der Rezeptgruppe bereits angelegt ist -
die Datengrundlage fuer die Faelle A / B1 / B2.

Realer Ablauf, den der Bot hier faehrt:
1. Rezeptgruppe eintragen (Pflichtfeld) - kommt aus dem
   RezGrp-Lookup (Maske 2)
2. Farbe eintragen (exakte Suche: nur das Von-Feld fuellen)
3. BEIDE Haekchen setzen: "mit Anzeige der Werke (MARC)" und
   "Werk-Sperrstatus anzeigen" - ohne sie bleiben die
   entscheidenden Spalten leer!
4. F8 = Ausfuehren
5. Trefferliste lesen: DT-Zeilen ignorieren, nur FG zaehlt.
   Werke-Spalte per ";" trennen, nach eigenem Werkskreis filtern
   (gleiche erste zwei Ziffern), Sperrstatus im Standardwerk pruefen.

Bewusst nachgebaute bzw. dokumentierte Eigenheiten:
- Die Werke stehen ";"-separiert in EINER Spalte - das Zerlegen und
  Gruppieren nach Werkskreis ist Aufgabe des Bots, wie im Original.
- Die Spalte "Gesperrt in" liefert der echte Report NICHT (real wird
  der Sperrstatus in der MARC nachgeschlagen). Fuer dieses Projekt
  ist sie als dokumentierte Vereinfachung eingebaut: Teilmenge der
  Werke-Spalte, ebenfalls ";"-separiert, leer = nirgends gesperrt.
- Beide Haekchen sind standardmaessig AUS. Wer sie vergisst, bekommt
  eine Trefferliste ohne Werke und ohne Sperrstatus - ein
  realistischer Stolperstein fuer Mensch und Bot.
- Die Selektion dauert spuerbar und unterschiedlich lange
  (Wartepunkt: elementbasiert auf die Trefferliste warten).

Alle Werte sind synthetisch und dienen nur der Demonstration.
"""

import random
import tkinter as tk
from tkinter import ttk

import state_manager

SUCHZEIT_MIN_MS = 800    # Selektion dauert zufaellig zwischen
SUCHZEIT_MAX_MS = 2500   # 0,8 und 2,5 Sekunden


class MockReport:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock-System - Rezeptgruppen-Report (Demo)")
        self.root.resizable(False, False)

        self._build_auswahlbild()
        self._build_aktionen()
        self._build_treffer()
        self._build_statusleiste()

        # F8 = Ausfuehren, unabhaengig davon, welches Feld den Fokus hat
        self.root.bind("<F8>", self._ausfuehren)

    # ------------------------------------------------------------------ #
    # Aufbau der Maske
    # ------------------------------------------------------------------ #
    def _build_auswahlbild(self):
        frame = ttk.LabelFrame(self.root, text="Auswahlbild", padding=10)
        frame.pack(fill="x", padx=12, pady=(12, 0))

        ttk.Label(frame, text="Rezeptgruppe:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Label(frame, text="*", foreground="#b00020").grid(row=0, column=1, sticky="w")
        self.gruppe_von_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.gruppe_von_var, width=8).grid(
            row=0, column=2, sticky="w", padx=(6, 4), pady=3
        )
        ttk.Label(frame, text="bis").grid(row=0, column=3, sticky="w")
        self.gruppe_bis_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.gruppe_bis_var, width=8).grid(
            row=0, column=4, sticky="w", padx=(4, 0), pady=3
        )

        ttk.Label(frame, text="Artikelnummer:").grid(row=1, column=0, sticky="w", pady=3)
        self.artikel_von_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.artikel_von_var, width=14).grid(
            row=1, column=2, sticky="w", padx=(6, 4), pady=3
        )
        ttk.Label(frame, text="bis").grid(row=1, column=3, sticky="w")
        self.artikel_bis_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.artikel_bis_var, width=14).grid(
            row=1, column=4, sticky="w", padx=(4, 0), pady=3
        )

        ttk.Label(frame, text="Farbe:").grid(row=2, column=0, sticky="w", pady=3)
        self.farbe_von_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.farbe_von_var, width=14).grid(
            row=2, column=2, sticky="w", padx=(6, 4), pady=3
        )
        ttk.Label(frame, text="bis").grid(row=2, column=3, sticky="w")
        self.farbe_bis_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.farbe_bis_var, width=14).grid(
            row=2, column=4, sticky="w", padx=(4, 0), pady=3
        )

        self.werke_anzeigen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="mit Anzeige der Werke (MARC)",
            variable=self.werke_anzeigen_var,
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(8, 0))

        self.sperren_anzeigen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Werk-Sperrstatus anzeigen",
            variable=self.sperren_anzeigen_var,
        ).grid(row=4, column=0, columnspan=5, sticky="w", pady=(2, 0))

    def _build_aktionen(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Button(frame, text="Ausfuehren (F8)", command=self._ausfuehren).pack(side="left")

    def _build_treffer(self):
        frame = ttk.LabelFrame(self.root, text="Trefferliste", padding=(10, 6, 10, 8))
        frame.pack(fill="both", padx=12, pady=(10, 8))

        spalten = ("gruppe", "material", "werke", "gesperrt")
        self.grid = ttk.Treeview(frame, columns=spalten, show="headings", height=8)
        self.grid.heading("gruppe", text="RezGrp")
        self.grid.heading("material", text="Materialnummer")
        self.grid.heading("werke", text="Werke")
        self.grid.heading("gesperrt", text="Gesperrt in")
        self.grid.column("gruppe", width=60, anchor="w")
        self.grid.column("material", width=130, anchor="w")
        self.grid.column("werke", width=150, anchor="w")
        self.grid.column("gesperrt", width=110, anchor="w")

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
        """Gleiche Selektionslogik wie im RezGrp-Lookup: beide Felder
        leer = keine Einschraenkung, nur Von gefuellt = Exakt-Suche,
        beide gefuellt = Bereich. Numerische Werte als Zahlen."""
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
        gruppe_von = self.gruppe_von_var.get().strip()
        gruppe_bis = self.gruppe_bis_var.get().strip()
        if not gruppe_von and not gruppe_bis:
            self._status("Rezeptgruppe ist ein Pflichtfeld.", fehler=True)
            return

        # Trefferliste erst leeren: sauberer Uebergang leer -> gefuellt,
        # auf den der Bot elementbasiert warten kann.
        self.grid.delete(*self.grid.get_children())
        self._status("Selektion laeuft...")
        kriterien = (
            gruppe_von,
            gruppe_bis,
            self.artikel_von_var.get().strip().upper(),
            self.artikel_bis_var.get().strip().upper(),
            self.farbe_von_var.get().strip().upper(),
            self.farbe_bis_var.get().strip().upper(),
            self.werke_anzeigen_var.get(),
            self.sperren_anzeigen_var.get(),
        )
        dauer = random.randint(SUCHZEIT_MIN_MS, SUCHZEIT_MAX_MS)
        self.root.after(dauer, lambda: self._treffer_anzeigen(*kriterien))

    def _treffer_anzeigen(
        self, gruppe_von, gruppe_bis, artikel_von, artikel_bis,
        farbe_von, farbe_bis, werke_anzeigen, sperren_anzeigen,
    ):
        state = state_manager.load_state()
        zuordnung = state["artikel_rezeptgruppe"]

        # Je Material (Stamm-Farbe) alle Werke einsammeln, in denen es
        # angelegt ist - im Original steht das ";"-separiert in einer
        # Spalte, und genau so geben wir es aus.
        treffer = {}
        for m in state["materialien"]:
            gruppe = zuordnung.get(m["stamm"])
            if gruppe is None:
                continue
            if not self._im_bereich(gruppe, gruppe_von, gruppe_bis):
                continue
            if not self._im_bereich(m["stamm"], artikel_von, artikel_bis):
                continue
            if not self._im_bereich(m["farbe"], farbe_von, farbe_bis):
                continue
            eintrag = treffer.setdefault(
                m["material"], {"gruppe": gruppe, "werke": [], "gesperrt": []}
            )
            eintrag["werke"].append(m["werk"])
            if m["gesperrt"]:
                eintrag["gesperrt"].append(m["werk"])

        for material in sorted(treffer):
            daten = treffer[material]
            werke = ";".join(sorted(daten["werke"])) if werke_anzeigen else ""
            gesperrt = ";".join(sorted(daten["gesperrt"])) if sperren_anzeigen else ""
            self.grid.insert(
                "", "end",
                values=(daten["gruppe"], material, werke, gesperrt),
            )

        if treffer:
            self._status(f"Anzahl Treffer: {len(treffer)}")
        else:
            self._status("Keine Treffer.", fehler=True)


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MockReport(root)
    root.mainloop()


if __name__ == "__main__":
    main()
