# app/main_bot.py
import uvicorn
from fastapi import FastAPI, Form, Response
from bot import procesar_mensaje
from database import esperar_y_crear_tablas

app = FastAPI()


@app.get("/")
def health_check():
    return {"status": "Bot WhatsApp operativo"}


@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...), From: str = Form("")):
    print(f"[WHATSAPP] De: {From} | Mensaje: {Body}")
    respuesta_xml = procesar_mensaje(Body)
    return Response(content=respuesta_xml, media_type="application/xml")


if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("Bot WhatsApp iniciado en http://0.0.0.0:8001")
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        print("Error: No se pudo conectar a la base de datos.")