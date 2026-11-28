"""Calibración de color de la animación de la funda, por zonas:
  - silicona (píxeles magenta saturados): ganancia exacta contra el dorso liso de la foto oficial, en todos los cuadros;
  - pantalla: ganancia contra el frontal oficial del iPhone, en los cuadros de frente;
  - meseta de cámaras (tonos rojizos oscuros): ganancia contra la meseta de la foto oficial, en los cuadros de atrás.
Uso: python3 RECURSOS/_scripts/funda_post.py cuadros/ foto_oficial_funda.png ancho/alto salida/ frontal_oficial_iphone.png
(la foto oficial de la funda vista de atrás, p. ej. MK904; el frontal oficial del iPhone de la biblioteca)"""
import sys, glob, os, numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traseras_iphones import s2l, l2s, Y709
src, ref_p, ratio, out, fr_p = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
fs = sorted(glob.glob(src + '/*.png')); N = len(fs) - 1
def rgba(p): return np.asarray(Image.open(p).convert('RGBA')).astype(float) / 255
def parche_pantalla(a):
    al = a[..., 3]; cols = np.where(al.max(0) > 0.5)[0]; rows = np.where(al.max(1) > 0.5)[0]
    x0, x1, y0, y1 = cols[0], cols[-1], rows[0], rows[-1]; W = x1 - x0; H = y1 - y0
    p = a[int(y0 + .25 * H):int(y0 + .75 * H), int(x0 + .25 * W):int(x0 + .75 * W)]
    m = p[..., 3] > .98; return s2l(p[..., :3][m]).mean(0)
def ganancias(cr, cn, lim):
    g = cr / cn; lum = (cr @ Y709) / (cn @ Y709)
    return np.clip(g / (g @ Y709), *lim) * np.clip(lum, 0.6, 1.6)
ref = rgba(ref_p); last = rgba(fs[-1])
def parche_silicona(a):  # dorso liso, debajo del logo: 66-80 % de la altura, 30-70 % del ancho
    al = a[..., 3] > .98; rows = np.where(al.any(1))[0]; cols = np.where(al.any(0))[0]
    H = rows[-1] - rows[0]; W = cols[-1] - cols[0]
    p = a[rows[0] + int(.66 * H):rows[0] + int(.80 * H), cols[0] + int(.3 * W):cols[0] + int(.7 * W)]
    m = p[..., 3] > .98; return s2l(p[..., :3][m]).mean(0)
cr = parche_silicona(ref); cn = parche_silicona(last)
g_sil = np.clip(cr / cn, 0.3, 3.0)  # exacta: el parche liso queda igual a la foto oficial
g_fr = ganancias(parche_pantalla(rgba(fr_p)), parche_pantalla(rgba(fs[0])), (0.85, 1.18))
def parche_meseta(a):  # meseta de cámaras lisa, debajo del lente grande (23,5-27 % alto, 55-72 % ancho)
    al = a[..., 3] > .98; rows = np.where(al.any(1))[0]; cols = np.where(al.any(0))[0]
    H = rows[-1] - rows[0]; W = cols[-1] - cols[0]
    p = a[rows[0] + int(.235 * H):rows[0] + int(.27 * H), cols[0] + int(.55 * W):cols[0] + int(.72 * W)]
    return s2l(p[..., :3].reshape(-1, 3)).mean(0)
g_tr = np.clip(parche_meseta(ref) / parche_meseta(last), 0.3, 3.0)  # equipo visto por el recorte
print('silicona', g_sil.round(3), 'pantalla', g_fr.round(3), 'meseta', g_tr.round(3))
os.makedirs(out, exist_ok=True)
for i, f in enumerate(fs):
    t = np.clip((i / N - 0.35) / 0.30, 0, 1); w = t * t * (3 - 2 * t)
    a = rgba(f); rgb = a[..., :3]
    oscuro = np.clip((0.55 - rgb @ Y709) / 0.2, 0, 1)                # el flash y los brillos no se tiñen
    rojizo = np.clip((rgb[..., 0] / np.maximum(rgb[..., 1], 1e-3) - 1.15) / 0.15, 0, 1)  # meseta sí, vidrio de lentes no
    oscuro = (oscuro * rojizo)[..., None]
    g_mix = np.exp((1 - w) * np.log(g_fr) + w * oscuro * np.log(g_tr))
    mx, mn = rgb.max(-1), rgb.min(-1); sat = (mx - mn) / np.maximum(mx, 1e-4)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    tono = (r > g * 1.45) & (b > g * 1.35)                      # magenta: R y B altos, G bajo
    m = np.clip((sat - 0.36) / 0.12, 0, 1) * tono * np.clip((mx - 0.12) / 0.1, 0, 1)
    m = m[..., None]
    G = np.exp(m * np.log(g_sil) + (1 - m) * np.log(g_mix))
    o = l2s(np.clip(s2l(rgb) * G, 0, 1))
    Image.fromarray((np.dstack([o, a[..., 3]]) * 255).round().clip(0, 255).astype(np.uint8), 'RGBA').save(os.path.join(out, os.path.basename(f)))
print('OK', len(fs))
