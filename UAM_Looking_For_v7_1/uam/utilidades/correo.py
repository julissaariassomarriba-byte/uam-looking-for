"""Envío de correos con la librería estándar de Python (smtplib), sin servicios externos.

Se configura en el .env: SMTP_SERVIDOR, SMTP_PUERTO (587 con STARTTLS o 465 con SSL), SMTP_USUARIO, SMTP_CONTRASENA y
SMTP_REMITENTE. Si falta el servidor o el remitente, el sistema no intenta enviar y lo dice.
"""
import smtplib
import ssl
from email.message import EmailMessage

ESPERA_SEGUNDOS = 15


def configurado(env):
    return bool(env.get('SMTP_SERVIDOR') and env.get('SMTP_REMITENTE'))


def enviar(env, para, asunto, texto):
    """(True, None) si el servidor aceptó el correo; (False, motivo corto) si no. Nunca muestra claves."""
    if not configurado(env):
        return False, 'sin configurar'
    mensaje = EmailMessage()
    mensaje['From'], mensaje['To'], mensaje['Subject'] = env['SMTP_REMITENTE'], para, asunto
    mensaje.set_content(texto)
    try:
        puerto = int(env.get('SMTP_PUERTO') or 587)
        contexto = ssl.create_default_context()
        if puerto == 465:
            servidor = smtplib.SMTP_SSL(env['SMTP_SERVIDOR'], puerto, context=contexto, timeout=ESPERA_SEGUNDOS)
        else:
            servidor = smtplib.SMTP(env['SMTP_SERVIDOR'], puerto, timeout=ESPERA_SEGUNDOS)
            servidor.starttls(context=contexto)
        with servidor:
            if env.get('SMTP_USUARIO'):
                servidor.login(env['SMTP_USUARIO'], env.get('SMTP_CONTRASENA', ''))
            servidor.send_message(mensaje)
        return True, None
    except (OSError, ValueError, smtplib.SMTPException) as error:
        return False, type(error).__name__
