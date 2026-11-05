"""Genera el PDF del historial escribiendo el formato PDF a mano (sin librerías)."""
from config import ESTADOS

ANCHO, ALTO, MARGEN = 792, 612, 40
VERDE, GRIS, GRIS_FILA, BLANCO = (0, 0.478, 0.514), (0.15, 0.15, 0.15), (0.96, 0.97, 0.97), (1, 1, 1)


# Pasa el texto a Windows-1252 (la codificación de las fuentes del PDF) y escapa ( ) y \.
def texto_pdf(texto):
    texto = str('' if texto is None else texto).replace('→', '->').encode('cp1252', 'replace').decode('cp1252')
    return texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


# Divide un texto en líneas que quepan en el ancho dado (aprox. 0.52 del tamaño por letra).
def partir_lineas(texto, ancho, tamano):
    maximo = max(1, int(ancho / (tamano * 0.52)))
    lineas = ['']
    for palabra in str('' if texto is None else texto).split():
        for i in range(0, len(palabra), maximo):
            trozo = palabra[i:i + maximo]
            if len(f'{lineas[-1]} {trozo}'.strip()) <= maximo:
                lineas[-1] = f'{lineas[-1]} {trozo}'.strip()
            else:
                lineas.append(trozo)
    return lineas


# Documento PDF mínimo: guarda los comandos de dibujo de cada página y arma el archivo al final.
class DocumentoPDF:
    def __init__(self):
        self.paginas = []
        self.nueva_pagina()

    def nueva_pagina(self):
        self.ops, self.y = [], ALTO - MARGEN
        self.paginas.append(self.ops)

    def texto(self, x, y, contenido, tamano=9, negrita=False, rgb=GRIS):
        self.ops.append(f'{rgb[0]} {rgb[1]} {rgb[2]} rg BT /{"F2" if negrita else "F1"} {tamano} Tf {x:.1f} {y:.1f} Td '
                        f'({texto_pdf(contenido)}) Tj ET')

    def rectangulo(self, x, y, ancho, alto, rgb):
        self.ops.append(f'{rgb[0]} {rgb[1]} {rgb[2]} rg {x:.1f} {y:.1f} {ancho:.1f} {alto:.1f} re f')

    # Si no cabe lo que sigue, pasa a una página nueva.
    def espacio(self, alto):
        nueva = self.y - alto < MARGEN + 20
        if nueva:
            self.nueva_pagina()
        return nueva

    def encabezado_tabla(self, columnas):
        self.rectangulo(MARGEN, self.y - 20, ANCHO - 2 * MARGEN, 20, VERDE)
        x = MARGEN
        for titulo, ancho in columnas:
            self.texto(x + 5, self.y - 14, titulo, 8.5, True, BLANCO)
            x += ancho
        self.y -= 20

    # Tabla con título; columnas = [(encabezado, ancho), ...]. Repite el encabezado al cambiar de página.
    def tabla(self, titulo, columnas, filas):
        self.espacio(60)
        self.texto(MARGEN, self.y - 12, titulo, 12, True)
        self.y -= 22
        self.encabezado_tabla(columnas)
        for numero, fila in enumerate(filas):
            celdas = [partir_lineas(valor, ancho - 10, 8.5) for valor, (_, ancho) in zip(fila, columnas)]
            alto = max(len(c) for c in celdas) * 11 + 8
            if self.espacio(alto):
                self.encabezado_tabla(columnas)
            if numero % 2:
                self.rectangulo(MARGEN, self.y - alto, ANCHO - 2 * MARGEN, alto, GRIS_FILA)
            x = MARGEN
            for lineas, (_, ancho) in zip(celdas, columnas):
                for i, linea in enumerate(lineas):
                    self.texto(x + 5, self.y - 13 - i * 11, linea, 8.5)
                x += ancho
            self.y -= alto
            self.ops.append(f'0.85 0.87 0.88 RG 0.5 w {MARGEN} {self.y:.1f} m {ANCHO - MARGEN} {self.y:.1f} l S')
        self.y -= 25

    # Arma el archivo: objetos (catálogo, páginas, fuentes y contenido), tabla xref y trailer.
    def guardar(self):
        total = len(self.paginas)
        objetos = ['<< /Type /Catalog /Pages 2 0 R >>',
                   f'<< /Type /Pages /Kids [{" ".join(f"{5 + 2 * i} 0 R" for i in range(total))}] /Count {total} >>',
                   '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
                   '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
        for i, ops in enumerate(self.paginas):
            self.ops = ops
            self.texto(ANCHO - MARGEN - 60, 20, f'Página {i + 1} de {total}', 8, rgb=(0.5, 0.5, 0.5))
            contenido = '\n'.join(ops).encode('cp1252')
            objetos.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO} {ALTO}] '
                           f'/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {6 + 2 * i} 0 R >>')
            objetos.append(f'<< /Length {len(contenido)} >>\nstream\n'.encode('latin-1') + contenido + b'\nendstream')
        salida, posiciones = bytearray(b'%PDF-1.4\n'), []
        for numero, objeto in enumerate(objetos, 1):
            posiciones.append(len(salida))
            salida += f'{numero} 0 obj\n'.encode() + (objeto if isinstance(objeto, bytes) else objeto.encode('latin-1')) + b'\nendobj\n'
        xref = len(salida)
        salida += f'xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n'.encode()
        salida += ''.join(f'{p:010d} 00000 n \n' for p in posiciones).encode()
        salida += f'trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(salida)


# Reporte del historial: encabezado, resumen por estado, tabla de objetos y tabla de movimientos.
def generar_historial(objetos, movimientos, conteo, usuario, fecha):
    doc = DocumentoPDF()
    doc.rectangulo(0, ALTO - 64, ANCHO, 64, VERDE)
    doc.texto(MARGEN, ALTO - 34, 'UAM Looking For - Historial de Objetos', 18, True, BLANCO)
    doc.texto(MARGEN, ALTO - 50, f'Generado: {fecha}   |   Por: {usuario}', 9, rgb=BLANCO)
    resumen = '   '.join(f'{e}: {conteo.get(e, 0)}' for e in ESTADOS)
    doc.texto(MARGEN, ALTO - 84, f'Por estado  -  {resumen}   Total: {len(objetos)}', 9)
    doc.y = ALTO - 104
    doc.tabla('Todos los objetos',
              [('#', 30), ('Objeto', 115), ('Categoría', 95), ('Estado', 75), ('Se guarda en', 90), ('Encontrado en', 105),
               ('Fecha', 70), ('Descripción', 132)],
              [(o['id'], o['titulo'], o['categoria'], o['estado'], o['ubicacion'] or 'Sin asignar', o['lugar_encontrado'],
                f"{o['fecha']} {o['hora'] or ''}", o['descripcion'])
               for o in objetos] or [('-', 'Sin objetos registrados', '', '', '', '', '', '')])
    doc.tabla('Movimientos', [('Fecha y hora', 100), ('Objeto', 150), ('Acción', 150), ('Estado resultante', 120), ('Usuario', 192)],
              [(m['fecha_hora'], f'#{m["objeto_id"]} {m["titulo"]}', m['accion'], m['estado_nuevo'] or '-', m['usuario_nombre'])
               for m in movimientos] or [('-', 'Sin movimientos registrados', '', '', '')])
    return doc.guardar()
