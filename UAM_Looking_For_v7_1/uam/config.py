# Configuración fija del sistema: roles, estados, categorías y límites.

ROL_ADMIN, ROL_ENCARGADO, ROL_ESTUDIANTE = 'Administrador', 'Encargado', 'Estudiante'
ROLES_GESTIONABLES = (ROL_ESTUDIANTE, ROL_ENCARGADO)   # los que crea el administrador desde el panel
ROLES_PERSONAL = (ROL_ADMIN, ROL_ENCARGADO)

# Categoría -> ícono
CATEGORIAS = {'Electrónicos': 'laptop', 'Documentos/Carné': 'carne', 'Ropa/Accesorios': 'camisa',
              'Llaves': 'llave', 'Útiles/Libros': 'libro', 'Otros': 'paquete'}

# Estados del objeto y su ícono (los tres primeros los pone el personal).
ESTADOS = {'Activo': 'activo', 'En resguardo': 'escudo', 'En bodega': 'bodega', 'Entregado': 'check',
           'Por recuperar': 'historial', 'Recuperado': 'bandeja', 'Devuelto': 'mano'}
ESTADOS_MANUALES = ('Activo', 'En resguardo', 'En bodega')

# «Cancelada» solo existe en reclamaciones antiguas (desde la v9 no se cancelan).
ESTADOS_RECLAMACION = ('Pendiente', 'Aceptada', 'Rechazada')
ESTADO_RECLAMACION_ANTIGUO = 'Cancelada'

TIPOS_PERSONA = ('Estudiante', 'Docente', 'Administrativo', 'Visitante')   # quien trae o retira un objeto

# Reportes de visitantes: estado -> clase CSS
ESTADOS_REPORTE = {'Pendiente': 'pendiente', 'En revisión': 'revision', 'Localizado': 'localizado',
                   'Resuelto': 'resuelto', 'Cerrado': 'cerrado'}

CODIGO_PAIS = '505'   # Nicaragua: se antepone a los teléfonos de 8 dígitos para los enlaces de WhatsApp

# Puntos de resguardo. Para agregar uno basta con sumarlo aquí: la base no cambia.
UBICACIONES = ('Vida Estudiantil', 'Sala Docente', 'Edificio A')

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')

# Largos máximos de los textos (se revisan en el formulario y en el servidor).
LARGO_MAXIMO = {'nombre': 100, 'cif': 20, 'correo': 120, 'telefono': 30, 'carrera': 100, 'titulo': 150,
                'descripcion': 2000, 'descripcion_publica': 500, 'lugar': 200, 'senas': 1000, 'nota': 1000,
                'observaciones': 2000, 'contrasena': 128}

TAMANO_MAXIMO_ENVIO = 2 * 1024 * 1024   # bytes: Flask corta cualquier envío mayor antes de leerlo


# Lee el archivo .env (CLAVE=valor) y devuelve un diccionario.
def leer_env(ruta):
    valores = {}
    try:
        with open(ruta, encoding='utf-8') as archivo:
            for linea in archivo:
                linea = linea.strip()
                if not linea or linea.startswith('#') or '=' not in linea:
                    continue
                clave, valor = (parte.strip() for parte in linea.split('=', 1))
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in '"\'':
                    valor = valor[1:-1]
                valores[clave] = valor
    except OSError:
        pass
    return valores
