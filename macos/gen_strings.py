#!/usr/bin/env python3
"""Génère Sources/FomodCore/Strings.swift à partir de ../i18n/strings.json et ../i18n/ids.json (lancé par build_app.sh).

strings.json : {texte_fr: [en, it, es]}, la table commune à l'appli et à la preview web.
ids.json : {identifiant: texte_fr}, pour les textes cherchés par identifiant (interface « mac_* », clés « mackit.* »
que renvoie l'outil mackit).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "i18n" / "strings.json"
IDS = HERE.parent / "i18n" / "ids.json"
OUT = HERE / "Sources" / "FomodCore" / "Strings.swift"


def lit(s: str) -> str:
    return json.dumps(s, ensure_ascii=False).replace("\\/", "/")


table = json.loads(SRC.read_text(encoding="utf-8"))
ids = json.loads(IDS.read_text(encoding="utf-8"))
missing = [k for k, fr in ids.items() if fr not in table]
assert not missing, f"ids sans traduction : {missing}"
lines = [f"    {lit(k)}: [{', '.join(lit(t) for t in v)}]," for k, v in table.items()]
id_lines = [f"    {lit(k)}: {lit(v)}," for k, v in ids.items()]
OUT.write_text(
    "// FICHIER GÉNÉRÉ par macos/gen_strings.py à partir de i18n/strings.json et i18n/ids.json : ne pas modifier à la main.\n\n"
    "let translations: [String: [String]] = [\n" + "\n".join(lines) + "\n]\n\n"
    "/// Identifiant d'un texte (« card3_title », « mackit.fix.engine.title »…) -> texte français, clé de `translations`.\n"
    "let textIds: [String: String] = [\n" + "\n".join(id_lines) + "\n]\n",
    encoding="utf-8",
)
print(f"{len(table)} traductions, {len(ids)} identifiants → {OUT.relative_to(HERE)}")
