"""
mock_massenanlage.py

Mock-Maske "Stammdaten in Masse anlegen".
Bildet die Struktur der realen Massenanlage-Transaktion vereinfacht nach
und dient als Automatisierungsziel fuer UiPath (Phase 1 des Projekts).

Bewusst nachgebaute Eigenheiten des Originals:

- Die Werk-Variante bringt beim Laden bereits ein Vorlagematerial mit:
  Das Feld oben ist vorbefuellt, die Vorlagedaten unten sind sofort
  geladen. Wer sein eigenes Template eintippt und Enter vergisst,
  laesst unten die Daten der Varianten-Vorlage stehen - und legt
  damit von der falschen (hier sogar: einer Schwarz-)Vorlage an.
  Das ist der haeufigste manuelle Fehler im echten Prozess. Die Maske
  verhindert ihn absichtlich NICHT; die Absicherung ist Aufgabe der
  Automatisierung.
- Vorlagedaten laden nach Enter mit spuerbar schwankender Verzoegerung
  (Wartepunkt fuer den Bot). Der Uebergang ist alter Wert -> neuer
  Wert, nicht leer -> gefuellt.
- Die Produkthierarchie der Vorlage ist sichtbar - ihre Endziffer
  (4=Farbe, 3=Schwarz, 2=Weiss, 1=Roh) ist das optische Pruefzeichen
  fuer den Vorlagentyp.
- Nach dem Anlegen erscheint ein Protokoll-Grid im SAP-Stil:
  je Farbe erst der Farbzwirn (DT), dann die Fertigware (FG),
  darunter eine Zeile pro angelegter Sicht mit Status
  (Haken = angelegt, X = nicht angelegt, i = Info/bereits vorhanden).
  Bekannter Normalfall: Beim DT wird die Vertriebssicht nicht
  angelegt (DTs werden praktisch nie verkauft) - ein X, das fachlich
  in Ordnung ist.
- Die Transaktion bricht bei bereits vorhandenen Materialien NICHT ab:
  Vorhandenes wird als "i" gemeldet, Fehlendes ergaenzt - wie im
  Original. Dabei zaehlen zwei Datenebenen: Grunddaten und Vertrieb
  sind mandantenweit (MARA) - beim Rollout in ein weiteres Werk
  erscheinen sie als "i", waehrend die werksabhaengigen Sichten
  (Disposition, Stuecklisten, Fertigungsversionen usw.) dort neu
  angelegt werden.
- Fehlermeldungen zum Vorlage-Laden erscheinen wie im Original unten
  in der Statusleiste, nicht als Dialog.
"""

import random
import time
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import state_manager

# Jede Variante bringt Werk, Vk.org UND ein vorbelegtes Vorlagematerial
# mit - exakt wie die gespeicherten Varianten der realen Transaktion.
WERK_VARIANTEN = {
    "1010 - Standardwerk": {
        "werk": "1010", "vk_org": "1000", "default_vorlage": "9010-TEMPLATE",
    },
    "1090 - PPAP-Werk": {
        "werk": "1090", "vk_org": "1000", "default_vorlage": "9010-TEMPLATE",
    },
}

# Sichten, die je Material angelegt werden (reduzierter Satz des
# Originals), mit ihrer Datenebene:
# "mandant" = werksuebergreifend (MARA/Vertriebsdaten) - einmal
#             angelegt, in jedem Werk vorhanden
# "werk"    = je Werk neu (MARC, Stuecklisten, Fertigungsversionen)
SICHTEN = [
    ("Grunddaten", "mandant"),
    ("Vertrieb", "mandant"),
    ("Disposition", "werk"),
    ("Arbeitsvorbereitung", "werk"),
    ("Buchhaltung", "werk"),
    ("Kalkulation", "werk"),
    ("Stueckliste(n)", "werk"),
    ("Fertigungsversion(en)", "werk"),
]

LADEZEIT_MIN_MS = 1500   # Vorlage-Laden dauert zufaellig zwischen
LADEZEIT_MAX_MS = 4000   # 1,5 und 4 Sekunden (wie ein echtes System)
HANG_DAUER_S = 45        # simulierter Systemhaenger im Testmodus


class MockMassenanlage:
    def __init__(self, root):
        self.root = root
        self.root.title("Mock-System - Stammdaten in Masse anlegen (Demo)")
        self.root.resizable(False, False)

        # Getrennter Zustand fuer die Enter-Falle:
        # Das Eingabefeld kann etwas anderes enthalten als das,
        # was tatsaechlich geladen wurde.
        self.geladene_vorlage = None
        self.weitere_farben = []

        self._build_variante()
        self._build_vorlage()
        self._build_vorlagedaten()
        self._build_materialien()
        self._build_hinweiszeile()
        self._build_aktionen()
        self._build_protokoll()
        self._build_statusleiste()

        self._variante_uebernehmen()

    # ------------------------------------------------------------------ #
    # Aufbau der Maske
    # ------------------------------------------------------------------ #
    def _build_variante(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Label(frame, text="Variante:").pack(side="left")
        self.variante_var = tk.StringVar(value=list(WERK_VARIANTEN)[0])
        combo = ttk.Combobox(
            frame, textvariable=self.variante_var,
            values=list(WERK_VARIANTEN), state="readonly", width=24,
        )
        combo.pack(side="left", padx=(6, 0))
        combo.bind("<<ComboboxSelected>>", self._variante_uebernehmen)

    def _build_vorlage(self):
        frame = ttk.LabelFrame(self.root, text="Vorlage", padding=10)
        frame.pack(fill="x", padx=12, pady=(10, 0))

        ttk.Label(frame, text="Vorlagematerial:").grid(row=0, column=0, sticky="w", pady=3)
        self.vorlagematerial_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.vorlagematerial_var, width=26)
        entry.grid(row=0, column=1, sticky="w", padx=(6, 8), pady=3)
        entry.bind("<Return>", self._vorlage_laden)
        ttk.Label(frame, text="(Enter = Vorlage laden)").grid(row=0, column=2, sticky="w")

        ttk.Label(frame, text="Vorlagewerk:").grid(row=1, column=0, sticky="w", pady=3)
        self.vorlagewerk_var = tk.StringVar()
        ttk.Entry(
            frame, textvariable=self.vorlagewerk_var, width=10,
            state="readonly", takefocus=0,
        ).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=3)

        ttk.Label(frame, text="Vorlage fuer Vk.org:").grid(row=2, column=0, sticky="w", pady=3)
        self.vkorg_var = tk.StringVar()
        ttk.Entry(
            frame, textvariable=self.vkorg_var, width=10,
            state="readonly", takefocus=0,
        ).grid(row=2, column=1, sticky="w", padx=(6, 0), pady=3)

    def _build_vorlagedaten(self):
        frame = ttk.LabelFrame(
            self.root, text="Vorlagedaten (werden nach Enter geladen)", padding=10
        )
        frame.pack(fill="x", padx=12, pady=(10, 0))

        self.fg_template_var = tk.StringVar()
        self.dt_template_var = tk.StringVar()
        self.prodhier_var = tk.StringVar()

        ttk.Label(frame, text="Fertigware-Template:").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Label(frame, textvariable=self.fg_template_var, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(frame, text="Prod.hierarchie:").grid(row=0, column=2, sticky="w", padx=(14, 0))
        ttk.Label(frame, textvariable=self.prodhier_var, width=12).grid(row=0, column=3, sticky="w")

        ttk.Label(frame, text="Farbzwirn-Template (DT):").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(frame, textvariable=self.dt_template_var, width=20).grid(row=1, column=1, sticky="w")

    def _build_materialien(self):
        frame = ttk.LabelFrame(self.root, text="Materialien", padding=10)
        frame.pack(fill="x", padx=12, pady=(10, 0))

        ttk.Label(frame, text="Artikel:").grid(row=0, column=0, sticky="w", pady=3)
        self.artikel_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.artikel_var, width=16).grid(
            row=0, column=1, sticky="w", padx=(6, 0), pady=3
        )

        ttk.Label(frame, text="Farbe(n):").grid(row=1, column=0, sticky="w", pady=3)
        self.farbe_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.farbe_var, width=16).grid(
            row=1, column=1, sticky="w", padx=(6, 8), pady=3
        )
        ttk.Button(
            frame, text="Mehrfachselektion...", command=self._mehrfachselektion
        ).grid(row=1, column=2, sticky="w")
        self.weitere_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.weitere_var).grid(
            row=1, column=3, sticky="w", padx=(8, 0)
        )

    def _build_hinweiszeile(self):
        frame = ttk.Frame(self.root, padding=(12, 8, 12, 0))
        frame.pack(fill="x")
        ttk.Label(
            frame,
            text="Organisationsebenen / Sichtenauswahl: durch Variante vorbelegt "
                 "- im Mock nicht abgebildet",
            foreground="#777777",
        ).pack(side="left")

    def _build_aktionen(self):
        frame = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        frame.pack(fill="x")
        ttk.Button(frame, text="Anlegen", command=self._anlegen).pack(side="left")
        self.testmodus_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame,
            text="Testmodus: Systemfehler simulieren",
            variable=self.testmodus_var,
        ).pack(side="right")

    def _build_protokoll(self):
        frame = ttk.LabelFrame(self.root, text="Protokoll", padding=(10, 6, 10, 8))
        frame.pack(fill="both", padx=12, pady=(10, 8))

        spalten = ("material", "status", "hinweis")
        self.grid = ttk.Treeview(frame, columns=spalten, show="headings", height=10)
        self.grid.heading("material", text="Material")
        self.grid.heading("status", text="Status")
        self.grid.heading("hinweis", text="Hinweis")
        self.grid.column("material", width=130, anchor="w")
        self.grid.column("status", width=55, anchor="center")
        self.grid.column("hinweis", width=360, anchor="w")

        rollen = ttk.Scrollbar(frame, orient="vertical", command=self.grid.yview)
        self.grid.configure(yscrollcommand=rollen.set)
        self.grid.pack(side="left", fill="both", expand=True)
        rollen.pack(side="right", fill="y")

        # Zeilenfarben nach Status - gruen/rot/blau wie die SAP-Symbole
        self.grid.tag_configure("ok", foreground="#1a7f37")
        self.grid.tag_configure("fehler", foreground="#b00020")
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
        """Meldung in der Statusleiste anzeigen - wie im Original ist das
        der Kanal fuer Fehler beim Vorlage-Laden (kein Dialog)."""
        self.status_var.set(text)
        self.status_label.config(fg="#b00020" if fehler else "#000000")

    def _variante_uebernehmen(self, _event=None):
        """Variante laden: Werk, Vk.org UND das vorbelegte Vorlagematerial
        uebernehmen. Die Vorlagedaten sind danach sofort geladen -
        wie im Original steht die Maske nie 'leer' da. Genau daraus
        entsteht die Enter-Falle."""
        daten = WERK_VARIANTEN[self.variante_var.get()]
        self.vorlagewerk_var.set(daten["werk"])
        self.vkorg_var.set(daten["vk_org"])
        self.vorlagematerial_var.set(daten["default_vorlage"])
        self._vorlage_anzeigen(daten["default_vorlage"])

    def _aktuelle_farben(self):
        """Farbe aus dem Feld plus Farben aus der Mehrfachselektion,
        Reihenfolge erhalten, Doppelte entfernen."""
        farben = []
        erste = self.farbe_var.get().strip().upper()
        if erste:
            farben.append(erste)
        for f in self.weitere_farben:
            if f not in farben:
                farben.append(f)
        return farben

    # ------------------------------------------------------------------ #
    # Vorlage laden (Enter)
    # ------------------------------------------------------------------ #
    def _vorlage_laden(self, _event=None):
        name = self.vorlagematerial_var.get().strip().upper()
        if not name:
            self._status("Vorlagematerial eingeben, dann Enter.", fehler=True)
            return
        # Felder erst leeren: der Bot bekommt so einen sauberen
        # Uebergang alter Wert -> leer -> neuer Wert, auf den er
        # elementbasiert warten kann.
        self.fg_template_var.set("")
        self.dt_template_var.set("")
        self.prodhier_var.set("")
        self._status("Vorlage wird gelesen...")
        dauer = random.randint(LADEZEIT_MIN_MS, LADEZEIT_MAX_MS)
        self.root.after(dauer, lambda: self._vorlage_anzeigen(name))

    def _vorlage_anzeigen(self, name):
        state = state_manager.load_state()
        vorlage = state["vorlagen"].get(name)
        if vorlage is None:
            self.geladene_vorlage = None
            self._status(f"Vorlage {name} im System nicht vorhanden.", fehler=True)
            return
        self.geladene_vorlage = name
        self.fg_template_var.set(name)
        self.dt_template_var.set(vorlage["dt_vorlage"])
        self.prodhier_var.set(vorlage["prod_hierarchie"])
        self._status(f"Vorlage {name} geladen.")

    # ------------------------------------------------------------------ #
    # Mehrfachselektion (Popup)
    # ------------------------------------------------------------------ #
    def _mehrfachselektion(self):
        popup = tk.Toplevel(self.root)
        popup.title("Mehrfachselektion Farben")
        popup.resizable(False, False)
        popup.geometry("+180+160")  # feste Position, vorhersagbar fuer den Bot
        popup.grab_set()  # modal, wie das Original-Popup in SAP

        ttk.Label(popup, text="Eine Farbe pro Zeile:", padding=(10, 8, 10, 4)).pack(anchor="w")
        text = tk.Text(popup, width=24, height=8)
        text.pack(padx=10)
        vorhandene = self._aktuelle_farben()
        if vorhandene:
            text.insert("1.0", "\n".join(vorhandene))
        # Cursor direkt ins Eingabefeld setzen - wie im Original springt
        # der Fokus beim Oeffnen in die erste Zelle. Ohne diese Zeile
        # gehen Tastatureingaben (auch die des Bots) ins Leere.
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
        # F8 = Uebernehmen, wie in der Original-Mehrfachselektion.
        # Funktioniert unabhaengig davon, welches Element den Fokus hat.
        popup.bind("<F8>", lambda _e: uebernehmen())

    # ------------------------------------------------------------------ #
    # Anlegen
    # ------------------------------------------------------------------ #
    def _anlegen(self):
        if self.testmodus_var.get():
            self._systemfehler_simulieren()
            return

        werk = self.vorlagewerk_var.get()
        vk_org = self.vkorg_var.get()
        artikel = self.artikel_var.get().strip().upper()
        farben = self._aktuelle_farben()

        # Pflichtpruefungen, wie sie auch das Original macht.
        # WICHTIG: Es wird NICHT geprueft, ob der Feldinhalt
        # Vorlagematerial zur geladenen Vorlage passt - genau diese
        # Luecke hat das Original auch (Enter vergessen = die
        # Varianten-Vorlage bleibt geladen).
        if self.geladene_vorlage is None:
            messagebox.showerror(
                "Keine Vorlage geladen",
                "Es ist keine Vorlage geladen.\n"
                "Vorlagematerial eingeben und mit Enter laden.",
            )
            return
        if not artikel:
            messagebox.showerror("Eingabe fehlt", "Artikel ist ein Pflichtfeld.")
            return
        if not farben:
            messagebox.showerror("Eingabe fehlt", "Mindestens eine Farbe angeben.")
            return

        state = state_manager.load_state()
        vorlage_info = state["vorlagen"][self.geladene_vorlage]
        dt_stamm = vorlage_info["dt_vorlage"].split("-")[0]

        # Protokoll je Lauf neu aufbauen (wie das SAP-Grid je Ausfuehrung)
        self.grid.delete(*self.grid.get_children())

        for farbe in farben:
            # Reihenfolge wie im Original: erst der Farbzwirn (DT),
            # dann die Fertigware (FG), je Farbe ein Blockpaar.
            for stamm, art in ((dt_stamm, "DT"), (artikel, "FG")):
                material = f"{stamm}-{farbe}"
                existiert_werk = state_manager.material_existiert(state, werk, material)
                existiert_mandant = state_manager.material_existiert_mandant(state, material)
                self._protokoll_block(material, art, existiert_werk, existiert_mandant)
                if not existiert_werk:
                    state_manager.material_anlegen(
                        state, werk, material, art, stamm, farbe,
                        self.geladene_vorlage, vk_org,
                    )
                # Bereits Vorhandenes wird NICHT neu angelegt und NICHT
                # als Fehler behandelt - die Transaktion ergaenzt nur
                # Fehlendes, wie das Original.

        state_manager.save_state(state)
        uhrzeit = datetime.datetime.now().strftime("%H:%M:%S")
        self._status(
            f"Lauf abgeschlossen um {uhrzeit}: {len(farben)} Farbe(n), "
            f"Vorlage {self.geladene_vorlage}. Details siehe Protokoll."
        )

    def _protokoll_block(self, material, art, existiert_werk, existiert_mandant):
        """Protokollzeilen fuer EIN Material (DT oder FG) einfuegen:
        eine Zeile pro Sicht, Materialname nur in der ersten Zeile -
        wie im Original-Grid. Mandantenweite Sichten (MARA/Vertrieb)
        gelten als vorhanden, sobald der Stamm in irgendeinem Werk
        existiert; Werkssichten nur bei Existenz im Zielwerk."""
        erste_zeile = True
        for sicht, ebene in SICHTEN:
            name = material if erste_zeile else ""
            erste_zeile = False
            if art == "DT" and sicht == "Vertrieb":
                # Bekannter Normalfall: DT-Vorlagen haben keine
                # Vertriebssicht, DTs werden praktisch nie verkauft.
                # Die Sicht fehlt deshalb bei JEDEM Lauf - auch wenn
                # das Material sonst laengst existiert. Fachlich
                # zulaessiges X - der Bot muss das kennen.
                self.grid.insert(
                    "", "end", tags=("fehler",),
                    values=(name, "X", "Vk.org/Vertriebsweg wurde nicht angelegt"),
                )
            elif (ebene == "mandant" and existiert_mandant) or (
                ebene == "werk" and existiert_werk
            ):
                self.grid.insert(
                    "", "end", tags=("info",),
                    values=(name, "i", f"{sicht} bereits vorhanden"),
                )
            else:
                self.grid.insert(
                    "", "end", tags=("ok",),
                    values=(name, "OK", f"{sicht} erfolgreich angelegt"),
                )

    # ------------------------------------------------------------------ #
    # Testmodus: Systemhaenger
    # ------------------------------------------------------------------ #
    def _systemfehler_simulieren(self):
        """Blockiert absichtlich den Tkinter-Mainloop: das Fenster
        reagiert nicht mehr ('Keine Rueckmeldung'), wie eine haengende
        SAP-Session. Der Bot soll das per Timeout erkennen, der
        Watchdog soll alarmieren."""
        self._status(
            f"SIMULIERTER SYSTEMFEHLER: Session haengt {HANG_DAUER_S}s "
            f"(Testmodus aktiv)...", fehler=True,
        )
        self.root.update_idletasks()  # letzte Anzeige VOR dem Einfrieren
        time.sleep(HANG_DAUER_S)
        self._status("Session wieder frei (Testmodus).")


def main():
    root = tk.Tk()
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    MockMassenanlage(root)
    root.mainloop()


if __name__ == "__main__":
    main()
