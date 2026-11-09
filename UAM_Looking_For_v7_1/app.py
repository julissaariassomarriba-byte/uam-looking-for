"""Punto de entrada de UAM Looking For v9.

PythonAnywhere (archivo WSGI) hace «from app import app as application»; en tu computadora: python app.py
Todo el código está en el paquete uam/ (ver uam/__init__.py).
"""
from uam import crear_app

app = crear_app()

if __name__ == '__main__':
    app.run(debug=True)
