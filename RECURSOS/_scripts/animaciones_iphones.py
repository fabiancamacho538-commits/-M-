#!/usr/bin/env python3
"""
Animaciones 3D "media vuelta" de iPhone: el equipo arranca mostrando la PANTALLA y gira 180°
hasta mostrar la TRASERA, con fondo transparente. Se renderiza el modelo 3D oficial de Apple
(USDZ de AR Quick Look) con Blender y el color se calibra contra la foto oficial del mismo modelo.

Salidas en RECURSOS/IPHONES/<Modelo>/:
  <Modelo>_media_vuelta.mov           ProRes 4444 con canal alfa (Premiere, Final Cut, DaVinci, After Effects)
  <Modelo>_media_vuelta.webm          VP9 con canal alfa (web, Remotion, HyperFrames, navegadores)
  <Modelo>_media_vuelta_preview.mp4   vista previa H.264 sobre fondo oscuro (sin alfa)

Uso:
    BLENDER_PY=/ruta/blenv/bin/python python3 RECURSOS/_scripts/animaciones_iphones.py [--modelos "iPhone 16 Pro Max,iPhone 17"]
    python3 RECURSOS/_scripts/animaciones_iphones.py --solo-catalogo   # registra en catalogo.json lo que ya exista
Opciones: --cuadros 48 (1,6 s a 30 fps) --muestras 8 --ancho 1080 --alto 1920 --forzar
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from descargar_iphones import MODELOS, NO_DISPONIBLES, cargar_catalogo, descargar, guardar_catalogo, rel, ruta_vista, slug  # noqa: E402
from traseras_iphones import AR, LICENCIA_TRASERA, STORE, TRASERAS, Y709, caja_trasera, color_parche, l2s, s2l  # noqa: E402

FPS = 30
# Modelos con modelo 3D oficial de una sola pieza (el resto no tiene USDZ individual publicado).
EXTRA_3D = {
    "iPhone 16e": ("iphone/shared/ar/2025/aa5fba56-f772-4712-9d4c-0516416169e3/iphone-16e/iphone16_e_white.usdz",
                   "iphone-16e-white-select-202502", ""),
    "iPhone 17e": ("iphone/shared/ar/2026/44fa1631-e6c3-4596-b59b-0d58f7e8735c/iphone-17e/iphone-17e-e-sim-soft-pink.usdz",
                   "iphone-17e-finish-select-softpink-202603", ""),
}


def fuentes_3d() -> dict:
    d = {m: (src, ref, hide) for m, (met, src, ref, hide) in TRASERAS.items() if met == "3d"}
    d.update(EXTRA_3D)
    return d


def _ganancias(cr: np.ndarray, cn: np.ndarray) -> np.ndarray:
    g = cr / cn
    lum = (cr @ Y709) / (cn @ Y709)
    return np.clip(g / (g @ Y709), 0.85, 1.18) * np.clip(lum, 0.6, 1.6)


def _parche_pantalla(a: np.ndarray) -> np.ndarray:
    al = a[..., 3]
    cols = np.where(al.max(0) > 0.5)[0]; rows = np.where(al.max(1) > 0.5)[0]
    x0, W, y0, H = cols[0], cols[-1] - cols[0], rows[0], rows[-1] - rows[0]
    p = a[int(y0 + 0.25 * H):int(y0 + 0.75 * H), int(x0 + 0.25 * W):int(x0 + 0.75 * W)]
    return s2l(p[..., :3][p[..., 3] > 0.98]).mean(0)


def calibrar_y_aplicar(frames: list[Path], ref: np.ndarray, frontal: np.ndarray, ratio: float, outdir: Path) -> dict:
    """Calibra los dos extremos: el cuadro inicial (pantalla) contra la imagen frontal oficial y el
    cuadro final (trasera) contra la foto oficial; en el medio interpola mientras el equipo está de canto."""
    rgba = lambda f: np.asarray(Image.open(f).convert("RGBA")).astype(float) / 255
    first, last = rgba(frames[0]), rgba(frames[-1])
    gb = _ganancias(color_parche(ref, caja_trasera(ref[..., 3], ratio, True)),
                    color_parche(last, caja_trasera(last[..., 3], ratio, False)))
    gf = _ganancias(_parche_pantalla(frontal), _parche_pantalla(first))
    outdir.mkdir(parents=True, exist_ok=True)
    n = len(frames) - 1
    for i, f in enumerate(frames):
        t = float(np.clip((i / n - 0.35) / 0.30, 0, 1)); w = t * t * (3 - 2 * t)
        g = np.exp((1 - w) * np.log(gf) + w * np.log(gb))
        a = rgba(f)
        rgb = l2s(np.clip(s2l(a[..., :3]) * g, 0, 1))
        Image.fromarray((np.dstack([rgb, a[..., 3]]) * 255).round().clip(0, 255).astype(np.uint8), "RGBA").save(outdir / f.name)
    return {"pantalla": [round(float(x), 3) for x in gf], "trasera": [round(float(x), 3) for x in gb]}


def codificar(frames_dir: Path, base: Path, ancho: int, alto: int) -> None:
    pat = str(frames_dir / "%04d.png")
    run = lambda *a: subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
    run("-framerate", str(FPS), "-i", pat, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        "-vendor", "apl0", "-qscale:v", "9", f"{base}.mov")
    run("-framerate", str(FPS), "-i", pat, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28",
        "-row-mt", "1", "-auto-alt-ref", "0", f"{base}.webm")
    run("-f", "lavfi", "-i", f"color=c=0x101114:s={ancho}x{alto}:r={FPS}", "-framerate", str(FPS), "-i", pat,
        "-filter_complex", "[0:v][1:v]overlay=shortest=1,format=yuv420p", "-c:v", "libx264", "-crf", "20",
        "-movflags", "+faststart", f"{base}_preview.mp4")


def registrar(modelos: dict, modelo: str, info: dict | None = None) -> bool:
    base = ruta_vista(modelo, "trasera").parent / f"{slug(modelo)}_media_vuelta"
    mov, webm, prev = Path(f"{base}.mov"), Path(f"{base}.webm"), Path(f"{base}_preview.mp4")
    if not (mov.exists() and webm.exists()):
        return False
    meta = {}
    try:
        p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                            "stream=width,height,nb_read_frames", "-of", "json", str(webm)],
                           capture_output=True, text=True, check=True)
        s = json.loads(p.stdout)["streams"][0]
        meta = {"ancho": s["width"], "alto": s["height"], "cuadros": int(s["nb_read_frames"])}
    except Exception:  # noqa: BLE001
        pass
    prev_info = modelos.get(modelo, {}).get("animaciones", {}).get("media_vuelta", {})
    src, ref, _ = fuentes_3d()[modelo]
    entrada = {
        "descripcion": "Media vuelta 3D: arranca mostrando la pantalla y gira 180° hasta la trasera "
                       "(entrada y salida suaves). Fondo transparente.",
        "mov_prores4444_alfa": rel(mov),
        "webm_vp9_alfa": rel(webm),
        "preview_mp4": rel(prev) if prev.exists() else None,
        "resolucion": f"{meta.get('ancho', 1080)}x{meta.get('alto', 1920)}",
        "fps": FPS,
        "cuadros": meta.get("cuadros"),
        "duracion_s": round(meta["cuadros"] / FPS, 2) if meta.get("cuadros") else None,
        "metodo": "Render Blender Cycles del modelo 3D oficial de Apple (AR Quick Look), cámara 85 mm; "
                  "color calibrado en los dos extremos: pantalla contra la imagen frontal oficial y trasera "
                  "contra la foto oficial de la Apple Store",
        "url_modelo_3d": AR.format(src),
        "calibrado_contra": STORE.format(ref),
        "balance_rgb": (info or {}).get("balance_rgb", prev_info.get("balance_rgb")),
        "licencia": LICENCIA_TRASERA,
    }
    modelos.setdefault(modelo, {"modelo": modelo}).setdefault("animaciones", {})["media_vuelta"] = entrada
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", help="lista separada por comas (por defecto, todos los que tienen modelo 3D)")
    ap.add_argument("--cuadros", type=int, default=48)
    ap.add_argument("--muestras", type=int, default=8)
    ap.add_argument("--ancho", type=int, default=1080)
    ap.add_argument("--alto", type=int, default=1920)
    ap.add_argument("--ev-json", help="JSON {<Modelo>: ev} de la calibración de las traseras")
    ap.add_argument("--cache", default=str(Path(tempfile.gettempdir()) / "iphones_cache"))
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--solo-catalogo", action="store_true")
    args = ap.parse_args()
    cache = Path(args.cache); cache.mkdir(parents=True, exist_ok=True)
    fuentes = fuentes_3d()
    lista = [m.strip() for m in args.modelos.split(",")] if args.modelos else [m[0] for m in MODELOS if m[0] in fuentes]
    blender_py = os.environ.get("BLENDER_PY")
    evs = json.loads(Path(args.ev_json).read_text()) if args.ev_json else {}

    modelos = cargar_catalogo()
    for modelo in lista:
        if not args.solo_catalogo:
            base = ruta_vista(modelo, "trasera").parent / f"{slug(modelo)}_media_vuelta"
            if Path(f"{base}.webm").exists() and not args.forzar:
                registrar(modelos, modelo)
                continue
            if not blender_py:
                print(f"✗ {modelo}: falta BLENDER_PY", file=sys.stderr); continue
            src, ref_name, hide = fuentes[modelo]
            usdz = cache / Path(src).name
            if not usdz.exists():
                usdz.write_bytes(descargar(AR.format(src)))
            ref_p = cache / f"{ref_name}.png"
            if not ref_p.exists():
                ref_p.write_bytes(descargar(STORE.format(ref_name)))
            ev = float(evs.get(slug(modelo), 0.0)) - 0.3
            crudo, final = cache / f"{slug(modelo)}_anim", cache / f"{slug(modelo)}_anim_c"
            env = dict(os.environ, EXPO=str(ev), HIDE=hide)
            subprocess.run([blender_py, str(Path(__file__).parent / "anim_media_vuelta.py"), "--", str(usdz), str(crudo),
                            str(args.ancho), str(args.alto), str(args.cuadros), str(args.muestras)],
                           env=env, check=True, capture_output=True)
            frontal_im = Image.open(ruta_vista(modelo, "frontal"))
            fw, fh = frontal_im.size
            frontal = np.asarray(frontal_im.convert("RGBA")).astype(float) / 255
            ref = np.asarray(Image.open(ref_p).convert("RGBA")).astype(float) / 255
            g = calibrar_y_aplicar(sorted(crudo.glob("*.png")), ref, frontal, fw / fh, final)
            codificar(final, base, args.ancho, args.alto)
            registrar(modelos, modelo, {"balance_rgb": g})
            print(f"✓ {modelo}: {base.name}.mov / .webm / _preview.mp4")
        else:
            registrar(modelos, modelo)
    no_disp = json.loads((Path(__file__).parents[1] / "IPHONES" / "catalogo.json").read_text()).get("no_disponibles", [])
    guardar_catalogo(modelos, no_disp)
    n = sum(1 for m in modelos.values() if "animaciones" in m)
    print(f"{n} modelos con animación media vuelta registrados en el catálogo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
