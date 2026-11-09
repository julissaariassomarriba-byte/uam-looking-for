# UAM Looking For v9 · Reestructuración, validación de identidad y fin de la renuncia

La v9 parte de la v8.5 (la que está publicada) y conserva todo lo que hace. Sigue usando solo Flask, SQLite, HTML y CSS.

## 1. Código reorganizado por capas

Antes había seis archivos grandes en la raíz (`app.py` con 470 líneas de rutas, `logica.py` con 560 líneas de reglas,
`base_datos.py`…). Ahora todo vive en el paquete `uam/`, separado por responsabilidad:

| Capa | Carpeta | Qué hace | Qué no hace |
|---|---|---|---|
| Rutas | `uam/rutas/` (5 blueprints) | Lee la petición, llama a un servicio, muestra la página | No valida ni toca SQL |
| Servicios | `uam/servicios/` | Reglas y validaciones; devuelven `(True, resultado)` o `(False, mensaje)` | No conocen Flask (se prueban sin servidor) |
| Datos | `uam/datos/` | Una función por consulta, siempre con parámetros | No deciden reglas |
| Base | `schema.sql` | CHECK y triggers vuelven a revisar todo | — |

Otras mejoras:
- **Fábrica `crear_app()`**: la app recibe la ruta del `.env` y de la base, así las pruebas usan archivos temporales y
  nunca la base real. `app.py` quedó en 10 líneas y el WSGI de PythonAnywhere **no cambia**.
- **Conexiones que se cierran**: antes cada consulta abría una conexión a SQLite y no la cerraba.
- **Plantillas por sección** (`templates/acceso`, `objetos`, `reclamaciones`, `visitantes`, `admin`, `parciales`).
- Validaciones comunes en un solo lugar (`uam/validacion.py`) y criptografía en `uam/seguridad.py`.
- Nombres de rutas con su sección (`objetos.detalle`, `visitantes.panel`…). **Las direcciones (URL) no cambiaron.**
- Pruebas dentro del proyecto: `python tests/probar_app.py`.

## 2. Validación cruzada de identidad (el problema del CIF de otra persona)

**Antes:** si el encargado escribía un CIF que ya existía, el sistema usaba la fila de esa persona **aunque el nombre
escrito fuera otro**. En una persona sin cuenta, además, le **cambiaba el nombre** por el escrito. Resultado: el objeto o
la entrega quedaba a nombre de otra persona, y su registro quedaba alterado.

**Ahora** (`uam/servicios/personas.py`), al recibir un objeto, registrar una entrega, crear una cuenta en el panel o
registrarse como estudiante:

| Caso | v8.5 | v9 |
|---|---|---|
| CIF registrado + nombre de otra persona | Se guardaba a nombre del dueño del CIF (y se le cambiaba el nombre si no tenía cuenta) | Se rechaza: «El CIF … ya está registrado a nombre de …» |
| CIF registrado + su nombre (con o sin tildes, en otro orden, o parte de él) | Se aceptaba | Se acepta |
| CIF registrado + nombre vacío (solo «Recibir objeto») | Se usaba el registrado | Igual |
| CIF de un estudiante con cuenta anotado como docente o visitante | Se aceptaba | Se rechaza |
| Correo que ya es de otra persona | Se borraba en silencio | Se rechaza con el motivo |
| Registro de estudiante con el CIF de alguien de ventanilla con otro nombre | Se creaba la cuenta sobre su fila | Se rechaza |
| Admin cambia el CIF de una cuenta por el de otra | Error genérico | Mensaje claro |

Nunca se sobrescriben los datos de una persona registrada: solo se completa el teléfono o el correo que faltaba.

## 3. Validaciones que faltaban en el servidor

- CIF: solo letras y números (de 4 a 20), sin importar guiones ni espacios.
- Correo con formato válido en todas las cuentas (antes bastaba con que tuviera «@»).
- Teléfono con al menos 8 dígitos también en «Recibir objeto» y en la reclamación (antes no se revisaba).
- Fechas y horas reales (antes «2026-02-30» o «25:99» llegaban hasta la base).
- Categoría y estado inicial de la lista (antes una categoría inventada pasaba en silencio a «Otros»).
- Largo máximo de cada texto, también en el formulario (`maxlength`).
- Nombre completo de al menos 3 letras en las cuentas creadas por el administrador (igual que en el registro).
- La búsqueda de cuentas ya no trata `%` y `_` como comodines.
- Una contraseña de más de 128 caracteres se rechaza.

## 4. Se eliminó la renuncia a una reclamación

Se interpretó «la renuncia» como **«Cancelar reclamación»**, el botón con el que el estudiante retiraba su propia
solicitud.
- Se quitó el botón, la ruta `/mis-reclamaciones/<id>/cancelar` y su lógica. Ahora una reclamación solo la resuelve
  el personal (aceptar o rechazar).
- La base también lo impide, con el trigger nuevo `trg_reclamacion_sin_cancelar`.
- Las reclamaciones que ya estaban canceladas **no se borran ni se cambian**. El personal las ve en la pestaña
  «Canceladas (antes de v9)», que solo aparece si existe alguna.

## 5. Otros cambios de seguridad

- «Cerrar sesión» ahora es un formulario POST con token CSRF. Antes era un enlace, y cualquier página podía cerrarte
  la sesión.
- Las páginas de error ya no muestran textos de Flask en inglés.

## 6. Base de datos

El único cambio es que se **agrega** el trigger `trg_reclamacion_sin_cancelar`. El esquema queda en 7 tablas,
15 llaves foráneas, 12 índices y 26 triggers.

Al iniciar, una base v8.5 con datos se actualiza sola y el contenido de todas sus tablas sigue idéntico. Está
comprobado con una base creada por la propia v8.5, que incluía una reclamación cancelada.

## 7. Pruebas ejecutadas

| Prueba | Resultado |
|---|---|
| `tests/probar_app.py` + migración desde v6.2 y actualización desde v8.5 | **241/241** |
| `tests/probar_app.py` sin argumentos (lo que corre cualquiera) | **220/220** |
| `base_de_datos/probar_bd.py` | **135/135** (97 negativas) |
| Navegador real (Chromium): flujo de visitantes completo | **18/18** |
| Navegador real: aviso de CIF ajeno en «Recibir objeto» y «Cerrar sesión» por POST, en computadora y celular | **5/5** |

Las 32 pruebas nuevas de la v9 cubren cada caso de la tabla del punto 2, las validaciones del punto 3, la renuncia
eliminada (por la app y directo en la base) y el cierre de sesión.

## 8. Decisiones pendientes (no se inventaron reglas)

| Tema | Por qué queda pendiente |
|---|---|
| **Cuánto debe parecerse el nombre** | Se eligió: todas las palabras escritas deben estar en el nombre registrado, y al menos dos. Si la UAM prefiere exigir el nombre completo idéntico, es un cambio de una línea en `uam/validacion.py` (`mismo_nombre`). |
| **Un CIF que nadie ha usado todavía** | La validación compara con lo que ya está en la base. Si alguien se registra con un CIF ajeno que nunca pasó por ventanilla, el sistema no tiene con qué compararlo. Para cerrarlo hace falta una lista oficial de CIF de la UAM o verificar el correo institucional. |
| Límite de intentos de inicio de sesión | Hay que decidir cuántos intentos y por cuánto tiempo se bloquea. |
| Límite o captcha en el formulario de visitantes | Sigue igual que en la v8.5. |
| Conservación de los datos de visitantes | Sigue igual que en la v8.5. |
