import fastapi
import flet_fastapi
import uvicorn
from ui import main as build_dashboard
from database import esperar_y_crear_tablas
from fastapi.staticfiles import StaticFiles
import os

app = fastapi.FastAPI()
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api")
def read_root():
    return {"Smart_Liquor": "Backend Operativo vinculado a Supabase 🚀"}

# Montamos la app de Flet. El modo 'async' es vital para la estabilidad
app.mount("/", flet_fastapi.app(build_dashboard))

if __name__ == "__main__":
    # Esperamos la conexión a Supabase
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor Unificado en http://localhost:8000")
        # Arrancamos con Uvicorn de forma nativa
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")