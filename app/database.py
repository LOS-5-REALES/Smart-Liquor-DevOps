import os
import time
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

load_dotenv()

# URL de Supabase (inyectada por Docker)
DATABASE_URL = os.getenv("DATABASE_URL")

import os
import time  # Necesario para el time.sleep
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError  # Necesario para detectar fallos de red
from dotenv import load_dotenv

# 1. Cargar variables de entorno
load_dotenv()

# 2. Obtener la URL (Aquí estaba el error del 'None')
DATABASE_URL = os.getenv("DATABASE_URL")

# Si por alguna razón la URL no llega, el programa se detendrá con un mensaje claro
if not DATABASE_URL:
    raise ValueError("ERROR: La variable DATABASE_URL no está cargada. Revisa tu archivo .env o el comando docker run.")

# 3. Configuración de SQLAlchemy
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 4. Función para obtener la DB (para FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 5. Lógica de Resiliencia (Tu código original mantenido)
def esperar_y_crear_tablas():
    """Intenta conectar a Supabase 10 veces antes de rendirse"""
    intentos = 0
    while intentos < 10:
        try:
            print(f"--- 📡 Intentando conectar a Supabase (Intento {intentos + 1}/10) ---")
            # Sincroniza los modelos con la base de datos real
            Base.metadata.create_all(bind=engine)
            print("--- ✅ CONEXIÓN EXITOSA Y TABLAS SINCRONIZADAS ---")
            return True
        except OperationalError as e:
            intentos += 1
            print(f"--- ⏳ Esperando respuesta de la nube... ({e}) ---")
            time.sleep(4)
    return False