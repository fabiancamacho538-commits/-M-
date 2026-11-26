#!/usr/bin/env python3
"""
Detecta menciones de modelos de iPhone en un texto (guion, transcripción,
subtítulos, prompt) y devuelve la imagen correspondiente de la biblioteca
RECURSOS/IPHONES según catalogo.json.

Uso:
    python3 RECURSOS/_scripts/buscar_iphone.py "comparamos el iPhone quince Pro Max con el 16e"
    python3 RECURSOS/_scripts/buscar_iphone.py --archivo transcripcion.srt
    python3 RECURSOS/_scripts/buscar_iphone.py --modelo "iphone 17 pro"     # un solo modelo

Como módulo:
    from buscar_iphone import buscar_menciones, resolver_modelo

Nunca sustituye un modelo por otro: si el modelo mencionado no está en la
biblioteca (no existe o todavía no salió), lo devuelve con "disponible": false.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ_REPO / "RECURSOS" / "IPHONES" / "catalogo.json"

NUMEROS = {
    # español
    "once": "11", "doce": "12", "trece": "13", "catorce": "14", "quince": "15",
    "dieciseis": "16", "diez y seis": "16", "diecisiete": "17", "diez y siete": "17",
    "dieciocho": "18", "diez y ocho": "18",
    # inglés
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
    "sixteen": "16", "seventeen": "17", "eighteen": "18",
}

# "iPhone 15 Pro Max", "iphone15promax", "el 15 Pro", "iPhone 16e", "iPhone Air", "iPhone Duo"
PATRON = re.compile(
    r"""
    (?:
        \biphone\s*(?P<n1>1[1-9])                                              # iPhone 15 Pro Max
            (?:(?P<e1>e)\b|\s*(?P<v1>pro\s*max|pro|plus|mini|air)\b)?          # (16e va pegado: "15 e iPhone" no es 15e)
      | \biphone\s*(?P<solo>air|duo|fold)\b                                    # iPhone Air / Duo
      | \b(?P<n2>1[1-8])\s*(?P<v2>pro\s*max|pro|plus|mini)\b                   # "el 15 Pro Max" (sin la palabra iPhone)
      | \b(?P<n3>1[6-8])e\b                                                    # "el 16e"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = t.replace("i phone", "iphone").replace("ifone", "iphone").replace("aifon", "iphone")
    for palabra, num in sorted(NUMEROS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{palabra}\b", num, t)
    t = re.sub(r"\bpromax\b", "pro max", t)
    t = re.sub(r"\bpro\s*maximo\b", "pro max", t)
    return t


def _cargar() -> dict:
    cat = json.loads(CATALOGO.read_text())
    return cat


def _nombre_canonico(numero: str | None, variante: str | None, solo: str | None) -> str:
    if solo:
        return {"air": "iPhone Air", "duo": "iPhone Duo", "fold": "iPhone Duo"}[solo.lower()]
    v = re.sub(r"\s+", "", (variante or "").lower())  # "pro max" / "promax" -> "promax"
    sufijo = {"": "", "pro": " Pro", "promax": " Pro Max", "plus": " Plus", "mini": " mini",
              "e": "e", "air": " Air"}[v]
    if v == "air":  # "iPhone 18 Air" no existe con ese nombre; el Air 2 todavía no salió
        return f"iPhone {numero} Air"
    return f"iPhone {numero}{sufijo}"


def resolver_modelo(nombre: str, catalogo: dict | None = None) -> dict:
    """Devuelve la entrada del catálogo para un nombre canónico, o un aviso si no está."""
    cat = catalogo or _cargar()
    for e in cat["imagenes"]:
        if e["modelo"].lower() == nombre.lower():
            return {"modelo": e["modelo"], "disponible": True, "ruta": e["ruta_local"],
                    "resolucion": e["resolucion"]["texto"],
                    "resolucion_limitada": e["resolucion_limitada"],
                    "alto_maximo_en_video_px": e["alto_maximo_en_video_px"],
                    "color": e["color"], "perspectiva": e["perspectiva"]}
    motivo = "No está en la biblioteca."
    for nd in cat.get("no_disponibles", []):
        if nombre.lower() in nd["modelo"].lower():
            motivo = nd["motivo"]
            break
    return {"modelo": nombre, "disponible": False, "motivo": motivo,
            "accion": "No usar la imagen de otro modelo: resolver con tipografía/ícono genérico."}


def buscar_menciones(texto: str, catalogo: dict | None = None) -> list[dict]:
    cat = catalogo or _cargar()
    norm = _normalizar(texto)
    salida = []
    for m in PATRON.finditer(norm):
        g = m.groupdict()
        numero = g["n1"] or g["n2"] or g["n3"]
        variante = g["v1"] or g["v2"] or ("e" if (g["e1"] or g["n3"]) else None)
        nombre = _nombre_canonico(numero, variante, g["solo"])
        res = resolver_modelo(nombre, cat)
        res["mencion"] = m.group(0).strip()
        res["posicion"] = m.start()  # índice en el texto normalizado
        salida.append(res)
    return salida


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("texto", nargs="?", help="texto donde buscar menciones")
    ap.add_argument("--archivo", help="leer el texto desde un archivo (srt, txt, md...)")
    ap.add_argument("--modelo", help="resolver un único nombre de modelo")
    args = ap.parse_args()
    if args.modelo:
        hits = buscar_menciones(args.modelo) or [resolver_modelo(args.modelo)]
        print(json.dumps(hits[0], ensure_ascii=False, indent=2))
        return 0 if hits[0]["disponible"] else 1
    texto = Path(args.archivo).read_text() if args.archivo else (args.texto or sys.stdin.read())
    print(json.dumps(buscar_menciones(texto), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
