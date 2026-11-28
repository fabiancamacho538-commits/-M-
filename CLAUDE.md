# CLAUDE.md

## Biblioteca permanente de recursos gráficos

`RECURSOS/` guarda los recursos gráficos reutilizables para la edición automatizada de videos.
Antes de buscar o generar una imagen nueva, revisá siempre si ya existe en esta biblioteca.

```
RECURSOS/
├── IPHONES/
│   ├── iPhone_11/
│   │   ├── iPhone_11_trasera.png     # vista TRASERA (la que se usa por defecto)
│   │   └── iPhone_11_frontal.png     # vista frontal con el fondo de pantalla oficial
│   ├── iPhone_16_Pro_Max/            # los modelos con modelo 3D oficial suman la animación:
│   │   ├── iPhone_16_Pro_Max_media_vuelta.mov          # 3D pantalla → trasera, ProRes 4444 con alfa
│   │   ├── iPhone_16_Pro_Max_media_vuelta.webm         # lo mismo en VP9 con alfa (web/Remotion/HyperFrames)
│   │   └── iPhone_16_Pro_Max_media_vuelta_preview.mp4  # vista previa sobre fondo oscuro
│   ├── iPhone_11_Pro/ … iPhone_18_Pro_Max/   # una carpeta por modelo, mismo esquema
│   ├── catalogo.json                 # fuente de verdad: modelo, rutas, resolución, URL, licencia
│   └── _indice_visual.jpg            # hoja de contacto (trasera + frontal de cada modelo)
├── ACCESORIOS/                       # AirPods, cargadores y fundas (ver "Accesorios" más abajo)
│   ├── AirPods_Pro_3/
│   │   ├── AirPods_Pro_3_media_vuelta.mov / .webm / _preview.mp4   # giro 3D, mismo formato que los iPhone
│   │   ├── AirPods_Pro_3_frontal.png / _trasera.png               # primer y último cuadro del giro
│   │   └── AirPods_Pro_3_oficial.png                              # foto oficial de la Apple Store
│   ├── Cargador_20W_USB-C/ · Cargador_MagSafe/ · Funda_Silicona_iPhone_18_Pro_Max_Magenta/
│   ├── catalogo.json
│   └── _indice_visual.jpg
└── _scripts/
    ├── buscar_iphone.py         # detecta modelos de iPhone en un texto y devuelve su PNG
    ├── descargar_iphones.py     # frontales: descarga, verifica (AppleDB + Pillow), optimiza
    ├── traseras_iphones.py      # traseras: recorte de imágenes de la Apple Store o render 3D oficial
    ├── animaciones_iphones.py   # animación 3D media vuelta (pantalla → trasera) con Blender
    ├── anim_media_vuelta.py     # escena de Blender de la media vuelta (la usa el script anterior)
    ├── extraer_trasera.py       # separa la trasera de una composición oficial trasera+frente
    ├── render_trasera_usdz.py   # render de la trasera desde el modelo 3D (USDZ) de Apple con Blender
    ├── accesorios.py            # accesorios: imágenes fijas, foto oficial, catalogo.json e índice
    ├── modelos_accesorios.py    # modelos 3D a medida de los cargadores 20W y MagSafe (Blender)
    └── funda_silicona.py        # funda de silicona construida sobre el modelo 3D oficial del iPhone
```

Todas las imágenes son PNG RGBA con transparencia real, recortadas al contorno del equipo.

## Regla obligatoria: iPhones en ediciones de video

En **toda** edición de video (reels, intros de YouTube, anuncios, motion graphics, subtítulos animados),
cuando el guion, la transcripción, los subtítulos o el pedido mencionen un modelo de iPhone:

1. **Detectar las menciones** con el buscador, que entiende variantes habladas y escritas
   ("iPhone quince Pro Max", "iphone15promax", "el 16 Pro", "el 16e", "iPhone Air"):
   ```bash
   python3 RECURSOS/_scripts/buscar_iphone.py --archivo transcripcion.srt
   python3 RECURSOS/_scripts/buscar_iphone.py "texto del guion"
   python3 RECURSOS/_scripts/buscar_iphone.py --modelo "iPhone 17 Pro"
   python3 RECURSOS/_scripts/buscar_iphone.py --modelo "iPhone 17 Pro" --vista frontal
   ```
   Devuelve, por mención: `modelo`, `disponible`, `vista`, `ruta`, `rutas` (trasera y frontal),
   `resolucion`, `resolucion_limitada`, `alto_maximo_en_video_px`. Con un SRT, usá el tiempo del
   subtítulo donde aparece la mención para sincronizar la entrada del gráfico.
2. **Usar la TRASERA por defecto** (`RECURSOS/IPHONES/<Modelo>/<Modelo>_trasera.png`): es la vista que
   identifica el modelo (cámaras, color, materiales). Usá la frontal sólo si el video habla de la
   pantalla, la Dynamic Island o el contenido en pantalla, o si el usuario lo pide. Si un modelo no
   tiene trasera (`vista_pedida_disponible: false`), el buscador devuelve la frontal: usala y avisá.
3. **Nunca sustituir un modelo por otro.** Si `disponible` es `false` (p. ej. "iPhone 18" base,
   "iPhone 17 Plus"), no uses la imagen de un modelo parecido: resolvé ese momento con tipografía o un
   ícono genérico, y avisale al usuario qué modelo faltó y por qué (campo `motivo`).
4. **Animación 3D de giro:** si la edición pide mostrar el teléfono girando (o una presentación del
   modelo con movimiento), usá `animacion_media_vuelta` del buscador: la `.mov` (ProRes 4444 con alfa)
   para Premiere/Final Cut/DaVinci/After Effects, o la `.webm` (VP9 con alfa) para HTML, Remotion o
   HyperFrames. Dura 1,6 s (48 cuadros a 30 fps, 1080×1920): arranca con la pantalla y termina en la
   trasera. Para que quede quieto al final, congelá el último cuadro; para ir de la trasera a la
   pantalla, reproducila en reversa. Los modelos con el mismo diseño que otro (Pro ↔ Pro Max,
   Plus ↔ base, mini ↔ base) comparten la animación del gemelo: el buscador lo indica con
   `animacion_del_gemelo`, y es la decisión del usuario usarla así. Si el modelo no tiene animación,
   simulá el giro con las dos imágenes (ver "Giro trasera → frontal" más abajo).
5. **No modificar los archivos de la biblioteca.** Trabajá sobre copias en la carpeta del proyecto de video.

### Cómo usar las imágenes en motion graphics

- **Perspectiva:** traseras y frontales son vistas ortogonales (de frente a la cara). Para un look 3/4,
  aplicá la rotación en la animación: `rotateY(18deg)` a `rotateY(25deg)` con `perspective: 1600px`,
  más una sombra suave. No deformes el PNG de forma permanente.
- **Giro trasera → frontal:** para "dar vuelta" el teléfono, animá `rotateY` de 0° a 90° con la trasera,
  cambiá a la frontal en 90° y seguí de 90° a 0° (o usá `backface-visibility: hidden` con las dos caras).
  Ambas vistas de un mismo modelo están en el mismo color.
- **Entrada recomendada:** subida desde abajo + escala 0.92 → 1.0 + opacidad 0 → 1, entre 350 y 500 ms,
  con easing `cubic-bezier(0.22, 1, 0.36, 1)`. Salida más corta (200–300 ms).
- **Integración:** sombra proyectada (blur 40–80 px, opacidad 25–35 %) y, opcionalmente, un resplandor
  del color del equipo. Sobre fondos oscuros, un borde de luz sutil (rim light).
- **Resolución:** no mostrar el equipo más alto que `alto_maximo_en_video_px` (altura nativa + 15 %).
  Las traseras miden entre 2364 y 3966 px de alto (todas sirven a pantalla completa en 1080×1920).
  Frontales con `resolucion_limitada: true`: iPhone 16, 16 Pro, 16e, 17e y Air (~1580–1630 px),
  **17 Pro (1116 px)** y **iPhone 17 (650 px)**: usalas en tamaño medio o chico.
- **Comparativas de tamaño:** alineá los equipos por la base y escalalos según su altura real en mm
  (ficha técnica de Apple), no según la altura en píxeles del PNG: cada imagen tiene su propia escala.
- **ffmpeg (overlay rápido):**
  ```bash
  ffmpeg -i video.mp4 -loop 1 -i RECURSOS/IPHONES/iPhone_15_Pro_Max/iPhone_15_Pro_Max_trasera.png \
    -filter_complex "[1:v]scale=-1:1200,format=rgba,fade=t=in:st=2:d=0.4:alpha=1[ph];\
  [0:v][ph]overlay=(W-w)/2:(H-h)/2+80:enable='between(t,2,6)':shortest=1" -c:a copy salida.mp4
  ```
- **HTML / GSAP / Remotion / HyperFrames:** referenciar el PNG por su ruta relativa y animar con
  `transform`, sin rasterizar de nuevo la imagen.

### Accesorios (AirPods, cargador, funda)

Cuando el guion o el pedido mencionen AirPods, el cargador o la funda, usá `RECURSOS/ACCESORIOS/`
(los alias por accesorio están en `catalogo.json`):

| Mención | Carpeta | Origen del 3D |
|---|---|---|
| AirPods Pro / AirPods | `AirPods_Pro_3` | modelo 3D oficial de Apple (AR Quick Look) |
| cargador, cubo, 20W, USB-C | `Cargador_20W_USB-C` | modelado a medida con las proporciones de las fotos oficiales |
| MagSafe, cargador inalámbrico | `Cargador_MagSafe` | modelado a medida con las proporciones de las fotos oficiales |
| funda, case | `Funda_Silicona_iPhone_18_Pro_Max_Magenta` | funda a medida sobre el iPhone 18 Pro Max oficial |

- Las animaciones `_media_vuelta` tienen el mismo formato que las de los iPhone (1,6 s, 48 cuadros a 30 fps,
  1080×1920, `.mov` ProRes 4444 o `.webm` VP9 con alfa) y se usan igual: congelar el último cuadro o invertir.
- `_frontal.png`/`_trasera.png` son el primer y el último cuadro del giro (render 3D); `_oficial.png` es la
  foto de producto de la Apple Store: usala cuando el plano pida la imagen "de catálogo".
- La funda es Magenta para el 18 Pro Max: no la uses para otro modelo ni otro color. Si piden otra funda,
  generala con `funda_silicona.py` sobre el USDZ de ese modelo (ver el docstring) o avisá que falta.
- Los cargadores y la funda son recreaciones 3D (Apple no publica esos modelos): en anuncios pagos donde el
  accesorio sea protagonista, preferí `_oficial.png` o fotos propias.

### Licencia (leer antes de usar en anuncios)

Todo es material **© Apple Inc.** y **no es de licencia libre**:
- Frontales: renders oficiales tomados del repositorio de AppleDB, sin cambios.
- Traseras de iPhone 11 a 13, 17 Pro y 18 Pro: recortadas de las imágenes oficiales de la Apple Store.
- Traseras de iPhone 14 a 17 y Air y las animaciones de media vuelta: renderizadas desde el modelo 3D
  oficial de Apple (AR Quick Look), con el color calibrado contra la foto oficial.

El uso previsto aceptable es nominativo o editorial (reseñas, comparativas, noticias, tutoriales), sin
sugerir patrocinio de Apple. Si el video es **publicidad paga** con el iPhone como protagonista, avisale
al usuario que revise las *Guidelines for Using Apple Trademarks and Copyrights* o use fotos propias.
No uses imágenes de Apple Newsroom para recortar: su aviso legal prohíbe modificarlas.
El detalle por imagen está en el campo `licencia` de `catalogo.json`.

### Mantener la biblioteca

- Modelo nuevo (p. ej. iPhone 18 base en 2027):
  1. Frontal: agregá una fila a `MODELOS` en `descargar_iphones.py` (identificador de AppleDB y color) y
     corré `python3 RECURSOS/_scripts/descargar_iphones.py`. Sacá el modelo de `NO_DISPONIBLES`.
  2. Trasera: agregá una fila a `TRASERAS` en `traseras_iphones.py`. Usá `"2d"` si en la imagen de la
     Apple Store la trasera está completa delante del frente; si el frente la tapa, `"3d"` con el USDZ
     de AR de apple.com y una imagen de referencia del mismo color. Corré
     `BLENDER_PY=<python con bpy> python3 RECURSOS/_scripts/traseras_iphones.py`
     (bpy: `uv venv -p 3.11 blenv && VIRTUAL_ENV=blenv uv pip install bpy`).
- Ambos scripts verifican el canal alfa con Pillow (si una imagen llega con fondo sólido, se quita con
  `rembg`: `pip install "rembg[cpu]"`), optimizan sin pérdida y regeneran `catalogo.json` y
  `_indice_visual.jpg`. Necesitan acceso de red a `store.storeimages.cdn-apple.com`, `www.apple.com` y
  `raw.githubusercontent.com`.
  3. Animación (si Apple publica el modelo 3D): agregá el modelo en `TRASERAS` como `"3d"` y corré
     `BLENDER_PY=<python con bpy> python3 RECURSOS/_scripts/animaciones_iphones.py --modelos "<Modelo>"`.
- Verificación sin descargar: `--solo-verificar` en los scripts de imágenes; `--solo-catalogo` en el de animaciones.
- Después de agregar un modelo, revisá visualmente `_indice_visual.jpg` antes de dar el trabajo por terminado.
