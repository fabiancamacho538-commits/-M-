# CLAUDE.md

## Biblioteca permanente de recursos gráficos

`RECURSOS/` guarda los recursos gráficos reutilizables para la edición automatizada de videos.
Antes de buscar o generar una imagen nueva, revisá siempre si ya existe en esta biblioteca.

```
RECURSOS/
├── IPHONES/
│   ├── iPhone_11.png … iPhone_18_Pro_Max.png   # 1 render oficial por modelo, PNG RGBA transparente
│   ├── catalogo.json                           # fuente de verdad: modelo, ruta, resolución, URL, licencia
│   └── _indice_visual.jpg                      # hoja de contacto para ver la biblioteca de un vistazo
└── _scripts/
    ├── descargar_iphones.py   # descarga, verifica (AppleDB + Pillow), optimiza y regenera el catálogo
    └── buscar_iphone.py       # detecta modelos de iPhone en un texto y devuelve su PNG
```

## Regla obligatoria: iPhones en ediciones de video

En **toda** edición de video (reels, intros de YouTube, anuncios, motion graphics, subtítulos animados),
cuando el guion, la transcripción, los subtítulos o el pedido mencionen un modelo de iPhone:

1. **Detectar las menciones** con el buscador, que entiende variantes habladas y escritas
   ("iPhone quince Pro Max", "iphone15promax", "el 16 Pro", "el 16e", "iPhone Air"):
   ```bash
   python3 RECURSOS/_scripts/buscar_iphone.py --archivo transcripcion.srt
   python3 RECURSOS/_scripts/buscar_iphone.py "texto del guion"
   python3 RECURSOS/_scripts/buscar_iphone.py --modelo "iPhone 17 Pro"
   ```
   Devuelve, por mención: `modelo`, `disponible`, `ruta`, `resolucion`, `resolucion_limitada`,
   `alto_maximo_en_video_px`. Con un SRT, usar el tiempo del subtítulo donde aparece la mención para
   sincronizar la entrada del gráfico.
2. **Usar la imagen de `ruta`** (`RECURSOS/IPHONES/<Modelo>.png`) para la animación o el motion graphic,
   sin pedirle confirmación al usuario y sin buscarla de nuevo en internet.
3. **Nunca sustituir un modelo por otro.** Si `disponible` es `false` (p. ej. "iPhone 18" base,
   "iPhone 17 Plus"), no uses la imagen de un modelo parecido: resolvé ese momento con tipografía o un
   ícono genérico, y avisale al usuario qué modelo faltó y por qué (campo `motivo`).
4. **No modificar los archivos de la biblioteca.** Trabajá sobre copias en la carpeta del proyecto de video.

### Cómo usar las imágenes en motion graphics

- **Perspectiva:** los renders son **frontales** (con el fondo de pantalla oficial de lanzamiento de cada
  modelo); el iPhone Duo es la única excepción. Para un look 3/4, aplicá la rotación en la animación:
  `rotateY(-18deg)` a `rotateY(-25deg)` con `perspective: 1600px`, más una sombra suave bajo el equipo.
  No deformes el PNG de forma permanente.
- **Entrada recomendada:** subida desde abajo + escala 0.92 → 1.0 + opacidad 0 → 1, entre 350 y 500 ms,
  con easing `cubic-bezier(0.22, 1, 0.36, 1)`. Salida más corta (200–300 ms).
- **Integración:** sombra proyectada (blur 40–80 px, opacidad 25–35 %) y, opcionalmente, un resplandor del
  color dominante del fondo de pantalla del modelo. Sobre fondos oscuros, un borde de luz sutil (rim light).
- **Resolución:** no mostrar el equipo más alto que `alto_maximo_en_video_px` (altura nativa + 15 %).
  Modelos con `resolucion_limitada: true`: iPhone 16 (1582 px), 16 Pro (1574 px), 16e y 17e (1586 px),
  Air (1626 px), **17 Pro (1116 px)** y **iPhone 17 (650 px)**. En un video vertical 1080×1920, a estos
  últimos dos usalos en composiciones de tamaño medio o chico (comparativas, tarjetas, picture-in-picture),
  nunca a pantalla completa.
- **Comparativas de tamaño:** alineá los equipos por la base y escalalos según su altura real en mm (ficha
  técnica de Apple), no según la altura en píxeles del PNG: cada render está recortado al equipo y tiene
  su propia escala.
- **ffmpeg (overlay rápido):**
  ```bash
  ffmpeg -i video.mp4 -loop 1 -i RECURSOS/IPHONES/iPhone_15_Pro_Max.png \
    -filter_complex "[1:v]scale=-1:1200,format=rgba,fade=t=in:st=2:d=0.4:alpha=1[ph];\
  [0:v][ph]overlay=(W-w)/2:(H-h)/2+80:enable='between(t,2,6)':shortest=1" -c:a copy salida.mp4
  ```
- **HTML / GSAP / Remotion / HyperFrames:** referenciar el PNG por su ruta relativa y animar con
  `transform`, sin rasterizar de nuevo la imagen.

### Licencia (leer antes de usar en anuncios)

Las imágenes son renders oficiales de producto **© Apple Inc.**, tomados del repositorio público de
AppleDB (`littlebyteorg/apple-device-images`). **No son de licencia libre.** El uso previsto aceptable es
nominativo o editorial: identificar el modelo en reseñas, comparativas, noticias y tutoriales, sin alterar
el producto y sin sugerir patrocinio de Apple. Si el video es **publicidad paga** con el iPhone como
protagonista, avisale al usuario que revise las *Guidelines for Using Apple Trademarks and Copyrights*.
El detalle por imagen está en el campo `licencia` de `catalogo.json`.

### Mantener la biblioteca

- Modelo nuevo (p. ej. iPhone 18 base en 2027): agregá una fila a `MODELOS` en
  `RECURSOS/_scripts/descargar_iphones.py`, con el identificador de AppleDB y un color que exista en el
  repositorio de imágenes, y corré `python3 RECURSOS/_scripts/descargar_iphones.py`. El script verifica el
  nombre contra AppleDB, comprueba el canal alfa con Pillow (si una imagen llega con fondo sólido, lo quita
  con `rembg`; instalalo con `pip install "rembg[cpu]"`), recorta márgenes, optimiza sin pérdida y regenera
  `catalogo.json` y `_indice_visual.jpg`. Sacá el modelo de `NO_DISPONIBLES`.
- Verificación sin descargar: `python3 RECURSOS/_scripts/descargar_iphones.py --solo-verificar`.
- Después de agregar un modelo, revisá visualmente `_indice_visual.jpg` antes de dar el trabajo por terminado.
