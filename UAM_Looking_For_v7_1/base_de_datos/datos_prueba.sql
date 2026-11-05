-- =====================================================================
-- UAM Looking For v7.1 · Datos de prueba (caso completo de reclamación y devolución)
-- Ejecutar después de schema.sql en una base vacía.
-- En v7.1 NO se escribe a mano el estado del objeto ni el historial de los hechos: lo hacen los triggers.
-- Solo se escriben a mano las acciones que no nacen de otra tabla (aquí: «Foto»).
-- Contraseñas: hashes reales de «clave123» calculados con reglas_python.hash_contrasena.
-- =====================================================================
PRAGMA foreign_keys = ON;
BEGIN;

INSERT INTO usuarios (id, nombre, cif, correo, telefono, carrera, rol, contrasena_hash, activo) VALUES
 (1,  'Administración UAM', 'ADMIN',    'admin@uamv.edu.ni',     NULL,        NULL, 'Administrador', NULL, 1),
 (2,  'María Torres',       'ENC00001', 'mtorres@uamv.edu.ni',   '8800 1111', NULL, 'Encargado',
      'pbkdf2_sha256$600000$2e6b6835a8666821e0fcbcfe8d6bf04a$4d4a802ab535ae4ca7deab400be1a6e8c01302063987d0a2bcd9ff9334011e81', 1),
 (3,  'Luis Rivas',         'ENC00002', 'lrivas@uamv.edu.ni',    '8800 2222', NULL, 'Encargado',
      'pbkdf2_sha256$600000$79dc25552461312ae76cb3df54c1b532$44d548f0c72508da16196f8f94ac03ac55d57754a6562dd2d3b9ad8414152afa', 1),
 (4,  'Ana Martínez',       '26010001', 'amartinez@uamv.edu.ni', '8555 1111', 'Ingeniería en Sistemas', 'Estudiante',
      'pbkdf2_sha256$600000$8ee66f6f7e3143afa2310c6837dd2132$e80302ca426a9eab96521e26f21783db21ee508c1b51bcf4a6a508739d44abc6', 1),
 (5,  'Carlos López',       '26010002', 'clopez@uamv.edu.ni',    NULL,        'Medicina', 'Estudiante',
      'pbkdf2_sha256$600000$fcc1a12dc7076586054c01befc19ebc1$c8b0c0c61b56f9ed10be0d4933455cd5b9a2aebb51d589dea238b0a7a3c31347', 1),
 (6,  'Rosa Pérez',         'DOC00123', 'rperez@uamv.edu.ni',    '8123 4567', NULL, 'Docente',
      'pbkdf2_sha256$600000$425f2e12b2f993ef737c5021aa977d4b$6e78fc42ccafaf3dddd547f74d647d898fde3c978686cb06a0ff8f8f88c4bb15', 1),
 (7,  'Pedro Gómez',        NULL,       NULL,                    '8888 7777', NULL, 'Visitante', NULL, 1),   -- visitante sin CIF ni cuenta
 (8,  'Jorge Silva',        'ADM00045', NULL,                    '8777 6666', NULL, 'Administrativo', NULL, 1),
 (9,  'Elena Díaz',         NULL,       NULL,                    '8999 0000', NULL, 'Visitante', NULL, 1),   -- segundo NULL en cif: permitido
 (10, 'Marta Ruiz',         'ENC00003', 'mruiz@uamv.edu.ni',     NULL,        NULL, 'Encargado',
      'pbkdf2_sha256$600000$425f2e12b2f993ef737c5021aa977d4b$6e78fc42ccafaf3dddd547f74d647d898fde3c978686cb06a0ff8f8f88c4bb15', 0); -- encargada desactivada

-- Objetos (el trigger escribe «Registro» en el historial; Rosa trajo la calculadora, Jorge la mochila)
INSERT INTO objetos (id, titulo, descripcion, descripcion_publica, categoria, lugar_encontrado, ubicacion, fecha, hora,
                     estado, registrado_por, reportado_por, foto_publica, foto) VALUES
 (1, 'Calculadora Casio', 'fx-991LA gris con «A.M.» grabado atrás y una tapa rota', 'Calculadora científica gris',
     'Electrónicos', 'Biblioteca, mesa 4', 'Vida Estudiantil', '2026-10-28', '14:35', 'En resguardo', 2, 6, 0, NULL),
 (2, 'Llavero rojo', 'Tres llaves y un llavero de la selección', 'Llavero rojo con tres llaves',
     'Llaves', 'Cafetería', 'Edificio A', '2026-10-29', NULL, 'Activo', 3, NULL, 0, NULL),
 (3, 'Mochila azul', 'Mochila Totto azul con un cuaderno de Cálculo', 'Mochila azul',
     'Ropa/Accesorios', 'Aula A-203', 'Sala Docente', '2026-10-30', '09:10', 'En bodega', 2, 8, 1, X'FFD8FFE000104A46494600FFD9');
INSERT INTO historial (objeto_id, usuario_id, accion, fecha_hora) VALUES (3, 2, 'Foto', '2026-10-30 09:31:00');   -- acción manual

-- Entrega inicial: Pedro (visitante) retira la calculadora. El trigger la pasa a «Entregado» y lo anota.
INSERT INTO entregas (id, objeto_id, retirado_por, entregado_por, senas, fecha_entrega) VALUES
 (1, 1, 7, 2, 'Calculadora gris marca Casio', '2026-10-31 11:00:00');

-- Tres reclamaciones sobre la MISMA entrega (Ana y Carlos son estudiantes; Rosa, docente con cuenta)
INSERT INTO reclamaciones (id, entrega_id, usuario_id, descripcion, lugar_perdida, fecha_perdida, fecha_solicitud) VALUES
 (1, 1, 4, 'Casio fx-991LA gris, tiene mis iniciales A.M. grabadas atrás y la tapa rota', 'Biblioteca', '2026-10-28', '2026-11-01 08:30:00'),
 (2, 1, 5, 'Es una calculadora gris que dejé en la biblioteca', 'Biblioteca', NULL, '2026-11-01 09:00:00'),
 (3, 1, 6, 'Creo que es la que perdí en clase', NULL, NULL, '2026-11-01 09:15:00');

-- Resoluciones: Rosa cancela; María rechaza a Carlos con motivo y acepta a Ana (el objeto pasa a «Por recuperar»).
UPDATE reclamaciones SET estado = 'Cancelada', fecha_resolucion = '2026-11-01 10:00:00' WHERE id = 3;
UPDATE reclamaciones SET estado = 'Rechazada', respuesta = 'Las señas no coinciden con el registro',
                         fecha_resolucion = '2026-11-02 08:00:00', resuelto_por = 2 WHERE id = 2;
UPDATE reclamaciones SET estado = 'Aceptada', respuesta = 'Coinciden las iniciales grabadas',
                         fecha_resolucion = '2026-11-02 08:05:00', resuelto_por = 2 WHERE id = 1;

-- Devolución, momento 1: Pedro trae la calculadora y la recibe Luis   -> «Recuperado»
INSERT INTO devoluciones (id, reclamacion_id, recibido_por, fecha_recepcion, observaciones) VALUES
 (1, 1, 3, '2026-11-02 14:00:00', 'Pedro la devolvió sin problemas');

-- Devolución, momento 2: María se la devuelve a Ana                   -> «Devuelto»
UPDATE devoluciones SET devuelto_por = 2, fecha_devolucion = '2026-11-03 09:00:00' WHERE id = 1;

COMMIT;

-- Para revisar:
--   SELECT * FROM vista_devoluciones;   -- devolución con su reclamación, entrega original, objeto y dueño
--   SELECT fecha_hora, accion, LAG(estado_nuevo) OVER (ORDER BY id) AS estado_anterior, estado_nuevo
--   FROM historial WHERE objeto_id = 1 AND estado_nuevo IS NOT NULL ORDER BY id;
