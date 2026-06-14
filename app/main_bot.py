# app/main_bot.py
"""
Punto de entrada del microservicio del Bot de WhatsApp.

Expone los endpoints necesarios para integrarse con la API de Twilio,
recibiendo mensajes entrantes vía Webhooks y despachando las respuestas
generadas por el motor lógico del bot de forma multiusuario.
"""

import uvicorn
from fastapi import FastAPI, Form, Response
from bot import procesar_mensaje
from database import esperar_y_crear_tablas

app = FastAPI(
    title="Smart Liquor - Bot WhatsApp",
    description="Microservicio encargado de recibir y procesar los mensajes de los clientes vía Twilio",
    version="1.0"
)


@app.get("/", tags=["Sistema"], summary="Health Check del Bot")
def health_check():
    """
    Verifica si el servidor del bot está encendido y respondiendo.

    Returns:
        dict: Un diccionario JSON indicando el estado operativo del servicio.
    """
    return {"status": "Bot WhatsApp operativo"}


@app.post(
    "/whatsapp",
    tags=["Webhook de Twilio"],
    summary="Recepción de mensajes de WhatsApp",
    responses={
        200: {
            "description": "Respuesta en formato TwiML (XML) para que Twilio la envíe al usuario.",
            "content": {"application/xml": {"example": "<Response><Message>Hola Mundo</Message></Response>"}}
        }
    }
)
async def whatsapp_webhook(
        Body: str = Form(..., title="Mensaje", description="El texto que el cliente escribió en WhatsApp"),
        From: str = Form("", title="Número Remitente", description="Número de teléfono del cliente (ej. whatsapp:+51999999999)")
):
    """
    Este endpoint es consumido exclusivamente por los servidores de **Twilio**.

    1. Recibe el mensaje entrante del usuario y su número telefónico.
    2. Realiza un parsing/limpieza del número para extraer los datos reales limpios.
    3. Lo pasa al motor lógico indexando el estado por su número de celular puro.
    4. Devuelve las instrucciones de respuesta en formato XML.

    Args:
        Body (str): El contenido de texto del mensaje de WhatsApp extraído del formulario.
        From (str): Identificador único del remitente proveído por Twilio.

    Returns:
        Response: Respuesta HTTP con encabezado `application/xml` conteniendo
                  las instrucciones TwiML para Twilio.
    """
    print(f"[WHATSAPP ORIGINAL] De: {From} | Mensaje: {Body}")
    
    # 🧼 LIMPIEZA DE DATOS REALES:
    # Twilio envía "whatsapp:+51999888777". Removemos el prefijo para dejar solo los 9 dígitos "999888777".
    telefono_limpio = From.replace("whatsapp:", "").replace("+51", "").strip()
    
    # Salvaguarda por si el formato del remitente varía o llega vacío
    if not telefono_limpio:
        telefono_limpio = "default"

    print(f"[WHATSAPP PROCESADO] Celular Limpio para BD: {telefono_limpio}")
    
    # 💥 ENTRADA MULTIUSUARIO CORREGIDA: Pasamos el teléfono real limpio a la lógica y base de datos
    respuesta_xml = procesar_mensaje(Body, telefono=telefono_limpio)
    
    return Response(content=respuesta_xml, media_type="application/xml")


if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("Bot WhatsApp iniciado en http://0.0.0.0:8001")
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        print("Error: No se pudo conectar a la base de datos.")