"""
mock_sperr.py

Mock-Maske "Material sperren / entsperren" (Werksstatus).
Bildet die Sperr-Transaktion nach, mit der nach der Anlage der
PPAP-Zustand hergestellt wird - die erste Maske, die das
gesperrt-Flag in der Statusdatei tatsaechlich umlegt.

Realer Ablauf, den der Bot faehrt (nur in den Faellen A und B2):
  Lauf 1: Variante "Sperren - Werke 1010 + 1090"
          -> Gruppe + Farbe in BEIDEN Werken sperren
  Lauf 2: Variante "Entsperren - Werk 1090 (PPAP oeffnen)"
          -> PPAP-Werk wieder oeffnen
Endzustand: Standardwerk zu, PPAP-Werk offen - bemustern moeglich,
Serienfertigung blockiert, bis der Kunde freigibt.

Die dritte Variante "Entsperren - Werke 1010 + 1090 (Kundenfreigabe)"
ist der Status-800-Moment: der Kunde hat final freigegeben, beide
Werke gehen auf. Der Bot braucht sie (noch) nicht - sie existiert
real und erlaubt im Handbetrieb, einen Fehl-Sperrlauf zu heilen.

WICHTIG - gruppenweite Wirkung: Die Transaktion sperrt ALLE
Materialien der Rezeptgruppe in der gewaehlten Farbe und den
Werken der Variante - auch bereits freigegebene Geschwister!
Genau deshalb existiert der Entscheidungsbaum (Fall B1): Vor dem
Sperren wird geprueft, ob in der Gruppe schon etwas offen ist.
Ein gedankenloser Sperrlauf wuerde freigegebene Serienartikel
mit sperren - haengende Auftraege, teuer.
Die DT-Staemme gehoeren zur Gruppe und werden automatisch
mitgesperrt (deckt "Anderer Materialstatus fuer DTs" des
Originals ab).

Bewusste Vereinfachungen (im README dokumentiert):
- Sperrstatus ist boolesch (gesperrt ja/nein) statt der echten
  SAP-Materialstatus-Codes.
- Das Original-Feld "Anderes Werk fuer DT-Artikel" ist nicht
  nachgebaut (bei uns liegen DT und FG im selben Werk).
- Mindestens eine Farbe ist Pflicht - Schutz gegen versehentliches
  Sperren einer kompletten Gruppe ueber alle Farben.

Alle Werte sind synthetisch und dienen nur der Demonstration.
"""

import random
import tkinter as tk
from tkinter import ttk

import state_manager

VARIANTEN = {
    "Sperren - Werke 1010 + 1090": {
        "aktion": "sperren", "werke": ["1010", "1090"],
    },
    "Entsperren - Werk 1090 (PPAP oeffnen)": {
        "aktion": "entsperren", "werke": ["1090"],
    },
    "Entsperren - Werke 1010 + 1090 (Kundenfreigabe)": {
        "aktion": "entsperren", "werke": ["1010", "1090"],
    },
}

LAUFZEIT_MIN_MS = 800    # Verarbeitung dauert zufaellig zwischen
LAUFZEIT_MAX_MS = 2500   # 0,8 und 2,5 Sekunden


class MockSperr:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock-System - Material sperren/entsperren (Demo)")
        self.root.resizable(False, False)

        self.weitere_farben = []

        self._build_variante()
        self._build_selektion()
        self._build_materialstatus()
        self._build_aktionen()
        self._build_protokoll()
        self._build_statusleiste()

        self._variante_uebernehmen()

        # F8 = Ausfuehren, unabhaengig davon, welches Feld den Fokus hat
        self.root.bind("<F8>", self._ausfuehren)

    # ------------------------------------------------------------------ #
    # Aufbau der Maske
    # ------------------------------------------------------------------ #
    def _build_variante(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Label(frame, text="Variante:").pack(side="left")
        self.variante_var = tk.StringVar(value=list(VARIANTEN)[0])
        combo = ttk.Combobox(
            frame, textvariable=self.variante_var,
            values=list(VARIANTEN), state="readonly", width=42,
        )
        combo.pack(side="left", padx=(6, 0))
        combo.bind("<<ComboboxSelected>>", self._variante_uebernehmen)

    def _build_selektion(self):
        frame = ttk.LabelFrame(self.root, text="Selektionskriterien", padding=10)
        frame.pack(fill="x", padx=12, pady=(10, 0))

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

        ttk.Label(frame, text="Farbe(n):").grid(row=1, column=0, sticky="w", pady=3)
        self.farbe_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.farbe_var, width=14).grid(
            row=1, column=2, sticky="w", padx=(6, 8), pady=3
        )
        ttk.Button(
            frame, text="Mehrfachselektion...", command=self._mehrfachselektion
        ).grid(row=1, column=3, columnspan=2, sticky="w")
        self.weitere_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.weitere_var).grid(
            row=1, column=5, sticky="w", padx=(8, 0)
        )

    def _build_materialstatus(self):
        frame = ttk.LabelFrame(
            self.root, text="Materialstatus (durch Variante vorbelegt)", padding=10
        )
        frame.pack(fill="x", padx=12, pady=(10, 0))

        self.aktion_var = tk.StringVar()
        ttk.Radiobutton(
            frame, text="Sperren (Materialstatus setzen)",
            variable=self.aktion_var, value="sperren", state="disabled",
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            frame, text="Entsperren (Materialstatus aufheben)",
            variable=self.aktion_var, value="entsperren", state="disabled",
        ).grid(row=1, column=0, sticky="w")

        ttk.Label(frame, text="Werk(e):").grid(row=0, column=1, sticky="e", padx=(30, 4))
        self.werke_var = tk.StringVar()
        ttk.Entry(
            frame, textvariable=self.werke_var, width=12,
            state="readonly", takefocus=0,
        ).grid(row=0, column=2, sticky="w")

    def _build_aktionen(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Button(frame, text="Ausfuehren (F8)", command=self._ausfuehren).pack(side="left")

    def _build_protokoll(self):
        frame = ttk.LabelFrame(self.root, text="Protokoll", padding=(10, 6, 10, 8))
        frame.pack(fill="both", padx=12, pady=(10, 8))

        spalten = ("material", "werk", "aktion", "ergebnis")
        self.grid = ttk.Treeview(frame, columns=spalten, show="headings", height=8)
        self.grid.heading("material", text="Material")
        self.grid.heading("werk", text="Werk")
        self.grid.heading("aktion", text="Aktion")
        self.grid.heading("ergebnis", text="Ergebnis")
        self.grid.column("material", width=130, anchor="w")
        self.grid.column("werk", width=55, anchor="w")
        self.grid.column("aktion", width=90, anchor="w")
        self.grid.column("ergebnis", width=160, anchor="w")

        rollen = ttk.Scrollbar(frame, orient="vertical", command=self.grid.yview)
        self.grid.configure(yscrollcommand=rollen.set)
        self.grid.pack(side="left", fill="both", expand=True)
        rollen.pack(side="right", fill="y")

        self.grid.tag_configure("ok", foreground="#1a7f37")
        self.grid.tag_configure("info", foreground="#1f5fa8")

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

    def _variante_uebernehmen(self, _event=None):
        daten = VARIANTEN[self.variante_var.get()]
        self.aktion_var.set(daten["aktion"])
        self.werke_var.set(";".join(daten["werke"]))

    def _aktuelle_farben(self):
        farben = []
        erste = self.farbe_var.get().strip().upper()
        if erste:
            farben.append(erste)
        for f in self.weitere_farben:
            if f not in farben:
                farben.append(f)
        return farben

    @staticmethod
    def _im_bereich(wert, von, bis):
        """Gleiche Selektionslogik wie in den anderen Masken."""
        if not von and not bis:
            return True
        if von and not bis:
            return wert == von
        try:
            return int(von) <= int(wert) <= int(bis)
        except ValueError:
            return von <= wert <= bis

    # ------------------------------------------------------------------ #
    # Mehrfachselektion (Popup) - wie in der Massenanlage
    # ------------------------------------------------------------------ #
    def _mehrfachselektion(self):
        popup = tk.Toplevel(self.root)
        popup.title("Mehrfachselektion Farben")
        popup.resizable(False, False)
        popup.geometry("+180+160")
        popup.grab_set()

        ttk.Label(popup, text="Eine Farbe pro Zeile:", padding=(10, 8, 10, 4)).pack(anchor="w")
        text = tk.Text(popup, width=24, height=8)
        text.pack(padx=10)
        vorhandene = self._aktuelle_farben()
        if vorhandene:
            text.insert("1.0", "\n".join(vorhandene))
        text.focus_set()

        def uebernehmen():
            zeilen = [z.strip().upper() for z in text.get("1.0", "end").splitlines()]
            farben = [z for z in zeilen if z]
            if farben:
                self.farbe_var.set(farben[0])
                self.weitere_farben = farben[1:]
            else:
                self.farbe_var.set("")
                self.weitere_farben = []
            anzahl = len(self.weitere_farben)
            self.weitere_var.set(f"(+{anzahl} weitere)" if anzahl else "")
            popup.destroy()

        knopfzeile = ttk.Frame(popup, padding=(10, 8))
        knopfzeile.pack(fill="x")
        ttk.Button(knopfzeile, text="Uebernehmen (F8)", command=uebernehmen).pack(side="left")
        ttk.Button(knopfzeile, text="Abbrechen", command=popup.destroy).pack(
            side="left", padx=(8, 0)
        )
        popup.bind("<F8>", lambda _e: uebernehmen())

    # ------------------------------------------------------------------ #
    # Ausfuehren (F8)
    # ------------------------------------------------------------------ #
    def _ausfuehren(self, _event=None):
        gruppe_von = self.gruppe_von_var.get().strip()
        gruppe_bis = self.gruppe_bis_var.get().strip()
        if not gruppe_von and not gruppe_bis:
            self._status("Rezeptgruppe ist ein Pflichtfeld.", fehler=True)
            return
        farben = self._aktuelle_farben()
        if not farben:
            self._status("Mindestens eine Farbe angeben.", fehler=True)
            return

        self.grid.delete(*self.grid.get_children())
        self._status("Verarbeitung laeuft...")
        daten = VARIANTEN[self.variante_var.get()]
        dauer = random.randint(LAUFZEIT_MIN_MS, LAUFZEIT_MAX_MS)
        self.root.after(
            dauer,
            lambda: self._verarbeiten(
                gruppe_von, gruppe_bis, farben,
                daten["aktion"], daten["werke"],
            ),
        )

    def _verarbeiten(self, gruppe_von, gruppe_bis, farben, aktion, werke):
        state = state_manager.load_state()
        zuordnung = state["artikel_rezeptgruppe"]
        soll_gesperrt = aktion == "sperren"

        zeilen = []
        for m in state["materialien"]:
            gruppe = zuordnung.get(m["stamm"])
            if gruppe is None:
                continue
            if not self._im_bereich(gruppe, gruppe_von, gruppe_bis):
                continue
            if m["farbe"] not in farben:
                continue
            if m["werk"] not in werke:
                continue
            if m["gesperrt"] == soll_gesperrt:
                # Idempotenz sichtbar machen: nichts zu tun ist KEIN
                # Fehler - wichtig fuer Wiederholungslaeufe (Fall B2).
                ergebnis = "war bereits gesperrt" if soll_gesperrt else "war bereits offen"
                tag = "info"
            else:
                m["gesperrt"] = soll_gesperrt
                ergebnis = "gesperrt gesetzt" if soll_gesperrt else "entsperrt"
                tag = "ok"
            zeilen.append((m["material"], m["werk"], aktion.capitalize(), ergebnis, tag))

        state_manager.save_state(state)

        for material, werk, aktion_text, ergebnis, tag in sorted(zeilen):
            self.grid.insert(
                "", "end", tags=(tag,),
                values=(material, werk, aktion_text, ergebnis),
            )

        if zeilen:
            self._status(f"{len(zeilen)} Materialsatz/-saetze verarbeitet.")
        else:
            self._status(
                "Keine Materialien zu Gruppe/Farbe(n) in den Werken gefunden.",
                fehler=True,
            )


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MockSperr(root)
    root.mainloop()


if __name__ == "__main__":
    main()
