#!/usr/bin/env python3
"""
Biblioteca de accesorios Apple: RECURSOS/ACCESORIOS/<Accesorio>/
  <Accesorio>_media_vuelta.mov / .webm / _preview.mp4   animación 3D media vuelta (fondo transparente)
  <Accesorio>_frontal.png / _trasera.png                cuadro inicial y final de la animación (PNG RGBA)
  <Accesorio>_oficial.png                               foto oficial de la Apple Store (PNG RGBA)
y genera RECURSOS/ACCESORIOS/catalogo.json + _indice_visual.jpg.

Las animaciones se generan con anim_media_vuelta.py (Blender):
  AirPods Pro 3 ............ modelo 3D oficial de Apple (AR Quick Look)
  Cargadores 20W y MagSafe . modelos 3D a medida (modelos_accesorios.py), proporciones de las fotos oficiales
  Funda de silicona ........ funda a medida (funda_silicona.py) sobre el modelo 3D oficial del iPhone 18 Pro Max

uso: python3 RECURSOS/_scripts/accesorios.py --cuadros DIR [--solo Clave ...]
     (DIR/<Accesorio>[_c]/0000.png ... 0048.png; sin --cuadros sólo rehace catálogo e índice)
"""
import argparse, datetime as dt, json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from descargar_iphones import analizar_alfa, descargar, guardar_png  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
DEST = RAIZ / "ACCESORIOS"
STORE = "https://store.storeimages.cdn-apple.com/4982/as-images.apple.com/is/{}?scl=1&fmt=png-alpha"
AR = "https://www.apple.com/105/media/us/{}"

ACCESORIOS = {
    "AirPods_Pro_3": {
        "nombre": "AirPods Pro 3", "oficial": "airpods-pro-3-hero-select-202509",
        "alias": ["airpods pro", "airpods pro 3", "airpods"],
        "metodo_3d": "Modelo 3D oficial de Apple (AR Quick Look): estuche abierto con los auriculares",
        "fuente_3d": AR.format("airpods-pro/2025/7acffb13-4adb-40b1-9393-8f1c99bc6c90/ar/airpods-pro.usdz"),
        "vistas": {"frontal": "Frente del estuche abierto (LED) con los auriculares", "trasera": "Dorso del estuche con la tapa"},
    },
    "Cargador_20W_USB-C": {
        "nombre": "Cargador Apple 20W USB-C (MWVV3AM/A)", "oficial": "MWVV3",
        "alias": ["cargador 20w", "cargador de 20w", "cargador usb-c", "cubo", "cargador del iphone", "cargador"],
        "metodo_3d": "Modelo 3D hecho a medida con Blender (Apple no publica modelo 3D): 42,5 x 42,3 x 27,4 mm, "
                     "patas tipo A y puerto USB-C, proporciones medidas en las fotos oficiales MWVV3, _AV1 y _AV2",
        "fuente_3d": "RECURSOS/_scripts/modelos_accesorios.py (cargador_20w)",
        "vistas": {"frontal": "Cara ancha con las patas arriba", "trasera": "Cara opuesta"},
    },
    "Cargador_MagSafe": {
        "nombre": "Cargador MagSafe de Apple (MGD74LL/A)", "oficial": "MGD74",
        "alias": ["magsafe", "cargador magsafe", "cargador inalámbrico", "cargador inalambrico"],
        "metodo_3d": "Modelo 3D hecho a medida con Blender (Apple no publica modelo 3D): disco de 55,9 mm con "
                     "aro de aluminio, cable y conector USB-C, según las fotos oficiales MGD74, _AV2 y _AV3",
        "fuente_3d": "RECURSOS/_scripts/modelos_accesorios.py (cargador_magsafe)",
        "vistas": {"frontal": "Cara blanca de carga", "trasera": "Dorso de aluminio"},
    },
    "Funda_Silicona_iPhone_18_Pro_Max_Magenta": {
        "nombre": "Funda de silicona con MagSafe para iPhone 18 Pro Max – Magenta (MK904ZM/A)", "oficial": "MK904",
        "alias": ["funda", "funda de silicona", "case", "funda magenta", "funda del iphone"],
        "metodo_3d": "Funda construida a medida (funda_silicona.py) sobre el modelo 3D oficial del iPhone 18 Pro Max: "
                     "pared de 1,3 mm, borde sobre la pantalla, recorte de la meseta de cámaras; color y logo "
                     "tomados de la foto oficial MK904",
        "fuente_3d": AR.format("iphone-18-pro/2026/591df885-5ee2-4173-86e6-401021249f7c/ar/iphone-18-pro-e-sim.usdz")
                     + " + RECURSOS/_scripts/funda_silicona.py",
        "vistas": {"frontal": "iPhone 18 Pro Max de frente con la funda", "trasera": "Dorso de la funda Magenta"},
    },
}
LICENCIA = {
    "titular_derechos": "Apple Inc. (productos, fotos y modelos 3D oficiales)",
    "uso_previsto_permitido": "Uso nominativo/editorial: identificar el producto en reseñas, comparativas, "
                              "tutoriales y contenido de venta de productos Apple, sin sugerir patrocinio de Apple.",
    "precaucion": "Los modelos a medida (cargadores y funda) son recreaciones 3D del producto real. Para "
                  "publicidad paga con el producto como protagonista, revisar las pautas de marca de Apple.",
}


def recortar(im, m=6):
    bb = im.getchannel("A").getbbox()
    return im.crop((max(0, bb[0] - m), max(0, bb[1] - m), min(im.width, bb[2] + m), min(im.height, bb[3] + m)))


def info_video(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=width,height,nb_read_frames", "-of", "json", str(p)], capture_output=True, text=True)
    s = json.loads(r.stdout)["streams"][0]
    return {"resolucion": f"{s['width']}x{s['height']}", "cuadros": int(s["nb_read_frames"]), "fps": 30,
            "duracion_s": round(int(s["nb_read_frames"]) / 30, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuadros", help="carpeta con los cuadros renderizados (para las imágenes fijas)")
    ap.add_argument("--solo", nargs="*", help="actualizar sólo estos accesorios (el catálogo conserva los demás)")
    args = ap.parse_args()
    previo = {}
    if (DEST / "catalogo.json").exists():
        previo = {e["clave"]: e for e in json.loads((DEST / "catalogo.json").read_text())["accesorios"]}
    cat = []
    for clave, a in ACCESORIOS.items():
        d = DEST / clave; d.mkdir(parents=True, exist_ok=True)
        if args.solo and clave not in args.solo:
            if clave in previo:
                cat.append(previo[clave])
            continue
        e = {"accesorio": a["nombre"], "clave": clave, "carpeta": f"RECURSOS/ACCESORIOS/{clave}", "alias": a["alias"],
             "metodo_3d": a["metodo_3d"], "fuente_3d": a["fuente_3d"], "licencia": LICENCIA, "imagenes": {}}
        if args.cuadros:
            fr = Path(args.cuadros) / f"{clave}_c"
            fr = fr if fr.exists() else Path(args.cuadros) / clave
            for vista, n in (("frontal", "0000"), ("trasera", "0048")):
                if (fr / f"{n}.png").exists():
                    guardar_png(recortar(Image.open(fr / f"{n}.png").convert("RGBA")), d / f"{clave}_{vista}.png")
        of = d / f"{clave}_oficial.png"
        if not of.exists():
            guardar_png(recortar(Image.open(__import__("io").BytesIO(descargar(STORE.format(a["oficial"])))).convert("RGBA")), of)
        for vista in ("frontal", "trasera", "oficial"):
            p = d / f"{clave}_{vista}.png"
            if p.exists():
                im = Image.open(p)
                e["imagenes"][vista] = {
                    "ruta": f"RECURSOS/ACCESORIOS/{clave}/{p.name}", "resolucion": f"{im.width}x{im.height}",
                    "descripcion": a["vistas"].get(vista, "Foto oficial de la Apple Store"),
                    "transparencia": analizar_alfa(im),
                    "url_original": STORE.format(a["oficial"]) if vista == "oficial" else None,
                }
        base = d / f"{clave}_media_vuelta"
        if Path(f"{base}.webm").exists():
            e["animacion_media_vuelta"] = {"mov_prores4444_alfa": f"RECURSOS/ACCESORIOS/{clave}/{base.name}.mov",
                                           "webm_vp9_alfa": f"RECURSOS/ACCESORIOS/{clave}/{base.name}.webm",
                                           "preview_mp4": f"RECURSOS/ACCESORIOS/{clave}/{base.name}_preview.mp4",
                                           **info_video(f"{base}.webm")}
        cat.append(e)
        print("✓", clave, list(e["imagenes"]), "animación" if "animacion_media_vuelta" in e else "")
    (DEST / "catalogo.json").write_text(json.dumps({
        "biblioteca": "RECURSOS/ACCESORIOS", "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": "RECURSOS/_scripts/accesorios.py", "accesorios": cat}, ensure_ascii=False, indent=2) + "\n")
    # índice visual: oficial | frontal | trasera
    filas = len(cat); cw, ch, pie = 360, 420, 34
    hoja = Image.new("RGB", (3 * cw, filas * (ch + pie)), (255, 255, 255)); dr = ImageDraw.Draw(hoja)
    for y in range(0, hoja.height, 14):
        for x in range(0, hoja.width, 14):
            if (x // 14 + y // 14) % 2: dr.rectangle([x, y, x + 13, y + 13], fill=(222, 222, 222))
    try: f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    except OSError: f = ImageFont.load_default()
    for i, e in enumerate(cat):
        for j, v in enumerate(("oficial", "frontal", "trasera")):
            if v in e["imagenes"]:
                im = Image.open(RAIZ.parent / e["imagenes"][v]["ruta"]).convert("RGBA"); im.thumbnail((cw - 30, ch - 30))
                hoja.paste(im, (j * cw + (cw - im.width) // 2, i * (ch + pie) + (ch - im.height) // 2), im)
            dr.rectangle([j * cw, i * (ch + pie) + ch, (j + 1) * cw, (i + 1) * (ch + pie)], fill=(18, 18, 18))
            dr.text((j * cw + 8, i * (ch + pie) + ch + 8), f"{e['clave'][:28]} · {v}", fill=(255, 255, 255), font=f)
    hoja.save(DEST / "_indice_visual.jpg", quality=88)


if __name__ == "__main__":
    main()
