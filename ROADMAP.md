# IMetVi — Roadmap de Desarrollo

Prioridades derivadas de la encuesta de usuarios (Feb 2026), el análisis de
CUR_Res_CurationTools, y la revisión arquitectónica de agosto 2026.

Cada tarea tiene un estado: ` ` pendiente · `~` en progreso · `x` completada.

---

## Bloque A — Flujo de curaduría (archivistas y RDM)

### A1. Reporte de curaduría dedicado [x]
Exportar una tabla resumen separada de los metadatos disciplinares.
Una fila por archivo; columnas explícitas para cada flag de curaduría.
Compatible con el formato de CUR_Res_CurationTools para integración
en flujos de ingesta (FRDR, Archivematica, DSpace).

- Nuevo botón "Export Curation Report" en la UI
- CSV con columnas: FileName, MD5Checksum, Format, Dimensions,
  CurationFlags, Standard, StandardURL
- Activado sólo si hay archivos cargados (batch o individual)

### A2. Escritura de IPTC/XMP en JPEG [x]
Los archivistas de ciencias sociales y humanidades necesitan escribir
campos IPTC de vuelta al archivo (caption, keywords, rights, credit).
La lectura ya funciona; falta la escritura.

- Extender `utils/metadata_writer.py` con escritura IPTC via `iptcinfo3`
- Extender `utils/metadata_writer.py` con escritura XMP via `python-xmp-toolkit`
  o inyección manual del bloque XMP en el JPEG
- Exponer en el formulario de edición de metadatos (ya existe `open_metadata_editor`)

### A3. Sidecar metadata (`.json` junto al archivo original) [x]
En flujos GIS (QGIS, ArcGIS) y repositorios, el estándar es guardar
un archivo `.json` o `.xml` con el mismo nombre base que la imagen,
en la misma carpeta.

- Botón "Save Sidecar" en la UI
- Genera `<nombre_imagen>.json` en la misma carpeta que el archivo fuente
- Formato: JSON estandarizado (mismos campos que el Export JSON actual)

### A4. Verificación de integridad entre sesiones [x]
El MD5 se calcula en cada sesión pero no se persiste.

- Al exportar un batch, ofrecer guardar `checksums.json` en la misma carpeta
- Botón "Verify Integrity": re-calcula MD5 y compara con `checksums.json`
  si existe; reporta OK / MODIFIED / MISSING por archivo

---

## Bloque B — Nuevos formatos

### B1. LIF — Leica Image File [x]
Formato muy común en microscopios Leica (amplia presencia en USask y
otras instituciones del survey).

- Librería: `readlif` (pip)
- Parser: `metadata_parsers/lif_parser.py`
- Extrae: nombre de serie, dimensiones (X/Y/Z/T/C), tamaño de pixel,
  fecha de adquisición, objetivo, zoom, canal names/LUT
- Standardizer: `standardizers/lif_microscopy_standardizer.py`
  mapeado a campos REMBI
- Registrar extensión `.lif` en FORMAT_REGISTRY

### B2. PNG [x]
El formato más simple de agregar; Pillow ya está instalado.

- Parser: `metadata_parsers/png_parser.py` via `PIL.Image` + `PIL.PngImagePlugin`
- Extrae: dimensiones, modo de color, DPI, chunks de texto (Author, Comment,
  Creation Time, Software), chunks iTXt/zTXt si presentes
- Standardizer: `standardizers/png_general_standardizer.py`
- Extender `utils/metadata_writer.py` con escritura de chunks de texto PNG

### B3. NetCDF con CF Conventions [x]
Datos de teledetección atmosférica, oceanografía y climatología.
El HDF5 parser ya cubre `.nc4` estructuralmente pero no interpreta
convenciones CF.

- Librería: `netCDF4` o `xarray`
- Parser: `metadata_parsers/netcdf_parser.py`
- Extrae: atributo global `Conventions`, `institution`, `title`, `history`;
  variables y sus atributos `units`, `long_name`, `standard_name`;
  dimensiones y coordenadas (lat/lon/time)
- Standardizer con mapeo a ISO 19115 (mismo perfil que GeoTIFF)

---

## Bloque C — Mejoras de UI / UX

### C1. Etiquetas legibles con unidades en panel Recommended [x]
Los perfiles de metadatos existen pero el panel sigue mostrando
claves técnicas crudas (`OME_SizeX`, `XResolution`).

- Agregar diccionario `DISPLAY_LABELS` en cada perfil:
  `{"OME_SizeX": "Image Width", "PixelSizeX": "Pixel Size X (µm)", ...}`
- `render_metadata()` en main.py consulta el perfil activo para
  traducir claves antes de mostrarlas

### C2. Vista en pestañas (Raw / Recommended / Curation) [x]
Actualmente dos paneles lado a lado. Con tres categorías de información
(raw, estandarizado, curaduría) la UI se satura.

- Reemplazar el `QHBoxLayout` de paneles por un `QTabWidget` con tres pestañas:
  "Raw Metadata", "Recommended Fields", "Curation"
- La pestaña Curation muestra: flags, MD5, y advertencias de compresión
  resaltadas en color

### C3. Vista previa de imagen (thumbnail) [x]
Los usuarios necesitan confirmar visualmente que están viendo el archivo correcto.

- Panel adicional (colapsable) con thumbnail via `Pillow` o `QPixmap`
- Soportado para JPG, PNG, TIFF (primera página/frame)
- Para DICOM/FITS/HDF5 mostrar ícono genérico del formato

### C4. Interfaz bilingüe EN/FR [x]
Objetivo explícito del proyecto (institución canadiense).

- Archivo de strings `i18n/strings_en.py` y `i18n/strings_fr.py`
- Selector de idioma en la barra superior (EN | FR)
- Cubrir etiquetas de botones, labels, mensajes de error y diálogos

---

## Bloque D — Integridad y plantillas

### D1. Plantillas de campos esperados [x]
Para curación de ingesta: definir qué campos se *esperan* para un
tipo de archivo y advertir cuando faltan.

- Archivo `metadata_profiles/<formato>_required_fields.py` por formato
- Al cargar un archivo, comparar campos extraídos contra la plantilla
- Mostrar campos faltantes en rojo en el panel Recommended
- Exportar `MissingFields` como columna en el reporte de curaduría (A1)

---

## Orden de ejecución sugerido

| Orden | Tarea | Justificación |
|---|---|---|
| 1 | A1 — Reporte curaduría | Alto impacto, bajo esfuerzo; reutiliza flags ya implementados |
| 2 | B2 — PNG | Muy bajo esfuerzo; Pillow ya instalado |
| 3 | A2 — Escritura IPTC/XMP | Request explícito del survey (archivista Laval) |
| 4 | C2 — Vista pestañas | Mejora inmediata de UX; necesario antes de agregar más paneles |
| 5 | C1 — Etiquetas legibles | Prioridad 7 del survey original |
| 6 | B1 — LIF | Alto impacto en microscopía; requiere `readlif` |
| 7 | A3 — Sidecar JSON | Integración con repositorios |
| 8 | C3 — Thumbnail | UX de confirmación visual |
| 9 | B3 — NetCDF CF | Teledetección; usuarios de QGIS/ArcGIS |
| 10 | A4 — Verificación integridad | Curación a largo plazo |
| 11 | D1 — Plantillas de campos | Ingesta avanzada |
| 12 | C4 — Bilingüe EN/FR | Alcance institucional completo |
