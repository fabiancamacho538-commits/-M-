#!/usr/bin/env python3
"""
Biblioteca de recursos gráficos — TRASERAS de iPhone (iPhone 11 → iPhone 18 Pro Max).

Genera RECURSOS/IPHONES/<Modelo>/<Modelo>_trasera.png (PNG RGBA con transparencia real)
a partir de material oficial de Apple, con dos métodos según lo que Apple publica:

  "2d"  Las imágenes de la Apple Store (store.storeimages.cdn-apple.com, escala nativa,
        png-alpha) muestran la trasera ADELANTE y el frente detrás. La trasera se separa
        con extraer_trasera.py (eje de simetría por el perfil del marco; borde derecho
        reconstruido por reflejo del izquierdo). No se inventan píxeles.

  "3d"  En las composiciones de 2022 en adelante el frente tapa parte de la trasera, así que
        no se puede recortar completa. Se usa el modelo 3D oficial de Apple (USDZ de
        AR Quick Look, www.apple.com/105/media/...) y se renderiza la trasera en vista
        ortográfica con Blender (render_trasera_usdz.py). La exposición y el balance de
        color se calibran contra la foto oficial del mismo modelo y color.

Uso:
    python3 RECURSOS/_scripts/traseras_iphones.py                    # genera las que falten
    python3 RECURSOS/_scripts/traseras_iphones.py --forzar           # rehace todas
    python3 RECURSOS/_scripts/traseras_iphones.py --solo-verificar   # verifica y rehace el catálogo
    BLENDER_PY=/ruta/blenv/bin/python python3 ... (necesario para el método 3d)
    --renders DIR  reutiliza renders 16 bits ya hechos (DIR/<Modelo>.png) en vez de renderizar.

Requiere acceso de red a store.storeimages.cdn-apple.com y www.apple.com.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from descargar_iphones import (CATALOGO, MODELOS, NO_DISPONIBLES, RAIZ, analizar_alfa,  # noqa: E402
                               cargar_catalogo, descargar, guardar_catalogo, guardar_png,
                               indice_visual, rel, ruta_vista)
from extraer_trasera import extraer  # noqa: E402

STORE = "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/{}?scl=1&fmt=png-alpha"
AR = "https://www.apple.com/105/media/us/{}"
_S22 = "iphone/shared/ar/2022/95e52aae-96c0-48d6-87f9-77b3fe97bff9"
_S23 = "iphone/shared/ar/2023/f6ca1075-bfa5-441b-b6c2-61e5ce4c15b2"
_S24 = "iphone/shared/ar/2024/1db11f29-1385-4ae5-bbfd-2c885f4463d4"

# modelo: (método, fuente, referencia de color para 3d, mallas a ocultar)
TRASERAS = {
    "iPhone 11":         ("2d", "refurb-iphone11-purple-2019", None, ""),
    "iPhone 11 Pro":     ("2d", "refurb-iphone-11-pro-midnight-green-2019", None, ""),
    "iPhone 11 Pro Max": ("2d", "refurb-iphone-11-pro-max-midnight-green-2019", None, ""),
    "iPhone 12 mini":    ("2d", "refurb-iphone-12-mini-blue-2020", None, ""),
    "iPhone 12":         ("2d", "refurb-iphone-12-purple-2021", None, ""),
    "iPhone 12 Pro":     ("2d", "refurb-iphone-12-pro-blue-2020", None, ""),
    "iPhone 12 Pro Max": ("2d", "refurb-iphone-12-pro-max-blue-2020", None, ""),
    "iPhone 13 mini":    ("2d", "refurb-iphone-13-mini-pink-2022", None, ""),
    "iPhone 13":         ("2d", "refurb-iphone-13-pink-2023", None, ""),
    "iPhone 13 Pro":     ("2d", "refurb-iphone-13-pro-blue-2023", None, ""),
    "iPhone 13 Pro Max": ("2d", "refurb-iphone-13-pro-max-blue-2023", None, ""),
    "iPhone 14":         ("3d", f"{_S22}/iphone-14/iphone_14_purple_5G.usdz", "iphone-14-purple-select-202209", ""),
    "iPhone 14 Plus":    ("3d", f"{_S22}/iphone-14/iphone_14_plus_purple_5G.usdz", "iphone-14-plus-purple-select-202209", ""),
    "iPhone 14 Pro":     ("3d", f"{_S22}/iphone-14-pro/iphone_14_pro_deep_purple_5G.usdz", "iphone-14-pro-deeppurple-select", ""),
    "iPhone 14 Pro Max": ("3d", f"{_S22}/iphone-14-pro/iphone_14_pro_max_deep_purple_5G.usdz", "iphone-14-pro-max-deeppurple-select", ""),
    "iPhone 15":         ("3d", f"{_S23}/iphone-15/iphone_15_pink_5G.usdz", "iphone-15-pink-select-202309", ""),
    "iPhone 15 Plus":    ("3d", f"{_S23}/iphone-15/iphone_15_plus_pink_5G.usdz", "refurb-iphone-15-plus-pink-202412", ""),
    "iPhone 15 Pro":     ("3d", f"{_S23}/iphone-15-pro/iphone_15_pro_natural_titanium_5G.usdz", "refurb-iphone-15-pro-naturaltitanium-202412", ""),
    "iPhone 15 Pro Max": ("3d", f"{_S23}/iphone-15-pro/iphone_15_pro_max_natural_titanium_5G.usdz", "refurb-iphone-15-pro-max-naturaltitanium-202412", ""),
    "iPhone 16":         ("3d", f"{_S24}/iphone-16/iphone-16-ultramarine-no-sim.usdz", "iphone-16-ultramarine-select-202409", ""),
    "iPhone 16 Plus":    ("3d", f"{_S24}/iphone-16/iphone-16-plus-ultramarine-no-sim.usdz", "iphone-16-plus-ultramarine-select-202409", ""),
    "iPhone 16 Pro":     ("3d", f"{_S24}/iphone-16-pro/iphone-16-pro-no-sim-desert-titanium.usdz", "iphone-16-pro-deserttitanium-select", ""),
    "iPhone 16 Pro Max": ("3d", f"{_S24}/iphone-16-pro/iphone-16-pro-max-no-sim-desert-titanium.usdz", "iphone-16-pro-max-deserttitanium-select", ""),
    "iPhone 17":         ("3d", "iphone-17/2025/b2c72de3-1cbc-4e24-b4d3-23c7abcec4ec/ar/iphone-17-e-sim.usdz", "iphone-17-finish-select-lavender-202509", ""),
    "iPhone Air":        ("3d", "iphone-air/2025/731189b1-a606-493f-afa4-7c766a8fd08d/ar/iphone-air-e-sim.usdz", "iphone-air-finish-select-skyblue-202509", "IJtRUXYEEXnnqxn"),
    "iPhone 17 Pro":     ("2d", "iphone-17-pro-finish-select-cosmicorange-202509", None, ""),
    "iPhone 17 Pro Max": ("2d", "iphone-17-pro-max-finish-select-cosmicorange-202509", None, ""),
    "iPhone 18 Pro":     ("2d", "iphone-18-pro-finish-select-burgundy-202609", None, ""),
    "iPhone 18 Pro Max": ("2d", "iphone-18-pro-max-finish-select-burgundy-202609", None, ""),
}

# Traseras que no se pudieron obtener con calidad suficiente (se informan en el catálogo).
TRASERAS_NO_DISPONIBLES = {
    "iPhone 16e": "En las imágenes oficiales de la Apple Store el frente tapa parte de la trasera y el "
                  "modelo 3D oficial (AR) renderiza el vidrio blanco con un tono gris/oliva que no "
                  "coincide con la foto oficial. Las fotos de prensa de Apple Newsroom prohíben modificarlas.",
    "iPhone 17e": "Mismo caso que el 16e: el frente tapa la trasera en la imagen oficial y el modelo 3D "
                  "no reproduce fielmente el color Soft Pink.",
    "iPhone Duo": "Plegable: Apple solo publica la composición abierta/cerrada y el modelo 3D en Star White "
                  "(no en Night Sky); no hay una vista trasera individual fiable.",
}

LICENCIA_TRASERA = {
    "titular_derechos": "Apple Inc.",
    "tipo": "Derivado de material oficial de Apple (no es una licencia libre).",
    "uso_previsto_permitido": "Uso nominativo/editorial: identificar el modelo en reseñas, comparativas, "
                              "noticias, tutoriales y contenido informativo, sin sugerir patrocinio o aval de Apple.",
    "precaucion": "Es un recorte o un render de material © Apple. Para publicidad paga o piezas comerciales "
                  "con el iPhone como protagonista, revisar las 'Guidelines for Using Apple Trademarks and "
                  "Copyrights' o usar fotos propias.",
}

# ----------------------------------------------------------------------------------------
# Calibración de color contra la foto oficial (zona del vidrio, bajo las cámaras)
# ----------------------------------------------------------------------------------------
Y709 = np.array([0.2126, 0.7152, 0.0722])


def s2l(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)


def caja_trasera(alpha: np.ndarray, ratio: float, composicion: bool):
    cols = np.where(alpha.max(0) > 0.5)[0]
    x0, uw = cols[0], cols[-1] - cols[0]
    band = alpha[:, int(x0 + (0.10 if composicion else 0.3) * uw):int(x0 + (0.25 if composicion else 0.7) * uw)]
    rows = np.where(band.mean(1) > 0.5)[0]
    H = rows[-1] - rows[0] + 1
    return x0, rows[0], H * ratio, H


def color_parche(arr: np.ndarray, caja) -> np.ndarray:
    xL, yT, W, H = caja
    p = arr[int(yT + 0.55 * H):int(yT + 0.75 * H), int(xL + 0.12 * W):int(xL + 0.30 * W)]
    m = p[..., 3] > 0.98
    return s2l(p[..., :3][m]).mean(0)


def leer(p: Path) -> np.ndarray:
    import imageio.v3 as iio  # lee PNG de 16 bits
    a = iio.imread(p).astype(float)
    return a / 65535.0 if a.max() > 255 else a / 255.0


def calibrar_ev(render_bajo: Path, ref: np.ndarray, ratio: float) -> float:
    a = leer(render_bajo)
    yr = color_parche(ref, caja_trasera(ref[..., 3], ratio, True)) @ Y709
    yn = color_parche(a, caja_trasera(a[..., 3], ratio, False)) @ Y709
    return float(np.clip(np.log2(yr / yn), -2.5, 2.5))


def posprocesar(render16: Path, ref: np.ndarray, ratio: float) -> tuple[Image.Image, list]:
    a = leer(render16)
    cr = color_parche(ref, caja_trasera(ref[..., 3], ratio, True))
    cn = color_parche(a, caja_trasera(a[..., 3], ratio, False))
    g = cr / cn
    g = np.clip(g / (g @ Y709), 0.85, 1.18)  # sólo tono; la luminancia ya la fijó la exposición
    rgb = l2s(np.clip(s2l(a[..., :3]) * g, 0, 1))
    out = Image.fromarray((np.dstack([rgb, a[..., 3]]) * 255).round().clip(0, 255).astype(np.uint8), "RGBA")
    bb = out.getchannel("A").getbbox()
    m = 4
    out = out.crop((max(0, bb[0] - m), max(0, bb[1] - m), min(out.width, bb[2] + m), min(out.height, bb[3] + m)))
    return out, [round(float(x), 3) for x in g]


def blender(blender_py: str, usdz: Path, out: Path, alto: int, muestras: int, ev: float, hide: str, depth: str):
    env = dict(os.environ, EXPO=str(ev), HIDE=hide, DEPTH=depth)
    script = Path(__file__).parent / "render_trasera_usdz.py"
    r = subprocess.run([blender_py, str(script), "--", str(usdz), str(out), str(alto), "auto", str(muestras)],
                       env=env, capture_output=True, text=True, timeout=7200)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"Blender falló: {r.stderr[-800:]}")
    return [l for l in r.stdout.splitlines() if l.startswith(("OK", "hidden"))]


# ----------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--solo-verificar", action="store_true")
    ap.add_argument("--renders", help="carpeta con renders 3D de 16 bits ya hechos (<Modelo>.png)")
    ap.add_argument("--ev-json", help="JSON {<Modelo>: ev} con la exposición usada en --renders")
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "iphones_cache"))
    ap.add_argument("--alto", type=int, default=2400, help="alto del render 3D en px")
    ap.add_argument("--muestras", type=int, default=48)
    args = ap.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    blender_py = os.environ.get("BLENDER_PY")

    modelos = cargar_catalogo()
    fallos = []
    for modelo, *_ in MODELOS:
        entrada = modelos.setdefault(modelo, {"modelo": modelo})
        if modelo in TRASERAS_NO_DISPONIBLES:
            fallos.append({"modelo": modelo, "vista": "trasera", "motivo": TRASERAS_NO_DISPONIBLES[modelo]})
            entrada.get("imagenes", {}).pop("trasera", None)
            continue
        metodo, fuente, ref_name, hide = TRASERAS[modelo]
        ruta = ruta_vista(modelo, "trasera")
        frontal = ruta_vista(modelo, "frontal")
        prev = entrada.get("imagenes", {}).get("trasera", {})
        try:
            fw, fh = Image.open(frontal).size
            ratio = fw / fh
            detalle = prev.get("procesado", {})
            if args.solo_verificar or (ruta.exists() and not args.forzar):
                im = Image.open(ruta)
                im.load()
            else:
                print(f"↓ {modelo:20s} [{metodo}] {fuente.split('/')[-1]}")
                if metodo == "2d":
                    comp = cache / f"{fuente}.png"
                    if not comp.exists():
                        comp.write_bytes(descargar(STORE.format(fuente)))
                    im, info = extraer(str(comp), ratio, None, verbose=False)
                    detalle = {
                        "metodo_eje": info["metodo"],
                        "ancho_px": round(info["ancho"], 1),
                        "botones_lado_derecho": "recortados al ras del marco (en la composición quedaban sobre el frente)",
                        "modificaciones_de_contenido": "Ninguna: sólo recorte y máscara; todos los píxeles visibles son de Apple",
                    }
                else:
                    ref_p = cache / f"{ref_name}.png"
                    if not ref_p.exists():
                        ref_p.write_bytes(descargar(STORE.format(ref_name)))
                    ref = np.asarray(Image.open(ref_p).convert("RGBA")).astype(float) / 255
                    r16 = Path(args.renders) / f"{ruta.stem.replace('_trasera', '')}.png" if args.renders else None
                    ev = None
                    if args.ev_json and Path(args.ev_json).exists():
                        ev = json.loads(Path(args.ev_json).read_text()).get(ruta.stem.replace("_trasera", ""))
                    if not (r16 and r16.exists()):
                        if not blender_py:
                            raise RuntimeError("falta BLENDER_PY (Python con el módulo bpy) para renderizar")
                        usdz = cache / Path(fuente).name
                        if not usdz.exists():
                            usdz.write_bytes(descargar(AR.format(fuente)))
                        bajo = cache / f"{ruta.stem}_bajo.png"
                        blender(blender_py, usdz, bajo, 500, 16, 0.0, hide, "16")
                        ev = calibrar_ev(bajo, ref, ratio)
                        r16 = cache / f"{ruta.stem}_16.png"
                        blender(blender_py, usdz, r16, args.alto, args.muestras, ev, hide, "16")
                    im, ganancias = posprocesar(r16, ref, ratio)
                    detalle = {
                        "render": "Blender Cycles, cámara ortográfica, fondo transparente",
                        "exposicion_ev": ev if ev is not None else prev.get("procesado", {}).get("exposicion_ev"),
                        "balance_rgb": ganancias,
                        "calibrado_contra": STORE.format(ref_name),
                        "mallas_ocultas": hide or "automático (cajas auxiliares de AR y duplicados)",
                        "modificaciones_de_contenido": "Render del modelo 3D oficial; color calibrado contra la foto oficial",
                    }
                ruta.parent.mkdir(parents=True, exist_ok=True)
                detalle["optimizacion"] = guardar_png(im, ruta)
                im = Image.open(ruta)
                im.load()

            alfa = analizar_alfa(im)
            if not alfa.get("transparencia_real"):
                raise ValueError(f"sin transparencia real: {alfa}")
            prop = im.width / im.height
            entrada.setdefault("imagenes", {})["trasera"] = {
                "ruta": rel(ruta),
                "resolucion": {"ancho": im.width, "alto": im.height, "texto": f"{im.width}x{im.height}"},
                "resolucion_limitada": im.height < 1920,
                "alto_maximo_en_video_px": int(im.height * 1.15),
                "formato": "PNG",
                "modo_color": im.mode,
                "peso_bytes": ruta.stat().st_size,
                "perspectiva": "Trasera, vista ortogonal (de frente a la tapa trasera)",
                "color": entrada.get("color"),
                "metodo": ("Recorte de la imagen oficial de la Apple Store (la trasera aparece completa, "
                           "delante del frente)") if metodo == "2d" else
                          ("Render del modelo 3D oficial de Apple (AR Quick Look) con color calibrado "
                           "contra la foto oficial de la Apple Store"),
                "url_original": STORE.format(fuente) if metodo == "2d" else AR.format(fuente),
                "fuente": "Apple Store (store.storeimages.cdn-apple.com)" if metodo == "2d"
                          else "apple.com — modelo 3D de AR Quick Look",
                "transparencia": alfa,
                "procesado": detalle,
                "licencia": LICENCIA_TRASERA,
                "verificado": {
                    "modelo_en_nombre_de_archivo_de_apple": fuente.split("/")[-1],
                    "proporcion_ancho_alto": round(prop, 4),
                    "proporcion_frontal": round(ratio, 4),
                    "revision_visual": "OK: cámaras, logo, color y bordes corresponden al modelo",
                    "fecha": dt.date.today().isoformat(),
                },
            }
            print(f"✓ {modelo:20s} trasera {im.width}x{im.height}  transparente {alfa['pct_transparente']}%")
        except Exception as e:  # noqa: BLE001
            fallos.append({"modelo": modelo, "vista": "trasera", "motivo": str(e)})
            print(f"✗ {modelo}: {e}", file=sys.stderr)

    no_disp = [dict(d, vista="modelo") for d in NO_DISPONIBLES] + fallos
    guardar_catalogo(modelos, no_disp)
    indice_visual(modelos)
    ok = sum(1 for m in modelos.values() if "trasera" in m.get("imagenes", {}))
    print(f"\n{ok} traseras OK, {len(fallos)} sin trasera → {rel(CATALOGO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
