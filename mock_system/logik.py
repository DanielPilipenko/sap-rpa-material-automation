"""
logik.py

Erster lauffaehiger Test der Entscheidungslogik (Phase 2).
Liest die CDE-Liste aus der Statusdatei, ermittelt je CDE die
Report-Zeilen (Gruppe + Farbe) und entscheidet den Fall A1/A2/B1/B2.

Noch ohne UiPath - reine Logik gegen die "Datenbank" (system_state.json).
"""

import state_manager

# Zuordnung PPAP-Werk -> Standardwerk (die "kleine Datenbank" aus dem Draft)
WERKSPAARE = {
    "1090": "1010",
    "2090": "2010",
}


def hole_rezeptgruppe(state, artikel):
    """Lookup wie in mock_rezgrp: zu einem Artikel die Rezeptgruppe."""
    return state["artikel_rezeptgruppe"].get(artikel)


def baue_report_zeilen(state, gruppe, farbe):
    """Baut die Report-Zeilen wie mock_report: je Material (Stamm-Farbe)
    alle Werke einsammeln, plus die Werke, in denen es gesperrt ist.
    Gibt eine Liste von Paketen zurueck:
      {"material": ..., "werke": "1010;1090", "gesperrt": "1010"}
    """
    zuordnung = state["artikel_rezeptgruppe"]
    treffer = {}
    for m in state["materialien"]:
        if zuordnung.get(m["stamm"]) != gruppe:
            continue
        if m["farbe"] != farbe:
            continue
        eintrag = treffer.setdefault(m["material"], {"werke": [], "gesperrt": []})
        eintrag["werke"].append(m["werk"])
        if m["gesperrt"]:
            eintrag["gesperrt"].append(m["werk"])

    zeilen = []
    for material, daten in treffer.items():
        zeilen.append({
            "material": material,
            "werke": ";".join(sorted(daten["werke"])),
            "gesperrt": ";".join(sorted(daten["gesperrt"])),
        })
    return zeilen


def entscheide_fall(report_zeilen, eigener_kreis):
    """Kern der Logik: aus den Report-Zeilen den Fall ableiten."""
    # Schritt 1: DT-Zeilen wegwerfen, nur FG interessiert
    fg_zeilen = []
    for zeile in report_zeilen:
        if not zeile["material"].startswith("DT"):
            fg_zeilen.append(zeile)

    # Schritt 2: keine FG-Treffer -> A1
    if len(fg_zeilen) == 0:
        return "A1"

    # Schritt 3: nur Treffer im eigenen Werkskreis behalten
    im_kreis = []
    for zeile in fg_zeilen:
        werke = zeile["werke"].split(";")
        kreis_treffer = False
        for w in werke:
            if w[:2] == eigener_kreis:
                kreis_treffer = True
        if kreis_treffer:
            im_kreis.append(zeile)

    # Schritt 4: kein Treffer im eigenen Kreis -> A2
    if len(im_kreis) == 0:
        return "A2"

    # Schritt 5: ist mindestens ein Geschwister komplett offen?
    for zeile in im_kreis:
        werke = zeile["werke"].split(";")
        gesperrt = zeile["gesperrt"].split(";")

        kreis_werke = []
        for w in werke:
            if w[:2] == eigener_kreis:
                kreis_werke.append(w)

        offen = []
        for w in kreis_werke:
            if w not in gesperrt:
                offen.append(w)

        if len(offen) == len(kreis_werke):
            return "B1"

    # Schritt 6: sonst laeuft der PPAP noch -> B2
    return "B2"


def baue_arbeitsauftrag(cde, fall, gruppe):
    """Uebersetzt den entschiedenen Fall in konkrete Handlungsschritte -
    die Anweisung, die spaeter UiPath (die 'Haende') stur ausfuehrt.

    Vorlage = Artikelnummer + '-TEMPLATE' (immer derselbe Artikel, nie
    ein fremder). In der Praxis traegt sie einen Farbslot, z.B.
    artikel-COLOR05 (Standard) oder artikel-COL01 (Automotive);
    fuer die Demo vereinfacht auf '-TEMPLATE'.

    Bei B1 entfallen die Sperr-Schritte (Kunde hat bereits freigegeben),
    bei A1/A2/B2 laeuft die volle Kette.
    """
    artikel = cde["artikel"]
    farbe = cde["farbe"]
    material = f"{artikel}-{farbe}"
    vorlage = f"{artikel}-TEMPLATE"

    ppap_werk = cde["produktionswerk"]
    standardwerk = WERKSPAARE[ppap_werk]   # z.B. 1090 -> 1010

    schritte = []
    # Anlegen passiert in ALLEN Faellen, in beiden Werken
    schritte.append(f"Anlegen: {material} in Werk {standardwerk} (Vorlage {vorlage}, Enter!)")
    schritte.append(f"Anlegen: {material} in Werk {ppap_werk} (Vorlage {vorlage}, Enter!)")

    # Sperren nur bei A1/A2/B2 - bei B1 ist der Kunde bereits durch
    if fall != "B1":
        schritte.append(f"Sperren: Gruppe {gruppe}, Farbe {farbe}, Werke {standardwerk}+{ppap_werk}")
        schritte.append(f"Entsperren: Gruppe {gruppe}, Farbe {farbe}, Werk {ppap_werk} (PPAP oeffnen)")

    schritte.append(f"Post-Check + CDE {cde['nummer']} dokumentieren")
    return schritte


def main():
    state = state_manager.load_state()

    # anstehende CDEs (Status 100)
    anstehende = []
    for cde in state["cde_liste"]:
        if cde["status"] == "100":
            anstehende.append(cde)

    for cde in anstehende:
        artikel = cde["artikel"]
        farbe = cde["farbe"]
        produktionswerk = cde["produktionswerk"]
        eigener_kreis = produktionswerk[:2]

        gruppe = hole_rezeptgruppe(state, artikel)
        report_zeilen = baue_report_zeilen(state, gruppe, farbe)
        fall = entscheide_fall(report_zeilen, eigener_kreis)
        auftrag = baue_arbeitsauftrag(cde, fall, gruppe)

        print(f"\n{cde['nummer']}: Artikel {artikel}, Farbe {farbe}, "
              f"Gruppe {gruppe}, Kreis {eigener_kreis} -> Fall {fall}")
        for nr, schritt in enumerate(auftrag, start=1):
            print(f"   {nr}. {schritt}")


if __name__ == "__main__":
    main()