"""
state_manager.py

Zentrale Zustandsdatei fuer das Mock-System.

Alle Masken (Massenanlage, RezGrp-Lookup, Sperren) lesen und schreiben
ueber dieses Modul, damit sie denselben Datenstand sehen - vergleichbar
mit der Datenbank hinter einem echten SAP-System. Die Python-Schicht
(Phase 2) nutzt dieselbe Datei fuer den Existenz-Check vor der Anlage;
das entspricht dem MARC-Check via SE16 im realen Prozess.

Datenmodell-Entscheidungen:
- Jede Farbanlage erzeugt ZWEI Materialsaetze: den Farbzwirn (DT) mit
  eigenem Nummernkreis und die Fertigware (FG). Real haengen beide
  ueber die Stueckliste zusammen, nicht ueber die Nummer.
- Jede FG-Vorlage hat eine fest zugeordnete DT-Vorlage. (Vereinfachung:
  real koennen es auch zwei DTs sein.)
- Die Produkthierarchie ist eine verkuerzte Kunstnummer. Nur die
  Endziffer traegt die reale Bedeutung: 4 = Farbe, 3 = Schwarz,
  2 = Weiss, 1 = Roh. Sie ist das optische Pruefzeichen, an dem man
  den Vorlagentyp erkennt - und spaeter der Pruefanker fuer den Bot.

Alle Werte sind synthetisch und dienen nur der Demonstration.
"""

import json
import os
from datetime import datetime

STATE_FILE = os.path.join(os.path.dirname(__file__), "system_state.json")

DEFAULT_STATE = {
    # Bekannte Vorlagen (real: je Artikel vorab manuell per MM01 angelegt).
    # 9010 ist absichtlich eine Schwarz-Vorlage (PH endet auf 3):
    # sie ist die Default-Vorlage der Werk-Varianten und damit Teil
    # der Enter-Falle - wer Enter vergisst, kopiert von Schwarz.
    "vorlagen": {
        "1234-TEMPLATE": {
            "dt_vorlage": "DT4711-TEMPLATE",
            "prod_hierarchie": "830214",
            "typ": "Farbe",
        },
        "2345-TEMPLATE": {
            "dt_vorlage": "DT5290-TEMPLATE",
            "prod_hierarchie": "771834",
            "typ": "Farbe",
        },
        "5678-TEMPLATE": {
            "dt_vorlage": "DT4838-TEMPLATE",
            "prod_hierarchie": "615334",
            "typ": "Farbe",
        },
        "9010-TEMPLATE": {
            "dt_vorlage": "DT2105-TEMPLATE",
            "prod_hierarchie": "479213",
            "typ": "Schwarz",
        },
    },
    # Rezeptgruppen-Katalog (Nummer -> Bezeichnung) und die Zuordnung
    # Stamm -> Rezeptgruppe (real: im PLC gepflegt, genau eine Gruppe
    # je Stamm, Gruppennummer max. 4-stellig numerisch).
    # Auch die DT-Staemme gehoeren zur Gruppe - gefaerbt wird ja der
    # Zwirn. Im Report tauchen DT-Zeilen deshalb mit auf; der Bot
    # muss sie ignorieren (nur FG zaehlt).
    "rezeptgruppen_katalog": {
        "210": "Polyester Standard",
        "480": "Polyester Fein",
        "1055": "Schwarz Standard",
    },
    "artikel_rezeptgruppe": {
        "1234": "210",
        "2345": "210",
        "DT4711": "210",
        "DT5290": "210",
        "5678": "480",
        "DT4838": "480",
        "9010": "1055",
        "DT2105": "1055",
    },
    # Bereits angelegte Materialien - vorbereitet fuer die drei
    # Entscheidungs-Szenarien des Rezeptgruppen-Reports.
    # Automotive-Farben enden immer auf einen Buchstaben (hier: Z).
    #
    # Farbe 0100Z: Geschwister 2345 komplett FREI (Status 800,
    #              vom Kunden freigegeben)          -> Fall B1
    # Farbe 0300Z: Geschwister 2345 im Standardwerk GESPERRT
    #              (PPAP laeuft noch)               -> Fall B2
    # Farbe 0500Z: existiert NUR im fremden Werkskreis 2010
    #                                               -> Fall A (wie neu)
    # Farbe 0700Z: existiert nirgends               -> Fall A
    "materialien": [
        {
            "werk": "1010", "material": "DT5290-0100Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0100Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-05-12T10:15:00",
        },
        {
            "werk": "1090", "material": "DT5290-0100Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0100Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-05-12T10:15:00",
        },
        {
            "werk": "1010", "material": "2345-0100Z", "art": "FG",
            "stamm": "2345", "farbe": "0100Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-05-12T10:15:00",
        },
        {
            "werk": "1090", "material": "2345-0100Z", "art": "FG",
            "stamm": "2345", "farbe": "0100Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-05-12T10:15:00",
        },
        {
            "werk": "1010", "material": "DT5290-0300Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0300Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": True,
            "angelegt_am": "2026-06-20T14:40:00",
        },
        {
            "werk": "1090", "material": "DT5290-0300Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0300Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-06-20T14:40:00",
        },
        {
            "werk": "1010", "material": "2345-0300Z", "art": "FG",
            "stamm": "2345", "farbe": "0300Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": True,
            "angelegt_am": "2026-06-20T14:40:00",
        },
        {
            "werk": "1090", "material": "2345-0300Z", "art": "FG",
            "stamm": "2345", "farbe": "0300Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "1000", "gesperrt": False,
            "angelegt_am": "2026-06-20T14:40:00",
        },
        {
            "werk": "2010", "material": "DT5290-0500Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0500Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "2000", "gesperrt": False,
            "angelegt_am": "2026-04-03T08:05:00",
        },
        {
            "werk": "2090", "material": "DT5290-0500Z", "art": "DT",
            "stamm": "DT5290", "farbe": "0500Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "2000", "gesperrt": False,
            "angelegt_am": "2026-04-03T08:05:00",
        },
        {
            "werk": "2010", "material": "2345-0500Z", "art": "FG",
            "stamm": "2345", "farbe": "0500Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "2000", "gesperrt": False,
            "angelegt_am": "2026-04-03T08:05:00",
        },
        {
            "werk": "2090", "material": "2345-0500Z", "art": "FG",
            "stamm": "2345", "farbe": "0500Z", "vorlage": "2345-TEMPLATE",
            "vk_org": "2000", "gesperrt": False,
            "angelegt_am": "2026-04-03T08:05:00",
        },
    ],
    # CDE-Liste (Farbentwicklungsauftraege) - der Prozess-Eingang.
    # Status 100 = anlagebereit (verfremdet), 200 = dokumentiert.
    # Die vier CDEs zeigen exakt auf die vier Entscheidungsszenarien:
    # 0100Z -> B1, 0300Z -> B2 (Version 2 = PPAP-Wiederholung!),
    # 0700Z -> A (neu), 0500Z -> A (nur fremder Werkskreis).
    "cde_liste": [
        {
            "nummer": "CDE-90211", "erfasser": "A. Weber", "status": "100",
            "version": "1", "artikel": "1234",
            "bezeichnung": "Naehgarn Basis Typ A", "farbe": "0100Z",
            "produktionswerk": "1090", "vk_org": "1000",
            "debitor": "10001", "kunde": "Kunde A",
            "anlagedatum": "", "bearbeiter_freigabe": "",
        },
        {
            "nummer": "CDE-90214", "erfasser": "M. Fischer", "status": "100",
            "version": "2", "artikel": "1234",
            "bezeichnung": "Naehgarn Basis Typ A", "farbe": "0300Z",
            "produktionswerk": "1090", "vk_org": "1000",
            "debitor": "10002", "kunde": "Kunde B",
            "anlagedatum": "", "bearbeiter_freigabe": "",
        },
        {
            "nummer": "CDE-90218", "erfasser": "R. Santos", "status": "100",
            "version": "1", "artikel": "1234",
            "bezeichnung": "Naehgarn Basis Typ A", "farbe": "0700Z",
            "produktionswerk": "1090", "vk_org": "1000",
            "debitor": "10003", "kunde": "Kunde C",
            "anlagedatum": "", "bearbeiter_freigabe": "",
        },
        {
            "nummer": "CDE-90223", "erfasser": "T. Wibowo", "status": "100",
            "version": "1", "artikel": "1234",
            "bezeichnung": "Naehgarn Basis Typ A", "farbe": "0500Z",
            "produktionswerk": "1090", "vk_org": "1000",
            "debitor": "10004", "kunde": "Kunde D",
            "anlagedatum": "", "bearbeiter_freigabe": "",
        },
    ],
}


def load_state():
    """Zustand laden. Existiert die Datei noch nicht, wird sie mit den
    Beispieldaten angelegt (erster Start des Mock-Systems).
    Fehlende Bereiche (z.B. nach einem Update des Mock-Systems) werden
    aus den Beispieldaten ergaenzt, damit eine aeltere
    system_state.json weiter funktioniert."""
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    for bereich, inhalt in DEFAULT_STATE.items():
        if bereich not in state:
            state[bereich] = inhalt
    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def material_existiert(state, werk, material):
    """Existenz-Check je Werk - das Mock-Aequivalent zum Blick
    in die Tabelle MARC per SE16."""
    for m in state["materialien"]:
        if m["werk"] == werk and m["material"] == material:
            return True
    return False


def material_existiert_mandant(state, material):
    """Existenz-Check auf Mandantenebene (MARA): Gibt es den Stamm
    in IRGENDEINEM Werk? Grunddaten und Vertriebssichten sind
    werksuebergreifend - beim Rollout in ein weiteres Werk sind sie
    bereits vorhanden."""
    for m in state["materialien"]:
        if m["material"] == material:
            return True
    return False


def material_anlegen(state, werk, material, art, stamm, farbe, vorlage, vk_org):
    """Neuen Materialsatz (DT oder FG) im Werk eintragen.
    Die verwendete Vorlage wird mitgespeichert - so bleibt spaeter
    nachvollziehbar, ob mit der richtigen Vorlage kopiert wurde."""
    state["materialien"].append(
        {
            "werk": werk,
            "material": material,
            "art": art,
            "stamm": stamm,
            "farbe": farbe,
            "vorlage": vorlage,
            "vk_org": vk_org,
            "gesperrt": False,
            "angelegt_am": datetime.now().isoformat(timespec="seconds"),
        }
    )


def cde_dokumentieren(state, nummer, anlagedatum, kuerzel):
    """CDE abschliessen: Anlagedatum und Bearbeiter-Kuerzel eintragen,
    Status springt von 100 (anlagebereit) auf 200 (dokumentiert).
    Die Uebersichts-Variante filtert auf Status 100 - der CDE
    verschwindet damit automatisch aus der Liste."""
    for cde in state["cde_liste"]:
        if cde["nummer"] == nummer:
            cde["anlagedatum"] = anlagedatum
            cde["bearbeiter_freigabe"] = kuerzel
            cde["status"] = "200"
            return True
    return False
