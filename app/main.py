from fastapi import FastAPI, Form, Response  # <--- IMPORTANTE: Agregamos Form y Response
from app.bot import procesar_mensaje

app = FastAPI()

@app.get("/")
def read_root():
    return {"Smart_Liquor": "Sistema Operativo y Alineado 🚀"}

#------------------------------------------------------------------------------
@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(...)): # Ahora Form sí existe
    print(f"Mensaje recibido: {Body}") 
    respuesta_xml = procesar_mensaje(Body)
    # Ahora Response sí existe
    return Response(content=respuesta_xml, media_type="application/xml")
#-------------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    # Host 0.0.0.0 y puerto 8000 para que ngrok lo vea
    uvicorn.run(app, host="0.0.0.0", port=8000)