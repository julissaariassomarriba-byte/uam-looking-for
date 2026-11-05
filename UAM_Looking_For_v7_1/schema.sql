-- =====================================================================
-- UAM Looking For v7.1 · Modelo de base de datos (SQLite 3.25 o superior)
-- 6 tablas · 13 llaves foráneas · 1 vista · normalizado hasta 3FN
-- Se puede ejecutar desde cero y más de una vez: IF NOT EXISTS no borra datos.
--
-- Dónde vive cada regla:
--   CHECK     -> lo que depende de una sola fila (formatos, fechas, coherencia entre columnas).
--   UNIQUE    -> «no puede haber dos» (también índices únicos parciales).
--   Triggers  -> lo que mira otra tabla: roles de quien actúa, estado del objeto, fechas entre tablas,
--                hechos pasados que no cambian, y el historial que se escribe solo.
--   Python    -> lo que depende de QUIÉN ESTÁ CONECTADO (la base no sabe quién inició sesión) y el hash
--                de las contraseñas (ver reglas_python.py).
-- =====================================================================

PRAGMA foreign_keys = ON;   -- también se activa en cada conexión desde Python: SQLite lo apaga por defecto
PRAGMA page_size = 8192;    -- páginas de 8 KB: leen mejor las fotos (solo tiene efecto en una base nueva)

-- ---------------------------------------------------------------------
-- usuarios: todas las personas, una fila por persona.
--   Personal (puede operar): Administrador y Encargado, activos.
--   Con cuenta: contrasena_hash lleno (cualquier rol menos Visitante). El Administrador puede no tener
--   hash: su clave está en el .env.  Sin cuenta: quien solo trae o retira un objeto en ventanilla.
--   cif y correo: COLLATE NOCASE, así 'Ana@uam' y 'ana@UAM' cuentan como el mismo correo.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL CHECK (trim(nombre) <> ''),
    cif             TEXT    UNIQUE COLLATE NOCASE CHECK (cif IS NULL OR (cif = trim(cif) AND cif <> '')),
    correo          TEXT    UNIQUE COLLATE NOCASE CHECK (correo IS NULL OR (correo = trim(correo) AND correo LIKE '_%@_%._%')),
    telefono        TEXT    CHECK (telefono IS NULL OR trim(telefono) <> ''),
    carrera         TEXT    CHECK (carrera IS NULL OR trim(carrera) <> ''),
    rol             TEXT    NOT NULL CHECK (rol IN ('Administrador', 'Encargado', 'Estudiante',
                                                    'Docente', 'Administrativo', 'Visitante')),
    -- Hash auto-descriptivo («algoritmo$parámetros$sal$hash»: pbkdf2, bcrypt, argon2…). No se fija un formato:
    -- solo se rechaza lo que claramente no es un hash. Python calcula y verifica el hash.
    contrasena_hash TEXT    CHECK (contrasena_hash IS NULL OR (length(contrasena_hash) >= 40
                                   AND instr(contrasena_hash, '$') > 0 AND instr(contrasena_hash, ' ') = 0)),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    CHECK (rol <> 'Visitante' OR contrasena_hash IS NULL),                            -- un visitante no inicia sesión
    CHECK (contrasena_hash IS NULL OR (cif IS NOT NULL AND correo IS NOT NULL))       -- toda cuenta tiene CIF y correo
);

-- ---------------------------------------------------------------------
-- objetos: cada objeto encontrado y su estado ACTUAL.
--   Bajo custodia: Activo / En resguardo / En bodega (los cambia el personal a mano).
--   Después, el estado lo pone la base según los hechos: Entregado -> Por recuperar -> Recuperado -> Devuelto.
--   registrado_por = encargado que lo registró (no cambia). reportado_por = quien lo trajo (vacío si lo
--   encontró el personal; no puede ser el mismo que lo registró).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS objetos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo              TEXT    NOT NULL CHECK (trim(titulo) <> ''),
    descripcion         TEXT    NOT NULL CHECK (trim(descripcion) <> ''),
    descripcion_publica TEXT    CHECK (descripcion_publica IS NULL OR trim(descripcion_publica) <> ''),
    categoria           TEXT    NOT NULL CHECK (categoria IN ('Electrónicos', 'Documentos/Carné', 'Ropa/Accesorios',
                                                              'Llaves', 'Útiles/Libros', 'Otros')),
    lugar_encontrado    TEXT    NOT NULL CHECK (trim(lugar_encontrado) <> ''),
    ubicacion           TEXT    NOT NULL CHECK (ubicacion IN ('Vida Estudiantil', 'Sala Docente', 'Edificio A')),
    fecha               TEXT    NOT NULL CHECK (date(fecha) IS fecha),                           -- AAAA-MM-DD válida
    hora                TEXT    CHECK (hora IS NULL OR strftime('%H:%M', hora) IS hora),         -- HH:MM válida
    estado              TEXT    NOT NULL DEFAULT 'Activo'
                                CHECK (estado IN ('Activo', 'En resguardo', 'En bodega', 'Entregado',
                                                  'Por recuperar', 'Recuperado', 'Devuelto')),
    registrado_por      INTEGER NOT NULL REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    reportado_por       INTEGER          REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    foto_publica        INTEGER NOT NULL DEFAULT 0 CHECK (foto_publica IN (0, 1)),
    foto                BLOB    CHECK (foto IS NULL OR (length(foto) <= 307200 AND
                                       (substr(foto, 1, 3) = X'FFD8FF' OR                                 -- JPEG
                                        (substr(foto, 1, 4) = X'52494646' AND substr(foto, 9, 4) = X'57454250')))),  -- WebP
    CHECK (foto IS NOT NULL OR foto_publica = 0),                                                 -- no se publica una foto que no existe
    CHECK (reportado_por IS NULL OR reportado_por <> registrado_por)                              -- si lo encontró el personal, va vacío
);

-- ---------------------------------------------------------------------
-- entregas: la ENTREGA INICIAL de un objeto (una sola por objeto). No se modifica ni se borra.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entregas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    objeto_id     INTEGER NOT NULL UNIQUE REFERENCES objetos (id)  ON UPDATE RESTRICT ON DELETE RESTRICT,
    retirado_por  INTEGER NOT NULL        REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    entregado_por INTEGER NOT NULL        REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    senas         TEXT    NOT NULL CHECK (trim(senas) <> ''),
    fecha_entrega TEXT    NOT NULL CHECK (datetime(fecha_entrega) IS fecha_entrega)          -- AAAA-MM-DD HH:MM:SS
);

-- ---------------------------------------------------------------------
-- reclamaciones: el verdadero dueño reclama un objeto que ya se entregó a otra persona.
--   Una entrega puede recibir varias (1 : 0..N); solo una puede ser aceptada.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reclamaciones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    entrega_id       INTEGER NOT NULL REFERENCES entregas (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    usuario_id       INTEGER NOT NULL REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    descripcion      TEXT    NOT NULL CHECK (trim(descripcion) <> ''),
    lugar_perdida    TEXT    CHECK (lugar_perdida IS NULL OR trim(lugar_perdida) <> ''),
    fecha_perdida    TEXT    CHECK (fecha_perdida IS NULL OR date(fecha_perdida) IS fecha_perdida),
    estado           TEXT    NOT NULL DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Aceptada', 'Rechazada', 'Cancelada')),
    respuesta        TEXT    CHECK (respuesta IS NULL OR trim(respuesta) <> ''),
    fecha_solicitud  TEXT    NOT NULL CHECK (datetime(fecha_solicitud) IS fecha_solicitud),
    fecha_resolucion TEXT    CHECK (fecha_resolucion IS NULL OR datetime(fecha_resolucion) IS fecha_resolucion),
    resuelto_por     INTEGER REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    -- Pendiente: sin resolver. Aceptada/Rechazada: la resolvió el personal. Cancelada: la cerró el propio dueño.
    CHECK (estado <> 'Pendiente' OR (fecha_resolucion IS NULL AND resuelto_por IS NULL)),
    CHECK (estado NOT IN ('Aceptada', 'Rechazada') OR (fecha_resolucion IS NOT NULL AND resuelto_por IS NOT NULL)),
    CHECK (estado <> 'Cancelada' OR (fecha_resolucion IS NOT NULL AND resuelto_por IS NULL)),
    CHECK (estado <> 'Rechazada' OR respuesta IS NOT NULL),                                     -- un rechazo lleva motivo
    CHECK (fecha_resolucion IS NULL OR fecha_resolucion >= fecha_solicitud),
    CHECK (fecha_perdida IS NULL OR fecha_perdida <= date(fecha_solicitud))                     -- se perdió antes de reclamar
);

-- ---------------------------------------------------------------------
-- devoluciones: la recuperación FÍSICA tras aceptar una reclamación (como máximo una por reclamación).
--   Momento 1 (al crearla): el personal recibe el objeto de quien lo tenía       -> objeto «Recuperado».
--   Momento 2 (se completa una vez): el personal se lo devuelve a su dueño       -> objeto «Devuelto».
--   No repite el dueño, el objeto ni la entrega: se llega a ellos por reclamacion_id (ver vista_devoluciones).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devoluciones (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reclamacion_id   INTEGER NOT NULL UNIQUE REFERENCES reclamaciones (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    recibido_por     INTEGER NOT NULL        REFERENCES usuarios (id)      ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_recepcion  TEXT    NOT NULL CHECK (datetime(fecha_recepcion) IS fecha_recepcion),
    devuelto_por     INTEGER                 REFERENCES usuarios (id)      ON UPDATE RESTRICT ON DELETE RESTRICT,
    fecha_devolucion TEXT    CHECK (fecha_devolucion IS NULL OR datetime(fecha_devolucion) IS fecha_devolucion),
    observaciones    TEXT    CHECK (observaciones IS NULL OR trim(observaciones) <> ''),
    CHECK ((devuelto_por IS NULL) = (fecha_devolucion IS NULL)),          -- el momento 2 se registra completo o no se registra
    CHECK (fecha_devolucion IS NULL OR fecha_devolucion >= fecha_recepcion)
);

-- ---------------------------------------------------------------------
-- historial: bitácora de cada objeto. Solo se agregan filas.
--   objetos.estado = cómo está AHORA; historial = cómo llegó ahí (qué, quién, cuándo).
--   Las acciones que nacen de otra tabla (Registro, Entrega, Reclamación…, Recuperación, Devolución) las
--   escriben los triggers con el autor y la fecha del propio hecho: la app no puede olvidarlas ni duplicarlas.
--   Las demás (Cambio de estado, Cambio de ubicación, Foto, Descripción pública) las escribe Python.
--   El estado anterior no se guarda: es el estado_nuevo de la fila previa (LAG, ver la consulta al final).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    objeto_id    INTEGER NOT NULL REFERENCES objetos (id)  ON UPDATE RESTRICT ON DELETE RESTRICT,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios (id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    accion       TEXT    NOT NULL CHECK (accion IN ('Registro', 'Cambio de estado', 'Descripción pública', 'Cambio de ubicación',
                                                    'Foto', 'Entrega', 'Reclamación', 'Reclamación aceptada',
                                                    'Reclamación rechazada', 'Reclamación cancelada',
                                                    'Recuperación', 'Devolución')),
    estado_nuevo TEXT,
    fecha_hora   TEXT    NOT NULL CHECK (datetime(fecha_hora) IS fecha_hora),
    -- cada acción solo puede dejar el objeto en el estado que le corresponde (IS y IS NOT NULL: un NULL no debe pasar)
    CHECK (CASE accion
             WHEN 'Registro'             THEN estado_nuevo IS NOT NULL AND estado_nuevo IN ('Activo', 'En resguardo', 'En bodega')
             WHEN 'Cambio de estado'     THEN estado_nuevo IS NOT NULL AND estado_nuevo IN ('Activo', 'En resguardo', 'En bodega')
             WHEN 'Entrega'              THEN estado_nuevo IS 'Entregado'
             WHEN 'Reclamación aceptada' THEN estado_nuevo IS 'Por recuperar'
             WHEN 'Recuperación'         THEN estado_nuevo IS 'Recuperado'
             WHEN 'Devolución'           THEN estado_nuevo IS 'Devuelto'
             ELSE estado_nuevo IS NULL END)
);

-- ---------------------------------------------------------------------
-- Vista: cada devolución con su reclamación, su entrega original y su objeto, sin guardar nada dos veces.
-- ---------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS vista_devoluciones AS
SELECT d.id AS devolucion_id, r.id AS reclamacion_id, e.id AS entrega_id, o.id AS objeto_id, o.titulo,
       r.usuario_id AS dueno_id, e.retirado_por AS lo_tenia_id,
       d.recibido_por, d.fecha_recepcion, d.devuelto_por, d.fecha_devolucion, o.estado AS estado_objeto
FROM devoluciones d
JOIN reclamaciones r ON r.id = d.reclamacion_id
JOIN entregas e ON e.id = r.entrega_id
JOIN objetos o ON o.id = e.objeto_id;

-- ---------------------------------------------------------------------
-- Índices: solo los que usan las consultas de la app (SQLite no indexa solo las FK).
-- Ya tienen índice por su UNIQUE: usuarios.cif, usuarios.correo, entregas.objeto_id, devoluciones.reclamacion_id.
-- Todo índice de SQLite guarda el id al final, así que (objeto_id) ya devuelve el historial en orden de id.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_objetos_categoria      ON objetos (categoria);          -- filtro del catálogo
CREATE INDEX IF NOT EXISTS idx_objetos_estado         ON objetos (estado);             -- conteos y filtros por estado
CREATE INDEX IF NOT EXISTS idx_objetos_fecha          ON objetos (fecha);              -- consultas por fecha del hallazgo
CREATE INDEX IF NOT EXISTS idx_objetos_registrado_por ON objetos (registrado_por);     -- objetos registrados por un encargado
CREATE INDEX IF NOT EXISTS idx_entregas_retirado_por  ON entregas (retirado_por);      -- entregas de una persona
CREATE INDEX IF NOT EXISTS idx_reclamaciones_entrega  ON reclamaciones (entrega_id);   -- reclamaciones de una entrega
CREATE INDEX IF NOT EXISTS idx_reclamaciones_estado   ON reclamaciones (estado);       -- bandeja de pendientes
CREATE INDEX IF NOT EXISTS idx_reclamaciones_usuario  ON reclamaciones (usuario_id);   -- «Mis reclamaciones»
CREATE INDEX IF NOT EXISTS idx_historial_objeto       ON historial (objeto_id);        -- historial de un objeto (ya en orden de id)

-- Índices únicos parciales: reglas que dependen del estado de la fila
CREATE UNIQUE INDEX IF NOT EXISTS uq_reclamacion_aceptada  ON reclamaciones (entrega_id)             WHERE estado = 'Aceptada';
CREATE UNIQUE INDEX IF NOT EXISTS uq_reclamacion_pendiente ON reclamaciones (entrega_id, usuario_id) WHERE estado = 'Pendiente';

-- =====================================================================
-- Triggers
-- «Personal activo» = rol Administrador o Encargado y activo = 1.
-- =====================================================================

-- ---------- A. Hechos pasados: no se modifican ni se borran ----------
CREATE TRIGGER IF NOT EXISTS trg_historial_sin_cambios BEFORE UPDATE ON historial
BEGIN SELECT RAISE(ABORT, 'El historial no se modifica: solo se agregan filas.'); END;
CREATE TRIGGER IF NOT EXISTS trg_historial_sin_borrar BEFORE DELETE ON historial
BEGIN SELECT RAISE(ABORT, 'El historial no se borra.'); END;
CREATE TRIGGER IF NOT EXISTS trg_entregas_sin_cambios BEFORE UPDATE ON entregas
BEGIN SELECT RAISE(ABORT, 'Una entrega registrada no se modifica.'); END;
CREATE TRIGGER IF NOT EXISTS trg_entregas_sin_borrar BEFORE DELETE ON entregas
BEGIN SELECT RAISE(ABORT, 'Una entrega registrada no se borra.'); END;
CREATE TRIGGER IF NOT EXISTS trg_reclamaciones_sin_borrar BEFORE DELETE ON reclamaciones
BEGIN SELECT RAISE(ABORT, 'Una reclamación no se borra: se cancela o se rechaza.'); END;
CREATE TRIGGER IF NOT EXISTS trg_devoluciones_sin_borrar BEFORE DELETE ON devoluciones
BEGIN SELECT RAISE(ABORT, 'Una devolución registrada no se borra.'); END;

-- ---------- B. Objetos: quién los registra y estado coherente con los hechos ----------
CREATE TRIGGER IF NOT EXISTS trg_objeto_nuevo BEFORE INSERT ON objetos
BEGIN
    SELECT RAISE(ABORT, 'Solo el personal activo registra objetos.')
    WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.registrado_por AND rol IN ('Administrador', 'Encargado') AND activo = 1);
    SELECT RAISE(ABORT, 'Un objeto nuevo empieza bajo custodia (Activo, En resguardo o En bodega).')
    WHERE NEW.estado NOT IN ('Activo', 'En resguardo', 'En bodega');
END;

CREATE TRIGGER IF NOT EXISTS trg_objeto_registrado_por_fijo BEFORE UPDATE OF registrado_por ON objetos
WHEN NEW.registrado_por IS NOT OLD.registrado_por
BEGIN SELECT RAISE(ABORT, 'Quién registró el objeto no cambia.'); END;

-- El estado debe coincidir con la fase que dicen los hechos: sin entrega -> bajo custodia; con entrega ->
-- Entregado; con reclamación aceptada -> Por recuperar; con devolución -> Recuperado; completada -> Devuelto.
CREATE TRIGGER IF NOT EXISTS trg_objeto_estado_coherente BEFORE UPDATE OF estado ON objetos
WHEN NEW.estado IS NOT OLD.estado
 AND COALESCE((SELECT CASE WHEN d.fecha_devolucion IS NOT NULL THEN 'Devuelto'
                           WHEN d.id IS NOT NULL THEN 'Recuperado'
                           WHEN r.id IS NOT NULL THEN 'Por recuperar'
                           ELSE 'Entregado' END
               FROM entregas e
               LEFT JOIN reclamaciones r ON r.entrega_id = e.id AND r.estado = 'Aceptada'
               LEFT JOIN devoluciones d ON d.reclamacion_id = r.id
               WHERE e.objeto_id = NEW.id), 'Bajo custodia')
     IS NOT (CASE WHEN NEW.estado IN ('Activo', 'En resguardo', 'En bodega') THEN 'Bajo custodia' ELSE NEW.estado END)
BEGIN SELECT RAISE(ABORT, 'El estado no coincide con lo registrado para el objeto.'); END;

-- Registro en el historial al crear el objeto (autor = quien lo registró).
CREATE TRIGGER IF NOT EXISTS trg_historial_registro AFTER INSERT ON objetos
BEGIN
    INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
    VALUES (NEW.id, NEW.registrado_por, 'Registro', NEW.estado, datetime('now', 'localtime'));
END;

-- ---------- C. Entregas ----------
CREATE TRIGGER IF NOT EXISTS trg_entrega_valida BEFORE INSERT ON entregas
BEGIN
    SELECT RAISE(ABORT, 'Solo el personal activo registra entregas.')
    WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.entregado_por AND rol IN ('Administrador', 'Encargado') AND activo = 1);
    SELECT RAISE(ABORT, 'Solo se entrega un objeto que está bajo custodia.')
    WHERE (SELECT estado FROM objetos WHERE id = NEW.objeto_id) NOT IN ('Activo', 'En resguardo', 'En bodega');
    SELECT RAISE(ABORT, 'La entrega no puede ser anterior al hallazgo.')
    WHERE date(NEW.fecha_entrega) < (SELECT fecha FROM objetos WHERE id = NEW.objeto_id);
END;

CREATE TRIGGER IF NOT EXISTS trg_entrega_hecha AFTER INSERT ON entregas
BEGIN
    UPDATE objetos SET estado = 'Entregado' WHERE id = NEW.objeto_id;
    INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
    VALUES (NEW.objeto_id, NEW.entregado_por, 'Entrega', 'Entregado', NEW.fecha_entrega);
END;

-- ---------- D. Reclamaciones ----------
-- Nueva: sobre un objeto que sigue entregado, después de la entrega, por otra persona con cuenta activa.
CREATE TRIGGER IF NOT EXISTS trg_reclamacion_valida BEFORE INSERT ON reclamaciones
BEGIN
    SELECT RAISE(ABORT, 'Una reclamación nueva empieza como Pendiente.') WHERE NEW.estado <> 'Pendiente';
    SELECT RAISE(ABORT, 'Solo se reclama un objeto que sigue entregado.')
    WHERE (SELECT o.estado FROM entregas e JOIN objetos o ON o.id = e.objeto_id WHERE e.id = NEW.entrega_id) <> 'Entregado';
    SELECT RAISE(ABORT, 'Quien retiró el objeto no puede reclamarlo.')
    WHERE (SELECT retirado_por FROM entregas WHERE id = NEW.entrega_id) = NEW.usuario_id;
    SELECT RAISE(ABORT, 'Para reclamar se necesita una cuenta activa.')
    WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.usuario_id AND contrasena_hash IS NOT NULL AND activo = 1);
    SELECT RAISE(ABORT, 'La reclamación no puede ser anterior a la entrega.')
    WHERE NEW.fecha_solicitud < (SELECT fecha_entrega FROM entregas WHERE id = NEW.entrega_id);
END;

-- Al resolver: solo desde Pendiente, sin cambiar a qué entrega ni quién reclamó; acepta o rechaza el personal activo.
CREATE TRIGGER IF NOT EXISTS trg_reclamacion_resolver BEFORE UPDATE ON reclamaciones
BEGIN
    SELECT RAISE(ABORT, 'Una reclamación resuelta no se modifica.') WHERE OLD.estado <> 'Pendiente';
    SELECT RAISE(ABORT, 'No se cambia la entrega, el autor ni la fecha de una reclamación.')
    WHERE NEW.entrega_id IS NOT OLD.entrega_id OR NEW.usuario_id IS NOT OLD.usuario_id OR NEW.fecha_solicitud IS NOT OLD.fecha_solicitud;
    SELECT RAISE(ABORT, 'Solo el personal activo acepta o rechaza reclamaciones.')
    WHERE NEW.estado IN ('Aceptada', 'Rechazada')
      AND NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.resuelto_por AND rol IN ('Administrador', 'Encargado') AND activo = 1);
END;

CREATE TRIGGER IF NOT EXISTS trg_historial_reclamacion AFTER INSERT ON reclamaciones
BEGIN
    INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora)
    VALUES ((SELECT objeto_id FROM entregas WHERE id = NEW.entrega_id), NEW.usuario_id, 'Reclamación', NEW.fecha_solicitud);
END;

CREATE TRIGGER IF NOT EXISTS trg_reclamacion_aceptada AFTER UPDATE OF estado ON reclamaciones
WHEN NEW.estado = 'Aceptada'
BEGIN
    UPDATE objetos SET estado = 'Por recuperar' WHERE id = (SELECT objeto_id FROM entregas WHERE id = NEW.entrega_id);
    INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
    VALUES ((SELECT objeto_id FROM entregas WHERE id = NEW.entrega_id), NEW.resuelto_por, 'Reclamación aceptada', 'Por recuperar', NEW.fecha_resolucion);
END;

CREATE TRIGGER IF NOT EXISTS trg_reclamacion_cerrada AFTER UPDATE OF estado ON reclamaciones
WHEN NEW.estado IN ('Rechazada', 'Cancelada')
BEGIN
    INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora)
    VALUES ((SELECT objeto_id FROM entregas WHERE id = NEW.entrega_id),
            CASE NEW.estado WHEN 'Rechazada' THEN NEW.resuelto_por ELSE NEW.usuario_id END,
            CASE NEW.estado WHEN 'Rechazada' THEN 'Reclamación rechazada' ELSE 'Reclamación cancelada' END,
            NEW.fecha_resolucion);
END;

-- ---------- E. Devoluciones ----------
CREATE TRIGGER IF NOT EXISTS trg_devolucion_valida BEFORE INSERT ON devoluciones
BEGIN
    SELECT RAISE(ABORT, 'Solo se registra la devolución de una reclamación aceptada.')
    WHERE (SELECT estado FROM reclamaciones WHERE id = NEW.reclamacion_id) IS NOT 'Aceptada';
    SELECT RAISE(ABORT, 'Solo el personal activo recibe objetos de vuelta.')
    WHERE NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.recibido_por AND rol IN ('Administrador', 'Encargado') AND activo = 1);
    SELECT RAISE(ABORT, 'La devolución no puede ser anterior a la aceptación.')
    WHERE NEW.fecha_recepcion < (SELECT fecha_resolucion FROM reclamaciones WHERE id = NEW.reclamacion_id);
    SELECT RAISE(ABORT, 'El momento 2 se registra después, al devolverlo al dueño.') WHERE NEW.fecha_devolucion IS NOT NULL;
END;

CREATE TRIGGER IF NOT EXISTS trg_devolucion_recibida AFTER INSERT ON devoluciones
BEGIN
    UPDATE objetos SET estado = 'Recuperado'
    WHERE id = (SELECT e.objeto_id FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id WHERE r.id = NEW.reclamacion_id);
    INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
    VALUES ((SELECT e.objeto_id FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id WHERE r.id = NEW.reclamacion_id),
            NEW.recibido_por, 'Recuperación', 'Recuperado', NEW.fecha_recepcion);
END;

-- Completar (momento 2): una sola vez, por el personal activo, sin tocar lo ya registrado.
CREATE TRIGGER IF NOT EXISTS trg_devolucion_completar BEFORE UPDATE ON devoluciones
BEGIN
    SELECT RAISE(ABORT, 'Una devolución solo se completa una vez y lo registrado no cambia.')
    WHERE OLD.fecha_devolucion IS NOT NULL OR NEW.reclamacion_id IS NOT OLD.reclamacion_id
       OR NEW.recibido_por IS NOT OLD.recibido_por OR NEW.fecha_recepcion IS NOT OLD.fecha_recepcion;
    SELECT RAISE(ABORT, 'Solo el personal activo devuelve objetos.')
    WHERE NEW.devuelto_por IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.devuelto_por AND rol IN ('Administrador', 'Encargado') AND activo = 1);
END;

CREATE TRIGGER IF NOT EXISTS trg_devolucion_completada AFTER UPDATE OF fecha_devolucion ON devoluciones
WHEN OLD.fecha_devolucion IS NULL AND NEW.fecha_devolucion IS NOT NULL
BEGIN
    UPDATE objetos SET estado = 'Devuelto'
    WHERE id = (SELECT e.objeto_id FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id WHERE r.id = NEW.reclamacion_id);
    INSERT INTO historial (objeto_id, usuario_id, accion, estado_nuevo, fecha_hora)
    VALUES ((SELECT e.objeto_id FROM reclamaciones r JOIN entregas e ON e.id = r.entrega_id WHERE r.id = NEW.reclamacion_id),
            NEW.devuelto_por, 'Devolución', 'Devuelto', NEW.fecha_devolucion);
END;

-- ---------- F. Historial: quién puede firmar cada acción y que diga la verdad ----------
CREATE TRIGGER IF NOT EXISTS trg_historial_valido BEFORE INSERT ON historial
BEGIN
    SELECT RAISE(ABORT, 'Esta acción solo la hace el personal activo.')
    WHERE NEW.accion NOT IN ('Reclamación', 'Reclamación cancelada')
      AND NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.usuario_id AND rol IN ('Administrador', 'Encargado') AND activo = 1);
    SELECT RAISE(ABORT, 'Reclamar o cancelar requiere una cuenta.')
    WHERE NEW.accion IN ('Reclamación', 'Reclamación cancelada')
      AND NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.usuario_id AND contrasena_hash IS NOT NULL);
    SELECT RAISE(ABORT, 'El historial debe decir el estado real del objeto.')
    WHERE NEW.estado_nuevo IS NOT NULL AND NEW.estado_nuevo IS NOT (SELECT estado FROM objetos WHERE id = NEW.objeto_id);
END;

-- ---------------------------------------------------------------------
-- Consulta de ejemplo: la vida de un objeto con su estado anterior, sin guardarlo dos veces.
--   SELECT fecha_hora, accion, LAG(estado_nuevo) OVER (ORDER BY id) AS estado_anterior, estado_nuevo
--   FROM historial WHERE objeto_id = ? AND estado_nuevo IS NOT NULL ORDER BY id;
-- ---------------------------------------------------------------------
