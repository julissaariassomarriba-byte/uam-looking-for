# Envío de correos con smtplib.
import smtplib
import ssl
from email.message import EmailMessage

ESPERA_SEGUNDOS = 15


# Dice si el correo está configurado en el .env.
def configurado(env):
    return bool(env.get('SMTP_SERVIDOR') and env.get('SMTP_REMITENTE'))


# Envía un correo por SMTP.
def enviar(env, para, asunto, texto):
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
