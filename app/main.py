# app/main.py
import os
import re
import fastapi
import flet as ft
import flet_fastapi
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from database import esperar_y_crear_tablas

app = fastapi.FastAPI(
    title="Smart Liquor - Core Dashboard",
    version="1.0"
)

if not os.path.exists("static"):
    os.makedirs("static")

# PDFs de reportes
app.mount("/static", StaticFiles(directory="static"), name="static")
# HTML pages (catalogo, whatsapp)
app.mount("/assets", StaticFiles(directory="app/static"), name="assets")
# Fuentes Flet
app.mount("/assets/fonts", StaticFiles(directory="app/static/fonts"), name="flet_fonts")


@app.get("/api", tags=["Diagnóstico"])
def read_root():
    return {"Smart_Liquor": "Backend Operativo vinculado a Supabase 🚀"}


# ── API Catálogo Cliente ──────────────────────────────────────
@app.get("/api/catalogo/productos")
def get_productos():
    try:
        from sqlalchemy.orm import Session
        from database import engine
        import models
        with Session(engine) as db:
            prods = db.query(models.Producto).filter(
                ~models.Producto.nombre.startswith("[DESCONTINUADO]")
            ).order_by(models.Producto.id.asc()).all()
            return JSONResponse(content=[{
                "id":           p.id,
                "nombre":       p.nombre,
                "precio_venta": float(p.precio_venta or 0),
                "stock_actual": p.stock_actual or 0,
                "stock_minimo": p.stock_minimo or 10,
            } for p in prods])
    except Exception as ex:
        return JSONResponse(content={"error": str(ex)}, status_code=500)


# ── API REST para Panel WhatsApp ──────────────────────────────
@app.get("/api/wa/conversaciones")
def get_conversaciones():
    try:
        from sqlalchemy.orm import Session
        from database import engine
        import models
        with Session(engine) as db:
            mensajes = db.query(models.MensajeWhatsapp)\
                .order_by(models.MensajeWhatsapp.fecha.desc()).all()
            conversaciones = {}
            for m in mensajes:
                if m.telefono not in conversaciones:
                    conversaciones[m.telefono] = []
                conversaciones[m.telefono].append({
                    "id":      m.id,
                    "mensaje": m.mensaje,
                    "origen":  m.origen,
                    "fecha":   m.fecha.strftime("%d/%m %H:%M") if m.fecha else "",
                    "leido":   m.leido,
                })
            result = []
            for tel, msgs in conversaciones.items():
                cliente = db.query(models.Cliente)\
                    .filter(models.Cliente.telefono == tel).first()
                no_leidos = sum(1 for m in msgs
                                if not m["leido"] and m["origen"] == "cliente")
                result.append({
                    "telefono":       tel,
                    "nombre":         (cliente.nombre_completo if cliente else tel) or tel,
                    "modo_agente":    cliente.modo_agente if cliente else False,
                    "no_leidos":      no_leidos,
                    "ultimo_mensaje": msgs[0]["mensaje"][:40] if msgs else "",
                })
            return JSONResponse(content=result)
    except Exception as ex:
        return JSONResponse(content={"error": str(ex)}, status_code=500)


@app.get("/api/wa/mensajes/{telefono}")
def get_mensajes(telefono: str):
    try:
        from sqlalchemy.orm import Session
        from database import engine
        import models
        with Session(engine) as db:
            db.query(models.MensajeWhatsapp).filter(
                models.MensajeWhatsapp.telefono == telefono,
                models.MensajeWhatsapp.leido == False,
            ).update({"leido": True})
            db.commit()
            mensajes = db.query(models.MensajeWhatsapp)\
                .filter(models.MensajeWhatsapp.telefono == telefono)\
                .order_by(models.MensajeWhatsapp.fecha.asc()).all()
            return JSONResponse(content=[{
                "id":      m.id,
                "mensaje": m.mensaje,
                "origen":  m.origen,
                "fecha":   m.fecha.strftime("%d/%m %H:%M") if m.fecha else "",
            } for m in mensajes])
    except Exception as ex:
        return JSONResponse(content={"error": str(ex)}, status_code=500)


@app.post("/api/wa/enviar")
async def enviar_mensaje(request: fastapi.Request):
    try:
        from sqlalchemy.orm import Session
        from database import engine
        import models
        import httpx
        from datetime import datetime, timezone
        data     = await request.json()
        telefono = data.get("telefono", "")
        mensaje  = data.get("mensaje", "")
        if not telefono or not mensaje:
            return JSONResponse(content={"error": "Faltan datos"}, status_code=400)
        TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
        TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        r = httpx.post(url, data={
            "From": TWILIO_FROM_NUMBER,
            "To":   f"whatsapp:+{telefono}",
            "Body": mensaje,
        }, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        if r.status_code == 201:
            with Session(engine) as db:
                cliente = db.query(models.Cliente)\
                    .filter(models.Cliente.telefono == telefono).first()
                db.add(models.MensajeWhatsapp(
                    telefono=telefono,
                    cliente_id=cliente.id if cliente else None,
                    mensaje=mensaje, origen="agente", leido=True,
                ))
                if cliente:
                    cliente.ultimo_mensaje = datetime.now(timezone.utc)
                db.commit()
            return JSONResponse(content={"ok": True})
        else:
            return JSONResponse(content={"error": r.text}, status_code=500)
    except Exception as ex:
        return JSONResponse(content={"error": str(ex)}, status_code=500)


@app.post("/api/wa/devolver/{telefono}")
async def devolver_al_bot(telefono: str):
    try:
        from sqlalchemy.orm import Session
        from database import engine
        import models
        import httpx
        with Session(engine) as db:
            c = db.query(models.Cliente)\
                .filter(models.Cliente.telefono == telefono).first()
            if c:
                c.modo_agente = False
                db.commit()
        TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
        TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        httpx.post(url, data={
            "From": TWILIO_FROM_NUMBER,
            "To":   f"whatsapp:+{telefono}",
            "Body": "✅ Has sido reconectado con el bot.\n\nEscribe *MENU* para ver las opciones.",
        }, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        return JSONResponse(content={"ok": True})
    except Exception as ex:
        return JSONResponse(content={"error": str(ex)}, status_code=500)


# ── App principal (dashboard + catalogo cliente) ──────────────
async def app_con_login(page: ft.Page):
    page.title      = "Smart-Liquor DevOps"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0

    async def limpiar_pagina():
        page.controls.clear()
        page.overlay.clear()
        page.bottom_appbar = None

    async def mostrar_login():
        from componentes.login_screen import build_login_screen
        await limpiar_pagina()
        page.padding = 0
        page.controls.append(
            build_login_screen(page=page, on_login_exitoso=mostrar_dashboard)
        )
        await page.update_async()

    async def mostrar_dashboard(usuario=None):
        from ui import main as build_dashboard
        try:
            await limpiar_pagina()
            page.padding = 0
            page.session.store.set("mostrar_login", mostrar_login)
            page.session.store.set("telefono_cliente_whatsapp", None)
            page.session.store.set("modo_catalogo", "admin")
            page.session.store.set("autenticado", True)
            await build_dashboard(page)
            print(">>> Dashboard Admin cargado OK")
        except Exception as ex:
            print(f">>> ERROR cargando dashboard: {ex}")
            import traceback
            traceback.print_exc()

    async def evaluar_ruta_y_desplegar(route_event=None):
        url_contexto = str(page.route or "")
        print(f"[ROUTE] Ruta detectada: {url_contexto}")

        telefono_cliente = None
        modo_catalogo    = "ver"

        match_tel = re.search(r"[?&]telefono=([^&\s]+)", url_contexto)
        if match_tel:
            telefono_cliente = match_tel.group(1).strip()

        match_modo = re.search(r"[?&]modo=([^&\s]+)", url_contexto)
        if match_modo:
            modo_catalogo = match_modo.group(1).strip()

        if not telefono_cliente:
            try:
                if page.query:
                    telefono_cliente = page.query.get("telefono")
                    modo_catalogo    = page.query.get("modo", "ver")
            except Exception as eq:
                print(f"[ROUTE] page.query no disponible: {eq}")

        if not telefono_cliente:
            try:
                tel_session  = page.session.store.get("telefono_cliente_whatsapp")
                modo_session = page.session.store.get("modo_catalogo") or "ver"
                if tel_session and modo_session != "admin":
                    telefono_cliente = tel_session
                    modo_catalogo    = modo_session
            except Exception as es:
                print(f"[ROUTE] Sesión no disponible: {es}")

        print(f"[ROUTE] telefono={telefono_cliente} | modo={modo_catalogo}")

        if telefono_cliente and str(telefono_cliente).strip():
            print(f"[ROUTE] Redirigiendo cliente a catalogo HTML...")
            # Redirigir al catalogo HTML en vez de Flet
            await page.launch_url_async(
                f"http://57.156.66.168:8000/assets/catalogo.html"
                f"?telefono={telefono_cliente}&modo={modo_catalogo}"
            )
        else:
            print("[ROUTE] Sin parámetros de cliente → verificando autenticación")
            page.session.store.set("modo_catalogo", "admin")
            try:
                autenticado = page.session.store.get("autenticado")
                print(f"[ROUTE] autenticado en sesion: {autenticado}")
            except Exception:
                autenticado = False
            if autenticado:
                print("[ROUTE] Sesión activa → cargando dashboard")
                await mostrar_dashboard()
            else:
                print("[ROUTE] Sin sesión → Login administrativo")
                await mostrar_login()

    page.on_route_change = evaluar_ruta_y_desplegar
    await evaluar_ruta_y_desplegar(None)

@app.get("/whatsapp", response_class=HTMLResponse)
def panel_whatsapp():
    ruta_html = os.path.join(os.path.dirname(__file__), "static", "whatsapp.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Panel no encontrado</h1>", status_code=404)


@app.get("/catalogo", response_class=HTMLResponse)
def catalogo_cliente():
    ruta_html = os.path.join(os.path.dirname(__file__), "static", "catalogo.html")
    if os.path.exists(ruta_html):
        with open(ruta_html, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Catálogo no encontrado</h1>", status_code=404)

# ── Montar rutas ──────────────────────────────────────────────
app.mount("/", flet_fastapi.app(app_con_login, assets_dir="app/flet_assets"))

if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor en http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")