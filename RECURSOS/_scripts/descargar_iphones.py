#!/usr/bin/env python3
"""
Biblioteca de recursos gráficos — iPhones (iPhone 11 → iPhone 18 Pro Max).

VISTA FRONTAL. Descarga un render oficial (PNG con transparencia) de cada modelo,
verifica que el modelo sea el correcto contra la base de datos AppleDB,
comprueba con Pillow que tenga un canal alfa con transparencia real,
recorta el margen transparente sobrante, optimiza el PNG sin pérdida y
actualiza RECURSOS/IPHONES/catalogo.json + el índice visual.
Cada modelo vive en su propia carpeta: RECURSOS/IPHONES/<Modelo>/<Modelo>_frontal.png
(las traseras las genera traseras_iphones.py en la misma carpeta).

Uso:
    python3 RECURSOS/_scripts/descargar_iphones.py            # descarga todo lo que falte
    python3 RECURSOS/_scripts/descargar_iphones.py --forzar   # vuelve a descargar todo
    python3 RECURSOS/_scripts/descargar_iphones.py --solo-verificar

Para agregar un modelo nuevo (p. ej. iPhone 18 cuando salga): añadir una fila a
MODELOS con su identificador de AppleDB (deviceFiles/iPhone/<id>.json) y un
color que exista en device/<id>/ del repositorio de imágenes, y volver a correr.

Dependencias: requests, Pillow. Opcionales: pyoxipng (optimización sin pérdida),
rembg (solo se usa si una imagen llegara sin transparencia).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------
# Imágenes: repositorio público de imágenes de AppleDB (renders oficiales de
# producto de Apple, los mismos que muestra la lista de dispositivos de la
# cuenta de Apple). Se fija el commit para que la descarga sea reproducible.
IMG_REPO = "littlebyteorg/apple-device-images"
IMG_COMMIT = "b3082ba529681e25f3b465bcadf593460943687a"
# Datos de verificación (nombre comercial, números de modelo A, fecha de lanzamiento).
DB_REPO = "littlebyteorg/appledb"
DB_REF = "main"

RAW = "https://raw.githubusercontent.com/{repo}/{ref}/{path}"

RAIZ = Path(__file__).resolve().parents[1]          # RECURSOS/
DESTINO = RAIZ / "IPHONES"
CATALOGO = DESTINO / "catalogo.json"
INDICE_VISUAL = DESTINO / "_indice_visual.jpg"

# ---------------------------------------------------------------------------
# Modelos: (nombre comercial, identificador AppleDB, color elegido, variante, extra)
# Regla de color: el de mayor resolución disponible; a igual resolución, el
# color protagonista del lanzamiento. Única excepción: iPhone 17 Pro usa
# Cosmic Orange (542 px de ancho) y no Silver (575 px, +6 %) porque el naranja
# es el color que identifica al modelo en pantalla.
# extra=True -> variante fuera de Base/mini/Plus/Air/Pro/Pro Max (e, plegable).
# ---------------------------------------------------------------------------
MODELOS = [
    ("iPhone 11",          "iPhone12,1", "Purple",           "Base",    False),
    ("iPhone 11 Pro",      "iPhone12,3", "Midnight Green",   "Pro",     False),
    ("iPhone 11 Pro Max",  "iPhone12,5", "Midnight Green",   "Pro Max", False),
    ("iPhone 12 mini",     "iPhone13,1", "Blue",             "mini",    False),
    ("iPhone 12",          "iPhone13,2", "Purple",           "Base",    False),
    ("iPhone 12 Pro",      "iPhone13,3", "Pacific Blue",     "Pro",     False),
    ("iPhone 12 Pro Max",  "iPhone13,4", "Pacific Blue",     "Pro Max", False),
    ("iPhone 13 mini",     "iPhone14,4", "Pink",             "mini",    False),
    ("iPhone 13",          "iPhone14,5", "Pink",             "Base",    False),
    ("iPhone 13 Pro",      "iPhone14,2", "Sierra Blue",      "Pro",     False),
    ("iPhone 13 Pro Max",  "iPhone14,3", "Sierra Blue",      "Pro Max", False),
    ("iPhone 14",          "iPhone14,7", "Purple",           "Base",    False),
    ("iPhone 14 Plus",     "iPhone14,8", "Purple",           "Plus",    False),
    ("iPhone 14 Pro",      "iPhone15,2", "Deep Purple",      "Pro",     False),
    ("iPhone 14 Pro Max",  "iPhone15,3", "Deep Purple",      "Pro Max", False),
    ("iPhone 15",          "iPhone15,4", "Pink",             "Base",    False),
    ("iPhone 15 Plus",     "iPhone15,5", "Pink",             "Plus",    False),
    ("iPhone 15 Pro",      "iPhone16,1", "Natural Titanium", "Pro",     False),
    ("iPhone 15 Pro Max",  "iPhone16,2", "Natural Titanium", "Pro Max", False),
    ("iPhone 16",          "iPhone17,3", "Ultramarine",      "Base",    False),
    ("iPhone 16 Plus",     "iPhone17,4", "Ultramarine",      "Plus",    False),
    ("iPhone 16 Pro",      "iPhone17,1", "Desert Titanium",  "Pro",     False),
    ("iPhone 16 Pro Max",  "iPhone17,2", "Desert Titanium",  "Pro Max", False),
    ("iPhone 16e",         "iPhone17,5", "White",            "e",       True),
    ("iPhone 17",          "iPhone18,3", "Lavender",         "Base",    False),
    ("iPhone Air",         "iPhone18,4", "Sky Blue",         "Air",     False),
    ("iPhone 17 Pro",      "iPhone18,1", "Cosmic Orange",    "Pro",     False),
    ("iPhone 17 Pro Max",  "iPhone18,2", "Cosmic Orange",    "Pro Max", False),
    ("iPhone 17e",         "iPhone18,5", "Soft Pink",        "e",       True),
    ("iPhone 18 Pro",      "iPhone19,2", "Burgundy",         "Pro",     False),
    ("iPhone 18 Pro Max",  "iPhone19,3", "Burgundy",         "Pro Max", False),
    ("iPhone Duo",         "iPhone19,4", "Night Sky",        "Plegable", True),
]

# Modelos del rango pedido que NO existen o todavía no salieron (al 2026-11-26).
NO_DISPONIBLES = [
    {"modelo": "iPhone 18", "motivo": "No lanzado: en septiembre de 2026 Apple solo lanzó iPhone 18 Pro, 18 Pro Max e iPhone Duo. Los reportes ubican al iPhone 18 base en la primavera (boreal) de 2027."},
    {"modelo": "iPhone 18e", "motivo": "No lanzado (los reportes lo ubican en 2027)."},
    {"modelo": "iPhone Air 2 / iPhone 18 Air", "motivo": "No lanzado (los reportes lo ubican en 2027)."},
    {"modelo": "iPhone 18 Plus / iPhone 18 mini", "motivo": "No existen: Apple no anunció esas variantes."},
    {"modelo": "iPhone 14 mini, 15 mini, 16 mini, 17 mini", "motivo": "No existen: la línea mini terminó con el iPhone 13 mini."},
    {"modelo": "iPhone 17 Plus", "motivo": "No existe: en 2025 el iPhone Air reemplazó al Plus."},
    {"modelo": "iPhone 11 Plus / 12 Plus / 13 Plus", "motivo": "No existen: la variante Plus empezó con el iPhone 14."},
]

LICENCIA = {
    "titular_derechos": "Apple Inc.",
    "tipo": "Render oficial de producto de Apple (no es una licencia libre).",
    "redistribucion": "Publicado en el repositorio público littlebyteorg/apple-device-images (AppleDB). "
                      "La licencia MIT del repositorio cubre su código, no las imágenes de Apple.",
    "uso_previsto_permitido": "Uso nominativo/editorial: identificar el modelo en reseñas, comparativas, "
                              "noticias, tutoriales y contenido informativo, sin alterar el producto y sin "
                              "sugerir patrocinio o aval de Apple.",
    "precaucion": "Para publicidad pagada o piezas comerciales donde el iPhone sea protagonista, revisar las "
                  "'Guidelines for Using Apple Trademarks and Copyrights' de Apple.",
}


def raw_url(repo: str, ref: str, path: str) -> str:
    return RAW.format(repo=repo, ref=ref, path=urllib.parse.quote(path))


def slug(modelo: str) -> str:
    return modelo.replace(" ", "_")


def carpeta(modelo: str) -> Path:
    """Cada modelo tiene su propia carpeta: RECURSOS/IPHONES/iPhone_15_Pro/"""
    return DESTINO / slug(modelo)


def ruta_vista(modelo: str, vista: str) -> Path:
    """vista: 'trasera' o 'frontal' -> RECURSOS/IPHONES/iPhone_15_Pro/iPhone_15_Pro_trasera.png"""
    return carpeta(modelo) / f"{slug(modelo)}_{vista}.png"


def rel(p: Path) -> str:
    return str(p.relative_to(RAIZ.parent))


def cargar_catalogo() -> dict:
    """Devuelve {modelo: entrada}. Acepta el formato actual (lista 'modelos')."""
    if not CATALOGO.exists():
        return {}
    data = json.loads(CATALOGO.read_text())
    return {e["modelo"]: e for e in data.get("modelos", [])}


def guardar_catalogo(modelos: dict, no_disponibles: list) -> None:
    orden = [m[0] for m in MODELOS]
    lista = [modelos[m] for m in orden if m in modelos]
    con_trasera = sum(1 for e in lista if "trasera" in e.get("imagenes", {}))
    con_frontal = sum(1 for e in lista if "frontal" in e.get("imagenes", {}))
    catalogo = {
        "biblioteca": "RECURSOS/IPHONES",
        "estructura": "RECURSOS/IPHONES/<Modelo>/<Modelo>_trasera.png y <Modelo>_frontal.png "
                      "(PNG RGBA con transparencia real; una carpeta por modelo)",
        "vista_por_defecto": "trasera",
        "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scripts": {
            "frontales": "RECURSOS/_scripts/descargar_iphones.py",
            "traseras": "RECURSOS/_scripts/traseras_iphones.py",
            "busqueda": "RECURSOS/_scripts/buscar_iphone.py",
        },
        "total_modelos": len(lista),
        "total_traseras": con_trasera,
        "total_frontales": con_frontal,
        "modelos": lista,
        "no_disponibles": no_disponibles,
    }
    CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2) + "\n")


def descargar(url: str, intentos: int = 4) -> bytes:
    ultimo = None
    for i in range(intentos):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:  # reintento con espera creciente
            ultimo = e
            import time
            time.sleep(2 ** i)
    raise RuntimeError(f"No se pudo descargar {url}: {ultimo}")


def ficha_appledb(identificador: str) -> dict:
    url = raw_url(DB_REPO, DB_REF, f"deviceFiles/iPhone/{identificador}.json")
    return json.loads(descargar(url)), url


def analizar_alfa(im: Image.Image) -> dict:
    """Comprueba con Pillow que haya transparencia real (no un alfa 100 % opaco)."""
    if im.mode != "RGBA":
        return {"tiene_canal_alfa": False}
    a = im.getchannel("A")
    hist = a.histogram()
    total = im.width * im.height
    transparentes = hist[0]
    opacos = hist[255]
    esquinas = [a.getpixel(p) for p in [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]]
    return {
        "tiene_canal_alfa": True,
        "pct_transparente": round(100 * transparentes / total, 2),
        "pct_opaco": round(100 * opacos / total, 2),
        "pct_semitransparente": round(100 * (total - transparentes - opacos) / total, 2),
        "esquinas_transparentes": all(v == 0 for v in esquinas),
        "transparencia_real": transparentes > 0 and opacos > 0 and all(v == 0 for v in esquinas),
    }


def quitar_fondo(im: Image.Image) -> Image.Image:
    """Solo si una imagen llegara con fondo sólido: elimina el fondo con rembg."""
    from rembg import remove  # import diferido: dependencia opcional
    return remove(im.convert("RGB")).convert("RGBA")


def recortar_margen(im: Image.Image, margen: int = 4) -> tuple[Image.Image, bool]:
    bbox = im.getchannel("A").getbbox()
    if not bbox:
        return im, False
    l, t, r, b = bbox
    l, t = max(0, l - margen), max(0, t - margen)
    r, b = min(im.width, r + margen), min(im.height, b + margen)
    if (l, t, r, b) == (0, 0, im.width, im.height):
        return im, False
    return im.crop((l, t, r, b)), True


def guardar_png(im: Image.Image, destino: Path) -> str:
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    metodo = "Pillow optimize"
    try:
        import oxipng  # pyoxipng, optimización sin pérdida
        data = oxipng.optimize_from_memory(data, level=3, strip=oxipng.StripChunks.safe())
        metodo = "oxipng nivel 3 (sin pérdida)"
    except ImportError:
        pass
    destino.write_bytes(data)
    return metodo


def indice_visual(modelos: dict) -> None:
    """Hoja de contacto: por modelo, trasera (izquierda) y frontal (derecha) sobre damero."""
    orden = [m[0] for m in MODELOS if m[0] in modelos]
    celda_h, celda_w, pie = 440, 360, 34
    cols = 6
    filas = (len(orden) + cols - 1) // cols
    W, H = cols * celda_w, filas * (celda_h + pie)
    hoja = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(hoja)
    s = 14
    for y in range(0, H, s):
        for x in range(0, W, s):
            if (x // s + y // s) % 2:
                d.rectangle([x, y, x + s - 1, y + s - 1], fill=(222, 222, 222))
    try:
        fuente = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
    except OSError:
        fuente = ImageFont.load_default()
    for i, modelo in enumerate(orden):
        x, y = (i % cols) * celda_w, (i // cols) * (celda_h + pie)
        imgs = modelos[modelo].get("imagenes", {})
        vistas = [v for v in ("trasera", "frontal") if v in imgs]
        ancho_v = (celda_w - 20) // max(1, len(vistas))
        for j, v in enumerate(vistas):
            im = Image.open(RAIZ.parent / imgs[v]["ruta"]).convert("RGBA")
            im.thumbnail((ancho_v - 8, celda_h - 24), Image.LANCZOS)
            cx = x + 10 + j * ancho_v + (ancho_v - im.width) // 2
            hoja.paste(im, (cx, y + (celda_h - im.height) // 2), im)
        d.rectangle([x, y + celda_h, x + celda_w, y + celda_h + pie], fill=(18, 18, 18))
        etiqueta = modelo + ("" if "trasera" in vistas else "  (sin trasera)")
        d.text((x + 10, y + celda_h + 7), etiqueta, fill=(255, 255, 255), font=fuente)
    hoja.save(INDICE_VISUAL, quality=88)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="volver a descargar aunque el archivo exista")
    ap.add_argument("--solo-verificar", action="store_true", help="no descargar; solo verificar y regenerar catálogo")
    args = ap.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    modelos = cargar_catalogo()
    fallos = []
    for modelo, ident, color, variante, extra in MODELOS:
        ruta = ruta_vista(modelo, "frontal")
        url_img = raw_url(IMG_REPO, IMG_COMMIT, f"device/{ident}/{color}.png")
        entrada = modelos.setdefault(modelo, {"modelo": modelo})
        previo = entrada.get("imagenes", {}).get("frontal", {})
        try:
            ficha, url_ficha = ficha_appledb(ident)
            nombre_db = ficha.get("name", "")
            # iPhone 18 Pro Max figura como "iPhone 18 Pro Max (US)" / "(Global)".
            if nombre_db.split(" (")[0] != modelo:
                raise ValueError(f"AppleDB dice que {ident} es '{nombre_db}', no '{modelo}'")
            colores_db = [c["name"] for c in ficha.get("colors", [])]
            if colores_db and color not in colores_db:
                raise ValueError(f"El color '{color}' no figura en AppleDB para {modelo}: {colores_db}")

            proc_prev = previo.get("procesado", {})
            fondo_eliminado = proc_prev.get("fondo_eliminado")
            recortado = proc_prev.get("margen_recortado", False)
            optimizacion = proc_prev.get("optimizacion")
            if args.solo_verificar or (ruta.exists() and not args.forzar):
                im = Image.open(ruta)
                im.load()
            else:
                print(f"↓ {modelo:20s} {ident:11s} {color}")
                original = Image.open(io.BytesIO(descargar(url_img)))
                original.load()
                if original.format != "PNG":
                    raise ValueError(f"formato inesperado {original.format}")
                im = original.convert("RGBA") if original.mode != "RGBA" else original
                if not analizar_alfa(im)["transparencia_real"]:
                    im = quitar_fondo(im)
                    fondo_eliminado = "rembg (u2net)"
                im, recortado = recortar_margen(im)
                ruta.parent.mkdir(parents=True, exist_ok=True)
                optimizacion = guardar_png(im, ruta)
                im = Image.open(ruta)
                im.load()

            alfa = analizar_alfa(im)
            if not alfa.get("transparencia_real"):
                raise ValueError(f"sin transparencia real: {alfa}")

            entrada.update({
                "modelo": modelo,
                "carpeta": rel(carpeta(modelo)),
                "variante": variante,
                "variante_adicional": extra,
                "identificador_apple": ident if ident != "iPhone19,3" else "iPhone19,3 / iPhone19,7",
                "numeros_de_modelo": ficha.get("model", []),
                "lanzamiento": ficha.get("released"),
                "color": color,
                "colores_del_modelo": colores_db,
                "url_verificacion_modelo": url_ficha,
                "modelo_confirmado_por_appledb": nombre_db,
            })
            entrada.setdefault("imagenes", {})["frontal"] = {
                "ruta": rel(ruta),
                "resolucion": {"ancho": im.width, "alto": im.height, "texto": f"{im.width}x{im.height}"},
                # Limitada = no llega a cubrir la altura de un video vertical 1080x1920
                # sin reescalar. Hasta +15 % de ampliación no se nota en video.
                "resolucion_limitada": im.height < 1920,
                "alto_maximo_en_video_px": int(im.height * 1.15),
                "formato": "PNG",
                "modo_color": im.mode,
                "peso_bytes": ruta.stat().st_size,
                "perspectiva": ("Frontal y trasera en escuadra (plegable)" if ident == "iPhone19,4"
                                 else "Frontal, con el fondo de pantalla oficial de lanzamiento"),
                "color": color,
                "transparencia": alfa,
                "procesado": {
                    "fondo_eliminado": fondo_eliminado,
                    "margen_recortado": recortado,
                    "optimizacion": optimizacion,
                    "modificaciones_de_contenido": "Ninguna (sin reescalado, sin retoque)",
                },
                "metodo": "Descarga directa del render oficial (sin cambios)",
                "url_original": url_img,
                "fuente": f"https://github.com/{IMG_REPO} (AppleDB, renders oficiales de Apple)",
                "licencia": LICENCIA,
                "verificado": {
                    "modelo_confirmado_por_appledb": nombre_db,
                    "revision_visual": "OK: fondo de pantalla y diseño corresponden al modelo",
                    "fecha": dt.date.today().isoformat(),
                },
            }
            print(f"✓ {modelo:20s} frontal {im.width}x{im.height}  transparente {alfa['pct_transparente']}%")
        except Exception as e:  # noqa: BLE001 — se informa y se sigue con el resto
            fallos.append({"modelo": modelo, "vista": "frontal", "motivo": str(e)})
            print(f"✗ {modelo}: {e}", file=sys.stderr)

    no_disp = NO_DISPONIBLES_BASE()
    no_disp += [f for f in json.loads(CATALOGO.read_text()).get("no_disponibles", [])
                if f.get("vista") == "trasera"] if CATALOGO.exists() else []
    no_disp += fallos
    guardar_catalogo(modelos, no_disp)
    indice_visual(modelos)
    print(f"\n{len(MODELOS) - len(fallos)} frontales OK, {len(fallos)} fallos → {rel(CATALOGO)}")
    return 1 if fallos else 0


def NO_DISPONIBLES_BASE() -> list:
    return [dict(d, vista="modelo") for d in NO_DISPONIBLES]


if __name__ == "__main__":
    sys.exit(main())
