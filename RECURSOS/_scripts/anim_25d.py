#!/usr/bin/env python3
"""
Media vuelta "2.5D" para modelos sin modelo 3D oficial publicado (p. ej. iPhone 11 Pro Max):
proyecta la imagen FRONTAL y la TRASERA oficiales sobre un plano 3D que gira 180° con perspectiva
real (cámara equivalente a 85 mm, igual que las animaciones 3D), con el canto del equipo como cara
lateral del color del marco. Misma duración, tamaño y curva de giro que las animaciones 3D.

uso: python3 anim_25d.py frontal.png trasera.png alto_mm grosor_mm salida_dir [cuadros=48 ancho=1080 alto=1920]
"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

front_p, back_p, H_MM, T_MM, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
NF = int(sys.argv[6]) if len(sys.argv) > 6 else 48
CW = int(sys.argv[7]) if len(sys.argv) > 7 else 1080
CH = int(sys.argv[8]) if len(sys.argv) > 8 else 1920
os.makedirs(out, exist_ok=True)
SS = 2  # supermuestreo para bordes suaves

front = Image.open(front_p).convert("RGBA")
back = Image.open(back_p).convert("RGBA")
W_MM = H_MM * front.width / front.height
# cámara: lente 85 mm, sensor vertical 24 mm; el equipo ocupa el 78 % de la altura (como en 3D)
f_mm, sensor_h = 85.0, 24.0
vfov = 2 * np.arctan(sensor_h / (2 * f_mm))
D = (H_MM / 0.78) / (2 * np.tan(vfov / 2))
px_per_mm_at_D = (CH * SS) / (2 * D * np.tan(vfov / 2))
cx, cy = CW * SS / 2, CH * SS / 2


def proyectar(P):
    """P: (n,3) en mm, cámara en z=+D mirando a -z. Devuelve (n,2) en px."""
    z = D - P[:, 2]
    s = (D / z) * px_per_mm_at_D
    return np.stack([cx + P[:, 0] * s, cy - P[:, 1] * s], 1)


def coef_perspectiva(dst, w, h):
    """Coeficientes de PIL (salida -> entrada) para mapear el rectángulo (0,0,w,h) sobre el cuadrilátero dst."""
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()


def color_marco(img):
    a = np.asarray(img).astype(float)
    m = a[..., 3] > 250
    cols = np.where(m.any(0))[0]
    x0 = cols[0]
    tira = a[int(a.shape[0] * 0.3):int(a.shape[0] * 0.7), x0 + 4:x0 + max(12, int(0.02 * a.shape[1]))]
    return tuple(int(v) for v in tira[..., :3].reshape(-1, 3).mean(0))


marco = color_marco(back)


def ease(t):  # curva similar a la Bezier "auto" de Blender
    return t * t * (3 - 2 * t)


def cuadro(i):
    th = np.pi * ease(i / NF)  # 0 = pantalla, pi = trasera
    canvas = Image.new("RGBA", (CW * SS, CH * SS), (0, 0, 0, 0))
    w2, h2, t2 = W_MM / 2, H_MM / 2, T_MM / 2
    c, s = np.cos(th), np.sin(th)

    def rot(x, z):  # giro alrededor del eje vertical
        return x * c + z * s, -x * s + z * c

    # cara visible: frontal mientras cos > 0, si no la trasera (vista desde atrás, espejada)
    if c >= 0:
        img, zc = front, t2
        xs = [-w2, w2]
    else:
        img, zc = back, -t2
        xs = [w2, -w2]  # al ver la trasera, la izquierda de la imagen es +x del equipo
    pts = []
    for (x, y) in [(xs[0], h2), (xs[1], h2), (xs[1], -h2), (xs[0], -h2)]:
        xr, zr = rot(x, zc)
        pts.append((xr, y, zr))
    quad = proyectar(np.array(pts))
    # canto lateral: el lado que mira a la cámara
    lado = -w2 if s > 0 else w2  # la cara lateral cuya normal mira a la cámara
    r_esq = 0.115 * W_MM  # el canto recto termina donde empieza el radio de las esquinas
    e = []
    for (zz, y) in [(t2, h2 - r_esq), (-t2, h2 - r_esq), (-t2, -h2 + r_esq), (t2, -h2 + r_esq)]:
        xr, zr = rot(lado, zz)
        e.append((xr, y, zr))
    equad = proyectar(np.array(e))
    d = ImageDraw.Draw(canvas)
    luz = (0.75 + 0.55 * abs(s))
    if abs(s) > 0.06:
        d.polygon([tuple(p) for p in equad], fill=tuple(min(255, int(v * luz)) for v in marco) + (255,))
    if abs(c) > 0.02:
        coef = coef_perspectiva([tuple(p) for p in quad], img.width, img.height)
        cara = img.transform(canvas.size, Image.PERSPECTIVE, coef, Image.BICUBIC)
        # sombreado suave según el ángulo + reflejo que barre el vidrio
        arr = np.asarray(cara).astype(float)
        sombra = 0.80 + 0.20 * abs(c)
        arr[..., :3] *= sombra
        xs_ = np.arange(arr.shape[1])[None, :]
        centro = cx + (quad[:, 0].mean() - cx) + (0.5 - i / NF) * (quad[:, 0].max() - quad[:, 0].min()) * 1.6
        brillo = np.exp(-((xs_ - centro) / (0.18 * (quad[:, 0].max() - quad[:, 0].min() + 1))) ** 2) * 0.18 * (1 - abs(c) ** 4)
        arr[..., :3] = arr[..., :3] + (255 - arr[..., :3]) * brillo[..., None]
        cara = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
        canvas.alpha_composite(cara)
    return canvas.resize((CW, CH), Image.LANCZOS)


for i in range(NF + 1):
    cuadro(i).save(os.path.join(out, f"{i:04d}.png"))
print("OK", out, NF + 1)
