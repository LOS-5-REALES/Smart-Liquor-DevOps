# app/bot.py
from twilio.twiml.messaging_response import MessagingResponse

def procesar_mensaje(cuerpo_mensaje: str):
    mensaje_recibido = cuerpo_mensaje.lower().strip()
    twiml_response = MessagingResponse()
    msg = twiml_response.message()

    if mensaje_recibido == "hola":
        msg.body("¡Hola! 🍷 Bienvenido a Smart-Liquor. Soy el bot de pedidos. ¿En qué parte de Ica o Chincha estás?")
    else:
        msg.body(f"Recibí: '{cuerpo_mensaje}'. Por ahora solo entiendo 'hola', pero pronto estaré conectado al inventario.")

    return str(twiml_response)