from fastapi import FastAPI, Form, Response  # <--- IMPORTANTE: Agregamos Form y Response
import flet_fastapi
import uvicorn
from ui import main as build_dashboard
from database import esperar_y_crear_tablas
from fastapi.staticfiles import StaticFiles
import os
from app.bot import procesar_mensaje

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
#------------------------------------------------------------------------------
@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...)): # Ahora Form sí existe
    print(f"Mensaje recibido: {Body}") 
    respuesta_xml = procesar_mensaje(Body)
    # Ahora Response sí existe
    return Response(content=respuesta_xml, media_type="application/xml")
#-------------------------------------------------------------------------------
