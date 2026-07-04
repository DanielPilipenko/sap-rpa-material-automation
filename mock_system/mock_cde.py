"""
mock_cde.py

Mock-Maske "CDE Farbentwicklung" (Uebersicht + Detail).
Bildet die CDE-Transaktion nach: den Prozess-Eingang (welche Farben
sind anlagebereit?) und den Prozess-Abschluss (Dokumentation nach
erfolgreicher Anlage).

Realer Ablauf, den der Bot faehrt:
1. Uebersicht lesen: Die Variante zeigt nur anlagebereite CDEs
   (Status 100, verfremdet). Je Zeile: Artikel + Farbe + Werk -
   der Input fuer Lookup, Report und Anlage.
2. Nach erledigter Anlage/Sperrung: Zeile markieren, "Step 1"
   klicken (NUR so kommt man in den CDE - direkte Step-Klicks
   funktionieren nicht), im Detail den Bearbeitungsmodus (Stift)
   aktivieren, DANN erst ist "Step 5 - Dokumentation" erreichbar.
3. Dort Anlagedatum + Bearbeiter-Kuerzel eintragen, Speichern
   (Strg+S wie im Original). Der Status springt auf 200, das
   Fenster schliesst sich, die Zeile verschwindet aus der Liste.

Bewusst nachgebaute Eigenheiten des Originals:
- Der Umweg Zeile markieren -> Step 1 -> Stift -> Step 5 ist
  historisch gewachsen ("nie Ressourcen gehabt, es zu aendern") -
  mehr Klickarbeit fuer Mensch und Bot, originalgetreu erhalten.
- Steps 2-4 existieren, sind hier aber nur Platzhalter.
- Statuswerte sind verfremdet (100 = anlagebereit, 200 =
  dokumentiert); die echten Werte weichen ab.

Alle Werte sind erfunden und dienen nur der Demonstration.
"""

import tkinter as tk
from tkinter import ttk

import state_manager

STATUS_TEXTE = {
    "100": "Rezeptur beendet - anlagebereit",
    "200": "Dokumentiert",
}


class MockCDE:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock-System - CDE Farbentwicklung (Demo)")
        self.root.resizable(False, False)

        self._build_kopf()
        self._build_liste()
        self._build_statusleiste()
        self._liste_laden()

    # ------------------------------------------------------------------ #
    # Uebersicht
    # ------------------------------------------------------------------ #
    def _build_kopf(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Label(frame, text="Variante:").pack(side="left")
        self.variante_var = tk.StringVar(value="Anlagebereite CDEs (Status 100)")
        ttk.Entry(
            frame, textvariable=self.variante_var, width=32,
            state="readonly", takefocus=0,
        ).pack(side="left", padx=(6, 20))

        # Step-Knoepfe wie im Original - Einstieg NUR ueber Step 1
        # bei markierter Zeile. Die uebrigen melden sich zu Wort.
        ttk.Button(frame, text="Step 1", command=self._step1).pack(side="left", padx=2)
        for nr in (2, 3, 4, 5):
            ttk.Button(
                frame, text=f"Step {nr}",
                command=lambda n=nr: self._status(
                    f"Step {n}: Einstieg nur ueber Step 1 moeglich.", fehler=True
                ),
            ).pack(side="left", padx=2)

    def _build_liste(self):
        frame = ttk.LabelFrame(self.root, text="Farbauftraege", padding=(10, 6, 10, 8))
        frame.pack(fill="both", padx=12, pady=(10, 8))

        spalten = (
            "nummer", "erfasser", "status", "version", "artikel",
            "bezeichnung", "farbe", "werk", "vkorg",
        )
        # selectmode="browse": genau EINE Zeile markierbar - der Prozess
        # bearbeitet ohnehin einen CDE nach dem anderen, und die
        # Tastaturnavigation (Pfeiltasten) selektiert damit zuverlaessig.
        self.grid = ttk.Treeview(
            frame, columns=spalten, show="headings", height=8,
            selectmode="browse",
        )
        titel = {
            "nummer": ("Nummer", 90), "erfasser": ("Erfasser", 90),
            "status": ("Status", 55), "version": ("Version", 55),
            "artikel": ("Artikel", 60), "bezeichnung": ("Bezeichnung", 150),
            "farbe": ("Farbe", 60), "werk": ("Produktionswerk", 100),
            "vkorg": ("VKOrg", 55),
        }
        for spalte, (text, breite) in titel.items():
            self.grid.heading(spalte, text=text)
            self.grid.column(spalte, width=breite, anchor="w")

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

    def _status(self, text, fehler=False):
        self.status_var.set(text)
        self.status_label.config(fg="#b00020" if fehler else "#000000")

    def _liste_laden(self):
        """Uebersicht neu aufbauen - die Variante filtert auf Status 100,
        dokumentierte CDEs verschwinden dadurch automatisch.
        Der Tastatur-Cursor wird auf die erste Zeile gesetzt (Anker
        fuer Pfeiltasten-Navigation); markiert wird eine Zeile erst
        durch Klick oder Tastendruck - wie im Original."""
        self.grid.delete(*self.grid.get_children())
        state = state_manager.load_state()
        for cde in state["cde_liste"]:
            if cde["status"] != "100":
                continue
            self.grid.insert(
                "", "end", iid=cde["nummer"],
                values=(
                    cde["nummer"], cde["erfasser"], cde["status"],
                    cde["version"], cde["artikel"], cde["bezeichnung"],
                    cde["farbe"], cde["produktionswerk"], cde["vk_org"],
                ),
            )
        kinder = self.grid.get_children()
        if kinder:
            self.grid.focus(kinder[0])

    def _step1(self):
        auswahl = self.grid.selection()
        if not auswahl:
            self._status("Bitte zuerst eine CDE-Zeile markieren.", fehler=True)
            return
        nummer = auswahl[0]
        state = state_manager.load_state()
        cde = next(
            (c for c in state["cde_liste"] if c["nummer"] == nummer), None
        )
        if cde is None:
            self._status(f"{nummer} nicht gefunden.", fehler=True)
            return
        self._status(f"{nummer} geoeffnet.")
        CDEDetail(self, cde)


class CDEDetail:
    """Detail-Fenster eines einzelnen CDE (Steps 1-5)."""

    def __init__(self, uebersicht, cde):
        self.uebersicht = uebersicht
        self.cde = cde
        self.bearbeitungsmodus = False

        self.fenster = tk.Toplevel(uebersicht.root)
        self.fenster.title(f"Farbauftrag {cde['nummer']} (Demo)")
        self.fenster.resizable(False, False)
        self.fenster.geometry("+120+80")  # feste Position fuer den Bot
        self.fenster.grab_set()

        self._build_kopfdaten()
        self._build_werkzeugleiste()
        self._build_steps()
        self._build_statusleiste()

        # Strg+S = Sichern, wie im Original
        self.fenster.bind("<Control-s>", lambda _e: self._speichern())

    # ------------------------------------------------------------------ #
    def _build_kopfdaten(self):
        frame = ttk.LabelFrame(
            self.fenster, text="Allgemeine Farbauftragdaten", padding=10
        )
        frame.pack(fill="x", padx=12, pady=(12, 0))

        felder = [
            ("Farbentwicklungsauftrag:", self.cde["nummer"],
             "Debitor:", f"{self.cde['debitor']} / {self.cde['kunde']}"),
            ("Versionsnummer:", self.cde["version"],
             "Status Farbentwicklung:",
             f"{self.cde['status']} - {STATUS_TEXTE.get(self.cde['status'], '')}"),
            ("Artikelnummer:", self.cde["artikel"],
             "Farbe:", self.cde["farbe"]),
        ]
        for zeile, (l1, w1, l2, w2) in enumerate(felder):
            ttk.Label(frame, text=l1).grid(row=zeile, column=0, sticky="w", pady=2)
            ttk.Label(frame, text=w1).grid(row=zeile, column=1, sticky="w", padx=(6, 24))
            ttk.Label(frame, text=l2).grid(row=zeile, column=2, sticky="w")
            ttk.Label(frame, text=w2).grid(row=zeile, column=3, sticky="w", padx=(6, 0))

    def _build_werkzeugleiste(self):
        frame = ttk.Frame(self.fenster, padding=(12, 8, 12, 0))
        frame.pack(fill="x")
        ttk.Button(
            frame, text="Bearbeiten (Stift)", command=self._bearbeiten
        ).pack(side="left")
        self.speichern_knopf = ttk.Button(
            frame, text="Speichern (Strg+S)", command=self._speichern,
            state="disabled",
        )
        self.speichern_knopf.pack(side="left", padx=(8, 0))

    def _build_steps(self):
        self.steps = ttk.Notebook(self.fenster)
        self.steps.pack(fill="both", padx=12, pady=(10, 0))

        namen = [
            "Step 1 - Anlage Farbauftrag",
            "Step 2 - Rezeptur",
            "Step 3 - Produktionsdaten",
            "Step 4 - Kundenbemusterung",
            "Step 5 - Dokumentation",
        ]
        self.tabs = []
        for name in namen:
            tab = ttk.Frame(self.steps, padding=12)
            self.steps.add(tab, text=name)
            self.tabs.append(tab)

        ttk.Label(
            self.tabs[0],
            text="Anlagedaten des Farbauftrags - im Mock nicht abgebildet.\n"
                 "Dieser Tab ist der Pflicht-Einstiegspunkt.",
            foreground="#777777",
        ).pack(anchor="w")
        for i in (1, 2, 3):
            ttk.Label(
                self.tabs[i], text="Im Mock nicht abgebildet.",
                foreground="#777777",
            ).pack(anchor="w")

        self._build_step5(self.tabs[4])

        # Step 5 ist erst nach dem Bearbeitungsstift erreichbar -
        # wie im Original. Vorher wird der Wechsel zurueckgeworfen.
        self.steps.bind("<<NotebookTabChanged>>", self._tabwechsel)

    def _build_step5(self, tab):
        frame = ttk.LabelFrame(tab, text="Materialstammdaten", padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="Anlagedatum:").grid(row=0, column=0, sticky="w", pady=3)
        self.anlagedatum_var = tk.StringVar()
        self.anlagedatum_feld = ttk.Entry(
            frame, textvariable=self.anlagedatum_var, width=14, state="disabled"
        )
        self.anlagedatum_feld.grid(row=0, column=1, sticky="w", padx=(6, 24), pady=3)

        ttk.Label(frame, text="SCM-Freigabe:").grid(row=0, column=2, sticky="w")
        ttk.Entry(frame, width=10, state="disabled", takefocus=0).grid(
            row=0, column=3, sticky="w", padx=(6, 0)
        )

        ttk.Label(frame, text="Bearbeiter Freigabe:").grid(row=1, column=0, sticky="w", pady=3)
        self.kuerzel_var = tk.StringVar()
        self.kuerzel_feld = ttk.Entry(
            frame, textvariable=self.kuerzel_var, width=8, state="disabled"
        )
        self.kuerzel_feld.grid(row=1, column=1, sticky="w", padx=(6, 24), pady=3)

        ttk.Label(frame, text="SCM-Bearbeiter:").grid(row=1, column=2, sticky="w")
        ttk.Entry(frame, width=8, state="disabled", takefocus=0).grid(
            row=1, column=3, sticky="w", padx=(6, 0), pady=3
        )

        self.dispo_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Dispomerkmal angepasst", variable=self.dispo_var,
            state="disabled", takefocus=0,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(frame, text="Storno geprueft SCM-MD:").grid(
            row=2, column=2, sticky="w", pady=(6, 0)
        )
        ttk.Entry(frame, width=10, state="disabled", takefocus=0).grid(
            row=2, column=3, sticky="w", padx=(6, 0), pady=(6, 0)
        )

    def _build_statusleiste(self):
        self.status_var = tk.StringVar(
            value="Nur lesend geoeffnet - Bearbeiten (Stift) fuer Aenderungen."
        )
        self.status_label = tk.Label(
            self.fenster, textvariable=self.status_var,
            relief="sunken", anchor="w", padx=6,
        )
        self.status_label.pack(fill="x", side="bottom", pady=(10, 0))

    def _status(self, text, fehler=False):
        self.status_var.set(text)
        self.status_label.config(fg="#b00020" if fehler else "#000000")

    # ------------------------------------------------------------------ #
    def _tabwechsel(self, _event=None):
        if self.steps.index("current") == 4 and not self.bearbeitungsmodus:
            self.steps.select(0)
            self._status(
                "Step 5 erst nach Bearbeiten (Stift) moeglich.", fehler=True
            )

    def _bearbeiten(self):
        self.bearbeitungsmodus = True
        self.anlagedatum_feld.config(state="normal")
        self.kuerzel_feld.config(state="normal")
        self.speichern_knopf.config(state="normal")
        self._status("Bearbeitungsmodus aktiv - Step 5 freigeschaltet.")

    def _speichern(self):
        if not self.bearbeitungsmodus:
            self._status("Erst Bearbeiten (Stift) aktivieren.", fehler=True)
            return
        anlagedatum = self.anlagedatum_var.get().strip()
        kuerzel = self.kuerzel_var.get().strip().upper()
        if not anlagedatum:
            self._status("Anlagedatum ist ein Pflichtfeld.", fehler=True)
            return
        if not kuerzel:
            self._status("Bearbeiter Freigabe (Kuerzel) ist ein Pflichtfeld.", fehler=True)
            return

        state = state_manager.load_state()
        state_manager.cde_dokumentieren(state, self.cde["nummer"], anlagedatum, kuerzel)
        state_manager.save_state(state)

        # Fenster schliesst sich, die Variante filtert Status 100 -
        # der dokumentierte CDE verschwindet aus der Uebersicht.
        self.fenster.destroy()
        self.uebersicht._liste_laden()
        self.uebersicht._status(
            f"{self.cde['nummer']} dokumentiert - Status 200."
        )


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MockCDE(root)
    root.mainloop()


if __name__ == "__main__":
    main()
