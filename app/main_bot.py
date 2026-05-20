# app/main_bot.py  — Servidor INDEPENDIENTE solo para WhatsApp
# Corre en puerto 8001, completamente separado del dashboard

import uvicorn
from fastapi import FastAPI, Form, Response
from bot import procesar_mensaje
from database import esperar_y_crear_tablas

app = FastAPI()


@app.get("/")
def health_check():
    """Endpoint para verificar que el bot está vivo."""
    return {"status": "Bot WhatsApp operativo"}


@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form("")):
    """Recibe mensajes de Twilio y responde con TwiML."""
    print(f"[WHATSAPP] De: {From} | Mensaje: {Body}")
    respuesta_xml = procesar_mensaje(Body)
    return Response(content=respuesta_xml, smedia_type="application/xml")


if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("Bot WhatsApp iniciado en http://0.0.0.0:8001")
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        print("Error: No se pudo conectar a la base de datos.")