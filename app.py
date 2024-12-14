from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import datetime
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import pytz
import time
import threading

app = Flask(__name__)

DB_FILE = "emails.db"
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")  # Asegúrate de tener tu API Key aquí

# Zona horaria de Madrid
MADRID_TZ = pytz.timezone('Europe/Madrid')

# Definir el adaptador para datetime
def adapt_datetime(value):
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return value

# Definir el convertidor para datetime
def convert_datetime(value):
    return datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')

# Registrar adaptadores de datetime en SQLite
sqlite3.register_adapter(datetime.datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)

def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    send_date DATETIME NOT NULL
                )
            """)
            conn.commit()
            print("Base de datos inicializada correctamente.")  # Verificación de la DB
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/send_email", methods=["POST"])
def send_email():
    try:
        recipient = request.form["recipient"]
        subject = request.form["subject"]
        body = request.form["body"]
        send_date_str = request.form["send_date"]  # Fecha y hora seleccionada
        send_date = datetime.datetime.strptime(send_date_str, "%Y-%m-%dT%H:%M")  # Convierte a datetime

        # Convertimos la hora a la zona horaria de Madrid
        send_date = MADRID_TZ.localize(send_date)  # Localizamos a la zona de Madrid

        print(f"Correo programado para {send_date} con el asunto '{subject}'")  # Log

        # Guarda el correo en la base de datos
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO emails (recipient, subject, body, send_date)
                VALUES (?, ?, ?, ?)
            """, (recipient, subject, body, send_date))
            conn.commit()

        print("Correo guardado en la base de datos.")  # Log
        return redirect(url_for("index"))
    except Exception as e:
        print(f"Error al procesar el correo: {e}")  # Log de errores
        return "Hubo un error al enviar el correo."

def send_scheduled_emails():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now(pytz.utc)  # Obtener la hora actual en UTC
            print(f"Comprobando correos para enviar en la fecha y hora: {now}")  # Log
            cursor.execute("SELECT * FROM emails WHERE send_date <= ?", (now,))
            emails_to_send = cursor.fetchall()

            if not emails_to_send:
                print("No hay correos programados para enviar.")  # Log

            for email in emails_to_send:
                print(f"Enviando correo a {email[1]}...")  # Log
                send_email_via_sendgrid(email[1], email[2], email[3])
                cursor.execute("DELETE FROM emails WHERE id = ?", (email[0],))

            conn.commit()
    except Exception as e:
        print(f"Error al enviar correos programados: {e}")  # Log de errores

def send_email_via_sendgrid(recipient, subject, body):
    try:
        print(f"Enviando correo a {recipient} con asunto '{subject}'")  # Log
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        message = Mail(
            from_email="mailsfromthepast@gmail.com",  # Tu correo como remitente
            to_emails=recipient,
            subject=subject,
            plain_text_content=body
        )
        response = sg.send(message)
        print(f"Correo enviado a {recipient}, estado: {response.status_code}")  # Log
    except Exception as e:
        print(f"Error enviando el correo: {e}")  # Log de errores

def run_scheduled_emails():
    while True:
        send_scheduled_emails()  # Ejecutar la comprobación continuamente
        time.sleep(60)  # Espera 1 minuto antes de la siguiente comprobación

if __name__ == "__main__":
    init_db()
    # Ejecutar la comprobación de correos en un hilo separado
    threading.Thread(target=run_scheduled_emails, daemon=True).start()
    app.run(debug=True)
