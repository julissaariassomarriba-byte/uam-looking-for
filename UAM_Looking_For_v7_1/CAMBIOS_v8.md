# UAM Looking For v8 · Informe de cambios

Refactorización de la v7.1 **sin modificar la base de datos**: mismo esquema, mismas consultas SQL, mismas rutas,
mismos formularios y mismo comportamiento. Se agregó una sola mejora visible: la zona para arrastrar y soltar la foto.

## 1. Resumen de la auditoría

| # | Hallazgo | Qué se hizo |
|---|---|---|
| C1 | Regla CSS `.entrega-revertida` sin uso desde la v6.2 | Eliminada (lote 1) |
| C2 | Funciones de contraseñas repetidas en `logica.py` y `base_de_datos/reglas_python.py` | **No se cambió.** Al revisarlas no son idénticas: ante un hash mal formado, la de `logica.py` responde «contraseña incorrecta» y la otra lanza un error. Unirlas cambiaría el comportamiento y exigiría tocar `base_de_datos/`, que debe seguir funcionando sola. |
| C3 | Validación de filtros de la URL repetida 4 veces en `app.py` | Una sola función `opcion()` (lote 3) |
| C4 | «Buscar el objeto; si no existe, error» repetido en `logica.py` | **No se cambió**: son 3 casos de 2 líneas; unificarlos obligaba a usar excepciones y complicaba más de lo que ahorraba. |
| C5 | `detalle()` atendía su POST y además lo llamaba `entregar()` (con un truco: `request.endpoint`) | Separado en `detalle()` (ruta) y `mostrar_detalle()` (página) (lote 3) |
| C6 | `migrar()` es larga (51 líneas) | No se toca: es el script de migración |
| C7 | Mensaje «JPG, PNG o WebP» en `imagenes.py` | **Es correcto**: solo aparece si se salta el formulario, y desde el formulario un PNG se convierte solo. No se cambió. |
| S2 | CSRF comparado con `!=` y aceptado sin token si la sesión tampoco tenía | `hmac.compare_digest` y token obligatorio (lote 2) |
| S3 | Cookie sin `Secure` | Opcional con `COOKIE_SEGURA=1` en el `.env` (lote 2) |
| S5 | Redirección `volver`: `/<tab>/otro-sitio.com` redirigía a otro sitio (comprobado en la v7.1) | Solo rutas internas, sin `\`, tabuladores ni saltos de línea (lote 2) |
| S6 | Faltaban cabeceras de seguridad | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` (lote 2) |
| S12 | El ZIP de la v7.1 traía `.env` y `database.db` | Los ZIP de la v8 no los traen; `.gitignore` nuevo (lote 1) |

## 2. Arquitectura

Es la misma; la v8 no agrega capas ni archivos de Python.

```
navegador ──> app.py (rutas, sesión, permisos, CSRF, cabeceras)
                 │
                 ├──> logica.py (reglas) ──> base_datos.py (SQL) ──> SQLite (schema.sql v7.1: CHECK + triggers)
                 ├──> imagenes.py (revisión de fotos)   ├──> reporte_pdf.py (PDF)   └──> migrar.py (v6.2 → v7.1)
                 └──> templates/ + static/ (HTML, CSS y el script de fotos, sin librerías)
```

Dentro de `app.py`: funciones auxiliares nuevas `opcion()` y `ruta_interna()`, `mostrar_detalle()` separada de `detalle()`,
y `cabeceras_seguridad()` (`@app.after_request`).

## 3. Archivos modificados, creados y eliminados

| Archivo | Cambio |
|---|---|
| `app.py` | Lotes 2 y 3 (344 → 379 líneas: crece por la seguridad nueva; la duplicación baja) |
| `templates/macros.html` | Ícono `subir` y macro `zona_foto()` (una sola definición para los dos formularios) |
| `templates/reportar.html` | Usa `zona_foto()` |
| `templates/detalle.html` | Usa `zona_foto()` |
| `templates/foto_script.html` | Arrastrar y soltar; busca la vista previa dentro de la zona |
| `static/css/styles.css` | Estilos de la zona; reglas sin uso eliminadas |
| `README.md` | Versión 8, seguridad, `COOKIE_SEGURA`, cómo subir fotos |
| `.gitignore` | **Nuevo**: `.env`, `database.db`, respaldos y `__pycache__` |
| `CAMBIOS_v8.md` | **Nuevo**: este informe |

No se eliminó ningún archivo. `.env` y `database.db` no van en los ZIP a propósito: los de tu servidor se quedan como están.

## 4. Justificación de cada eliminación

| Eliminado | Por qué es seguro |
|---|---|
| CSS `.entrega-revertida` | Ninguna plantilla, script ni archivo Python la usa (búsqueda en todo el proyecto, incluidas clases armadas en Jinja). |
| CSS `.subir-foto input[type=file]` | Estilaba el campo de archivo visible; ahora el campo está dentro de la zona y se oculta a la vista (sigue accesible con el teclado). |
| `envoltura.__name__ = vista.__name__` | Reemplazado por `@functools.wraps(vista)`, que hace lo mismo (Flask sigue viendo los mismos nombres de ruta: comprobado). |
| `request.endpoint == 'detalle'` y el parámetro `datos_entrega` de `detalle()` | Solo existían para que `entregar()` reutilizara `detalle()`; ahora ambas usan `mostrar_detalle()`. |
| `id="vista-foto"`, `id="info-foto"`, `data-vista`, `data-info` | Solo los usaba `foto_script.html`, que ahora busca esos elementos dentro de su zona. |

## 5. Base de datos: no se modificó

No cambió ningún archivo SQL, el esquema, la base SQLite ni los datos. Huellas SHA-256 idénticas antes y después:

| Archivo | Huella (16 primeros caracteres) |
|---|---|
| `schema.sql` | `20d3ae43af234fd2` |
| `base_datos.py` (todas las consultas) | `382c4aae62262ca2` |
| `migrar.py` | `75facf9a3ac7dddc` |
| `base_de_datos/datos_prueba.sql` | `5cc94190aaded0bc` |
| `base_de_datos/pruebas_negativas.sql` | `644b8aa212d2ce05` |
| `base_de_datos/probar_bd.py` | `673dccf8517b4e60` |
| `base_de_datos/reglas_python.py` | `9e20fa2d6f40ae0b` |

Todas las pruebas usaron bases temporales o en memoria; ninguna abrió una base real.

## 6. Pruebas ejecutadas (resultados reales)

| Prueba | Comando | Resultado |
|---|---|---|
| Batería de la app antes de empezar | `python test_v8.py <v8> <v6.2>` | 98/98 |
| Después del lote 1 | ídem | 98/98 |
| Después del lote 2 (+16 pruebas de seguridad) | ídem | 114/114 |
| Después del lote 3 (+8 de filtros) | ídem | 122/122 |
| Final (+5 de la zona de foto) | ídem | **127/127** |
| La misma batería sobre la v7.1 original | `python test_v8.py <v7.1> <v6.2>` | 117/122 de la batería del lote 3; fallan solo las 5 de seguridad nuevas, lo que demuestra que detectan algo real |
| Navegador real (Chromium + Playwright) | `node e2e.js` | **18/18**: soltar una foto de 2,5 MB la reduce a 78 KB (WebP), se guarda y el servidor la sirve; «Buscar foto»; rechazo de un archivo que no es imagen; soltar fuera de la zona; foco con teclado; celular sin desplazamiento horizontal; sin errores de JavaScript |
| Rutas, métodos y nombres | instantánea antes/después | 21 rutas idénticas |
| Formularios mostrados (acción, método, tipo de envío y campos) | 27 páginas × 3 roles, 6 objetos en todos los estados | 36 formularios idénticos |
| Base de datos (en memoria) | `python base_de_datos/probar_bd.py` | 104/104 (74 negativas) |
| Compilación | `compile()` de los 9 archivos `.py` | Sin errores |

Las pruebas cubren: registro, inicio y cierre de sesión, catálogo y filtros, detalle, recepción de objetos, fotos,
entrega, reclamación posterior a la entrega, resolución, recuperación, devolución, historial y PDF, administración de
usuarios, migración desde la v6.2 (en una copia temporal) y las reglas de la base. Se probó con Python 3.13 (el de
PythonAnywhere) y Flask 3.1.

## 7. Riesgos pendientes y decisiones que requieren tu aprobación

| Tema | Por qué no se hizo |
|---|---|
| Cerrar sesión con POST (hoy es GET) | Cambia una ruta y el botón del menú |
| Límite de intentos de inicio de sesión | Es una regla nueva y necesita guardar intentos (tabla nueva) |
| Verificar el correo institucional al registrarse | Regla nueva; exige enviar correos |
| Content-Security-Policy | Las páginas tienen scripts dentro del HTML; habría que moverlos o permitirlos |
| C2 y C4 | Ver punto 1 |
| `SECRET_KEY` | Si la actual es una frase fácil de adivinar, cámbiala por una al azar (ver README) |
| `.env` o `database.db` en GitHub | El ZIP de la v7.1 los traía, así que probablemente están en el repositorio. Sácalos con el procedimiento del punto 8 (comprobado) y cambia la contraseña del administrador y la `SECRET_KEY` |

## 8. Cómo probar la v8 y cómo aplicarla

**Probar en tu computadora (sin riesgo):** descomprime `UAM_Looking_For_v8.zip`, crea en esa carpeta un `.env` como el
del README, y ejecuta `pip install flask` y `python app.py`. Abre http://127.0.0.1:5000/login. Se crea una base nueva y vacía.

**Probar en PythonAnywhere con una copia de tus datos:**
1. En la pestaña Files sube `UAM_Looking_For_v8.zip` a tu carpeta principal.
2. En el Bash:
   ```bash
   cd ~ && unzip UAM_Looking_For_v8.zip
   cp ~/uam-looking-for/UAM_Looking_For_v7_1/.env ~/UAM_Looking_For_v8/
   cp ~/uam-looking-for/UAM_Looking_For_v7_1/database.db ~/UAM_Looking_For_v8/
   ```
   (Es una **copia**: la base real no se toca.)
3. Pestaña Web: en el archivo WSGI cambia la ruta a `/home/uamlookingfor/UAM_Looking_For_v8`, y en Static files cambia el
   directorio a `/home/uamlookingfor/UAM_Looking_For_v8/static`. Pulsa **Reload**.
4. Revisa la página. Lo que hagas mientras pruebas se guarda solo en la copia.
5. Para volver: deja de nuevo las rutas de `uam-looking-for/UAM_Looking_For_v7_1` y pulsa **Reload**.

**Aplicar la actualización al sitio que ya está subido:**
1. Respaldo, en el Bash: `cp ~/uam-looking-for/UAM_Looking_For_v7_1/database.db ~/respaldo_antes_v8.db`
2. En GitHub, desde la **página principal** del repositorio (no dentro de la carpeta): **Add file → Upload files**, arrastra
   la carpeta `UAM_Looking_For_v7_1` de `UAM_Looking_For_v8_actualizacion.zip` (solo trae los archivos que cambian, en sus
   mismas carpetas) y pulsa **Commit changes**.
3. En el Bash: `cd ~/uam-looking-for && git pull`
4. Pestaña Web: **Reload**. No hay que cambiar el WSGI, las rutas ni el `.env`.

Comprobado en una simulación con git: este `git pull` trae el código nuevo y deja intactos tu `database.db` y tu `.env`,
aunque estén en GitHub, porque la actualización no los incluye.

**Sacar `.env` y `database.db` de GitHub sin perder nada** (hazlo después de aplicar la actualización, que trae el `.gitignore`):
1. Para saber si están en git, en el Bash: `cd ~/uam-looking-for && git ls-files | grep -E "\.env|database\.db"`.
   Si no aparece nada, no hay que hacer nada más.
2. Respaldo: `cp UAM_Looking_For_v7_1/database.db ~/respaldo_bd.db && cp UAM_Looking_For_v7_1/.env ~/respaldo_env`
3. En GitHub, borra los dos archivos (clic en el archivo → ícono de la papelera → **Commit changes**).
4. En el Bash: `git rm --cached UAM_Looking_For_v7_1/database.db UAM_Looking_For_v7_1/.env` y después `git pull`.
   Así git deja de seguirlos, pero los archivos se quedan en el servidor con tus datos reales.
5. **Nunca uses `git stash`, `git checkout .` ni `git reset --hard` en el servidor.** Si `database.db` estuviera en git,
   esos comandos lo volverían a la copia vieja de GitHub.

## 9. Cómo revertir

- **Si probaste la v8 en su propia carpeta:** vuelve a poner las rutas anteriores en la pestaña Web y pulsa Reload.
- **Si ya aplicaste la actualización:** sube a GitHub, igual que la actualización, los mismos archivos pero tomados del ZIP de
  la v7.1 (`app.py`, `README.md`, `static/css/styles.css` y, de `templates/`, `detalle.html`, `foto_script.html`,
  `macros.html` y `reportar.html`); después, en el Bash, `cd ~/uam-looking-for && git pull`, y pulsa Reload.
  `.gitignore` y `CAMBIOS_v8.md` pueden quedarse: no cambian nada del funcionamiento.
- La base no necesita reversión: la v8 no la cambia. Si hiciera falta, el respaldo del paso 1 está en `~/respaldo_antes_v8.db`.

## 10. Cambios que NO se hicieron por requerir tocar la base de datos o el SQL

| Cambio | Qué tocaría |
|---|---|
| Q1: en `contar_objetos_por` y `actualizar_objeto` el nombre de la columna va en el SQL y lo protege un `assert` (con `python -O` desaparece). Hoy no se puede explotar: las columnas vienen del código. | Las consultas de `base_datos.py` |
| Q2: la búsqueda de usuarios no escapa `%` ni `_` en `LIKE` (si alguien escribe `%`, ve todos). Inofensivo. | La consulta de `listar_usuarios` |
| Límite de intentos de inicio de sesión | Una tabla nueva |
| Correo opcional en el registro de estudiantes | El CHECK de `usuarios` |
