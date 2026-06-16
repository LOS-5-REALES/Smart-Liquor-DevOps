# app/main.py
import os
import re
import fastapi
import flet as ft
import flet_fastapi
import uvicorn
from fastapi.staticfiles import StaticFiles
from database import esperar_y_crear_tablas

app = fastapi.FastAPI(
    title="Smart Liquor - Core Dashboard",
    version="1.0"
)

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api", tags=["Diagnóstico"])
def read_root():
    return {"Smart_Liquor": "Backend Operativo vinculado a Supabase 🚀"}


async def app_con_login(page: ft.Page):
    page.title      = "Smart-Liquor DevOps"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0

    async def mostrar_login():
        from componentes.login_screen import build_login_screen
        await page.clean_async()
        page.padding = 0
        page.controls.append(
            build_login_screen(page=page, on_login_exitoso=mostrar_dashboard)
        )
        await page.update_async()

    async def mostrar_dashboard(usuario=None):
        from ui import main as build_dashboard
        try:
            await page.clean_async()
            page.padding = 25
            page.session.set("mostrar_login", mostrar_login)
            # Limpiamos estados de cliente al entrar al panel administrativo
            page.session.set("telefono_cliente_whatsapp", None)
            page.session.set("modo_catalogo", "admin")
            await build_dashboard(page)
            print(">>> Dashboard cargado OK")
        except Exception as ex:
            print(f">>> ERROR cargando dashboard: {ex}")
            import traceback
            traceback.print_exc()

    async def evaluar_ruta_y_desplegar(route_event=None):
        """
        Manejador dinámico y redundante encargado de estabilizar la sesión en 
        smartphones evitando ejecuciones cruzadas o caídas a pantallas vacías.
        """
        url_contexto = str(page.route or "")
        print(f"[FLET ROUTE DETECTED] Ruta cruda en navegación: {url_contexto}")

        # Intentar lectura nativa desde la query string primero para entornos estables
        telefono_cliente = page.query.get("telefono")
        modo_catalogo = page.query.get("modo", "ver")

        # Fallback de seguridad vía Regex si page.query viene vacío por wrappers webview de WhatsApp
        if not telefono_cliente:
            match_tel = re.search(r"telefono=([0-9]+)", url_contexto)
            if match_tel:
                telefono_cliente = match_tel.group(1)

        if url_contexto and not page.query.get("modo"):
            match_modo = re.search(r"modo=([a-zA-Z]+)", url_contexto)
            if match_modo:
                modo_catalogo = match_modo.group(1)

        # ── CONTROL DE FLUJO MULTIUSUARIO INMUTABLE ──
        if telefono_cliente:
            print(f"[MAIN CONTROL] Modo Catálogo Activo: {telefono_cliente} | Enfoque: {modo_catalogo}")
            from ui import main as build_dashboard
            
            # Guardamos de forma persistente los parámetros en la sesión del cliente
            page.session.set("telefono_cliente_whatsapp", telefono_cliente)
            page.session.set("modo_catalogo", modo_catalogo)
            
            await page.clean_async() 
            page.padding = 0
            await build_dashboard(page)
        else:
            # Prevención de sobreescritura accidental: si ya hay una sesión activa de cliente, evitamos mandarlo al login
            if page.session.get("telefono_cliente_whatsapp"):
                print("[MAIN CONTROL] Manteniendo sesión activa del cliente actual.")
                return
                
            print("[MAIN CONTROL] Acceso estándar detectado. Desplegando Login Administrativo.")
            page.session.set("modo_catalogo", "admin")
            await mostrar_login()

    # Desactivar temporalmente el listener para prevenir bucles de recarga en el primer renderizado móvil
    page.on_route_change = None
    await evaluar_ruta_y_desplegar(None)
    
    # Vincular formalmente una vez inicializada la vista base
    page.on_route_change = evaluar_ruta_y_desplegar


app.mount("/", flet_fastapi.app(app_con_login))

if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor en http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")