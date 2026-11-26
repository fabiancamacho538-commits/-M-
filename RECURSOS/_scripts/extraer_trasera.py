#!/usr/bin/env python3
"""
Extrae la vista TRASERA individual de una composición oficial de Apple
(trasera adelante + frente detrás, PNG con transparencia real).

Cómo funciona:
  1. Mide el borde izquierdo, el superior y el inferior de la trasera con el canal alfa.
  2. Encuentra el eje de simetría vertical con el logo de Apple, que siempre está centrado
     (búsqueda subpíxel sobre una versión pasa-altos para que no influya el degradé de luz).
  3. El borde derecho, que en la composición está superpuesto al frente, se reconstruye
     reflejando el contorno izquierdo (antialiasado exacto, esquinas incluidas). En el tramo
     recto se usa un borde vertical limpio, para no copiar el botón lateral izquierdo.
  4. Recorta cualquier parte del frente que asome por arriba o por abajo, y limpia el
     color del último píxel del borde derecho.
No se dibuja ni se inventa contenido: todos los píxeles visibles son los de Apple.

uso: python3 extraer_trasera.py composicion.png proporcion_ancho_alto salida.png
"""
import sys
import numpy as np
from PIL import Image


def gauss_blur(img, sigma):
    from PIL import ImageFilter
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(float(sigma)))).astype(float)


def extraer(src, ratio, out=None, verbose=True):
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im).astype(float)
    rgb, a = arr[..., :3], arr[..., 3] / 255.0
    Hh, Ww = a.shape

    cols = np.where(a.max(0) > 0.5)[0]
    ux0, ux1 = cols[0], cols[-1]
    uw = ux1 - ux0
    # filas de la trasera: columnas 10-25 % (dentro de la trasera, lejos del frente)
    band = a[:, int(ux0 + 0.10 * uw):int(ux0 + 0.25 * uw)]
    rows = np.where(band.mean(1) > 0.5)[0]
    yT, yB = rows[0], rows[-1]
    H = yB - yT + 1
    W_est = H * ratio

    # borde izquierdo subpíxel por fila (cobertura por área), sin botones: mediana del tramo recto
    xs = max(0, ux0 - 40)
    K = 140
    def borde_izq(y):
        seg = a[y, xs:xs + K]
        return xs + np.sum(1.0 - seg[: np.argmax(seg > 0.999) + 1]) if (seg > 0.999).any() else np.nan
    recto = np.arange(int(yT + 0.15 * H), int(yB - 0.15 * H))
    b = np.array([borde_izq(y) for y in recto])
    b_med = float(np.nanmedian(b))

    xc_ratio = b_med + W_est / 2

    # Método 1 (preferido): filas de las esquinas donde la trasera asoma sola contra el fondo.
    # En esas filas el centro del tramo opaco es exactamente el eje de simetría.
    def centro_fila(y):
        row = a[y]
        nz = np.where(row > 0.002)[0]
        if len(nz) == 0:
            return np.nan
        l0, r0 = nz[0], nz[-1]
        run = row[l0:r0 + 1]
        if (run < 0.002).any():  # más de un tramo: hay hueco, no sirve
            return np.nan
        full = np.where(run > 0.998)[0]
        if len(full) == 0:
            return np.nan
        fl, fr = l0 + full[0], l0 + full[-1]
        left = fl - row[l0:fl].sum()
        right = fr + 1 + row[fr + 1:r0 + 1].sum()
        return (left + right) / 2
    filas_esq = list(range(yT, int(yT + 0.05 * H))) + list(range(int(yB - 0.05 * H), yB + 1))
    cent = np.array([centro_fila(y) for y in filas_esq])
    ok = np.abs(cent - xc_ratio) < 0.03 * W_est
    metodo = None
    if ok.sum() >= 8:
        vals = cent[ok]
        med = np.median(vals)
        vals = vals[np.abs(vals - med) < 1.5]  # descarta filas contaminadas
        if len(vals) >= 6:
            xc = float(np.mean(vals))
            metodo = f"esquinas ({len(vals)} filas)"

    # Método 2: simetría del logo (pasa-altos). Método 3: proporción del modelo.
    L = rgb @ np.array([0.2126, 0.7152, 0.0722])
    hp = L - gauss_blur(L, max(2, W_est * 0.02))
    y0, y1 = int(yT + 0.30 * H), int(yT + 0.78 * H)
    x0, x1 = int(b_med + 0.22 * W_est), int(b_med + 0.78 * W_est)
    reg = np.abs(hp[y0:y1, x0:x1])
    energia = reg.sum(1)
    umbral = np.percentile(energia, 85)
    filas_logo = np.where(energia >= umbral)[0] + y0
    ly0, ly1 = filas_logo.min(), filas_logo.max() + 1
    patch = hp[ly0:ly1]
    cands = np.arange(b_med + 0.44 * W_est, b_med + 0.56 * W_est, 0.25)
    half = int(0.20 * W_est)
    xx = np.arange(-half, half + 1)
    def costo(c):
        izq = np.array([np.interp(c - xx, np.arange(Ww), patch[r]) for r in range(patch.shape[0])])
        der = np.array([np.interp(c + xx, np.arange(Ww), patch[r]) for r in range(patch.shape[0])])
        return float(np.mean((izq - der) ** 2))
    # Método 2 (principal): el perfil del marco derecho es el espejo del izquierdo.
    # Se correlaciona la derivada horizontal promedio (filas del tramo recto) del marco
    # izquierdo con la del derecho reflejado y se toma el desplazamiento de máxima correlación.
    if metodo is None:
        filas = np.arange(int(yT + 0.25 * H), int(yB - 0.25 * H))
        # mediana por columna: robusta frente a los botones laterales (ocupan pocas filas)
        gx = np.median(np.diff(rgb[filas] @ np.array([0.2126, 0.7152, 0.0722]), axis=1), axis=0)
        k = np.arange(3, int(0.045 * W_est))
        xg = np.arange(len(gx)) + 0.5
        dL = np.interp(b_med + k, xg, gx)
        xR0 = b_med + W_est
        mejor = (-2, None)
        for xr in np.arange(xR0 - 0.03 * W_est, xR0 + 0.015 * W_est, 0.25):
            dR = -np.interp(xr - k, xg, gx)
            c = np.corrcoef(dL, dR)[0, 1]
            if c > mejor[0]:
                mejor = (c, xr)
        if mejor[0] >= 0.5:
            xr = mejor[1]
            metodo = f"perfil del marco (r={mejor[0]:.2f})"
            if mejor[0] < 0.8:
                # correlación moderada: afinar con el salto de luminancia más fuerte
                # (fin del marco -> pieza de atrás) en los 14 px previos al borde estimado
                xs_ = np.arange(int(xr) - 14, int(xr) + 3)
                salto = np.abs(gx[xs_])
                j = int(np.argmax(salto))
                xr = xs_[j] + 0.5 + 0.5  # el borde queda entre la columna j y j+1
                metodo += " + borde por salto de luminancia"
            xc = (b_med + xr) / 2

    if metodo is None:
        cs = np.array([costo(c) for c in cands])
        i = int(np.argmin(cs))
        xc_logo = None
        if 0 < i < len(cs) - 1:  # refinamiento parabólico
            d = cs[i - 1] - 2 * cs[i] + cs[i + 1]
            xc_logo = cands[i] + (0.5 * (cs[i - 1] - cs[i + 1]) / d * 0.25 if d > 0 else 0)
        if xc_logo is not None and abs(xc_logo - xc_ratio) < 0.015 * W_est:
            xc, metodo = float(xc_logo), "logo"
        else:
            xc, metodo = float(xc_ratio), "proporción del modelo"
    xR = 2 * xc - b_med
    W = xR - b_med
    dev = (W - W_est) / W_est

    # alfa izquierda "limpia": tramo recto con borde vertical ideal en b_med
    a_clean = a.copy()
    xgrid = np.arange(Ww, dtype=float)
    cov = np.clip(xgrid + 1 - b_med, 0, 1)
    for y in recto:
        lim = int(b_med) + 3
        a_clean[y, :lim] = cov[:lim]
    # reflejo respecto de xc
    mir_x = 2 * xc - xgrid - 1  # centro de píxel
    mirrored = np.empty_like(a)
    for y in range(Hh):
        mirrored[y] = np.interp(mir_x, xgrid, a_clean[y], left=0, right=0)

    # cobertura vertical de la trasera (columna de referencia dentro de la trasera)
    xref = int(b_med + 0.18 * W)
    V = a[:, xref - 2:xref + 3].mean(1)
    V[: max(0, yT - 3)] = 0
    V[yB + 3:] = 0

    xi = int(np.floor(xc))
    final = np.minimum(a, V[:, None])
    final[:, xi:] = np.minimum(final[:, xi:], mirrored[:, xi:])
    final[:, int(np.ceil(xR)) + 2:] = 0

    # limpieza de color del borde derecho (toma el color 3 px hacia adentro)
    out_rgb = rgb.copy()
    edge = (final > 0) & (final < 0.999)
    edge[:, :xi] = False
    ys, xs_ = np.where(edge)
    out_rgb[ys, xs_] = rgb[ys, np.clip(xs_ - 3, 0, Ww - 1)]

    res = np.dstack([out_rgb, final * 255]).round().clip(0, 255).astype(np.uint8)
    out_im = Image.fromarray(res, "RGBA")
    bb = out_im.getchannel("A").getbbox()
    m = 4
    out_im = out_im.crop((max(0, bb[0] - m), max(0, bb[1] - m), min(Ww, bb[2] + m), min(Hh, bb[3] + m)))
    if verbose:
        print(f"{src.split('/')[-1]}: [{metodo}] yT={yT} yB={yB} borde_izq={b_med:.1f} eje={xc:.2f} "
              f"borde_der={xR:.1f} ancho={W:.1f} (esperado {W_est:.1f}, desvío {dev*100:+.2f}%) "
              f"-> {out_im.size}")
    if out:
        out_im.save(out)
    return out_im, dict(metodo=metodo, eje=xc, ancho=W, ancho_esperado=W_est, desvio=dev, filas_logo=(int(ly0), int(ly1)))


if __name__ == "__main__":
    extraer(sys.argv[1], float(sys.argv[2]), sys.argv[3])
