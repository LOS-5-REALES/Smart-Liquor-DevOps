# app/main.py
"""
Punto de entrada principal del sistema unificado.

Este servidor actúa como el núcleo de la aplicación. Se encarga de tres tareas fundamentales:
1. Servir los archivos estáticos (como los reportes PDF generados).
2. Exponer rutas de API (como el health check).
3. Montar y servir la interfaz gráfica de usuario construida con Flet.
"""

import fastapi
import flet_fastapi
import uvicorn
from ui import main as build_dashboard
from database import esperar_y_crear_tablas
from fastapi.staticfiles import StaticFiles
import os

app = fastapi.FastAPI(
    title="Smart Liquor - Core Dashboard",
    description="Servidor principal que aloja el panel de control (Flet) y las APIs base.",
    version="1.0"
)

# Creación dinámica de la carpeta de archivos estáticos para los reportes
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get(
    "/api",
    tags=["Diagnóstico"],
    summary="Verificar conexión del backend core"
)
def read_root():
    """
    Ruta de prueba rápida para confirmar que el backend está corriendo.

    Permite a los administradores o monitores de red validar que el servidor
    FastAPI está levantado y conectado a Supabase antes de intentar cargar
    toda la interfaz gráfica.

    Returns:
        dict: Un mensaje de confirmación de estado operativo.
    """
    return {"Smart_Liquor": "Backend Operativo vinculado a Supabase 🚀"}


# Montamos la app de Flet. El modo 'async' es vital para la estabilidad
app.mount("/", flet_fastapi.app(build_dashboard))

if __name__ == "__main__":
    # Esperamos la conexión a Supabase antes de iniciar el servidor web
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor Unificado en http://localhost:8000")
        # Arrancamos con Uvicorn de forma nativa
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")