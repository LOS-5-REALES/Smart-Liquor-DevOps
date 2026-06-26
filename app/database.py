# app/database.py
"""
Módulo de configuración y conexión a la base de datos.

Maneja la conexión principal con Supabase (o cualquier base de datos PostgreSQL)
utilizando SQLAlchemy. Define el motor (engine), la fábrica de sesiones y las
rutinas de resiliencia para asegurar que el sistema no falle al arrancar.
"""

import os
import time
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv()

# URL de Supabase (inyectada por Docker o archivo .env local)
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    Generador de sesiones de base de datos.

    Crea una nueva sesión para una transacción o petición y garantiza
    que se cierre correctamente al finalizar, liberando los recursos,
    incluso si ocurre una excepción durante la ejecución.

    Es el estándar para inyectar dependencias en FastAPI usando `Depends()`.

    Yields:
        Session: Una sesión activa de base de datos de SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def esperar_y_crear_tablas() -> bool:
    """
    Establece la conexión inicial con la base de datos y sincroniza los modelos.

    Implementa lógica de resiliencia (retry pattern). Intenta conectarse a
    Supabase hasta 10 veces, con pausas de 4 segundos entre cada intento.
    Esto evita que la aplicación colapse si la nube tarda en responder o si
    el contenedor de la base de datos aún se está iniciando.

    Si las tablas definidas en `models.py` no existen, las crea automáticamente.

    Returns:
        bool: True si la conexión y creación de tablas fue exitosa.
              False si se agotaron los 10 intentos sin éxito.
    """
    intentos = 0
    while intentos < 10:
        try:
            print(f"--- 📡 Intentando conectar a Supabase (Intento {intentos + 1}/10) ---")
            # Esto verifica la conexión y crea tablas si no existen
            Base.metadata.create_all(bind=engine)
            print("--- ✅ CONEXIÓN EXITOSA Y TABLAS SINCRONIZADAS ---")
            return True
        except OperationalError as e:
            intentos += 1
            print(f"--- ⏳ Esperando respuesta de la nube... ({e}) ---")
            time.sleep(4)
    return False