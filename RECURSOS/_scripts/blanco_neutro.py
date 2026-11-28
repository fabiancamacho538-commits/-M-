"""Blanco neutro para accesorios blancos o de aluminio (cargadores), como en las fotos de la Apple Store:
reduce el croma al 25 % en todos los cuadros para quitar el tinte de la iluminación (cara superior
cálida, laterales azulados) sin cambiar el brillo. No usar en accesorios de color (fundas).

    python3 RECURSOS/_scripts/blanco_neutro.py cuadros_entrada/ cuadros_salida/
"""
import glob, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from traseras_iphones import Y709  # noqa: E402

CROMA = 0.25

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
fs = sorted(glob.glob(os.path.join(src, '*.png')))
for f in fs:
    a = np.asarray(Image.open(f).convert('RGBA')).astype(float) / 255
    s = a[..., :3]; L = (s @ Y709)[..., None]; s = L + (s - L) * CROMA
    Image.fromarray((np.dstack([np.clip(s, 0, 1), a[..., 3]]) * 255).round().astype(np.uint8), 'RGBA').save(
        os.path.join(out, os.path.basename(f)))
print('OK', len(fs), 'cuadros')
