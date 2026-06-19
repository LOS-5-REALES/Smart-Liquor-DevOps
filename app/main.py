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

    async def limpiar_pagina():
        """Limpia controles, overlay y bottomappbar de forma segura."""
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
            page.session.set("mostrar_login", mostrar_login)
            page.session.set("telefono_cliente_whatsapp", None)
            page.session.set("modo_catalogo", "admin")
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

        # Método 1: Regex sobre la URL
        match_tel = re.search(r"[?&]telefono=([^&\s]+)", url_contexto)
        if match_tel:
            telefono_cliente = match_tel.group(1).strip()

        match_modo = re.search(r"[?&]modo=([^&\s]+)", url_contexto)
        if match_modo:
            modo_catalogo = match_modo.group(1).strip()

        # Método 2: page.query como fallback
        if not telefono_cliente:
            try:
                if page.query:
                    telefono_cliente = page.query.get("telefono")
                    modo_catalogo    = page.query.get("modo", "ver")
            except Exception as eq:
                print(f"[ROUTE] page.query no disponible: {eq}")

        # Método 3: Sesión persistente
        if not telefono_cliente:
            try:
                telefono_cliente = page.session.get("telefono_cliente_whatsapp")
                modo_catalogo    = page.session.get("modo_catalogo") or "ver"
            except Exception as es:
                print(f"[ROUTE] Sesión no disponible: {es}")

        print(f"[ROUTE] telefono={telefono_cliente} | modo={modo_catalogo}")

        if telefono_cliente and str(telefono_cliente).strip():
            print(f"[ROUTE] Cargando catálogo para cliente: {telefono_cliente}")
            try:
                page.session.set("telefono_cliente_whatsapp", str(telefono_cliente))
                page.session.set("modo_catalogo", str(modo_catalogo))
                from ui import main as build_dashboard
                await limpiar_pagina()
                page.padding = 0
                await build_dashboard(page)
            except Exception as ex:
                print(f"[ROUTE ERROR] {ex}")
                import traceback
                traceback.print_exc()
                await limpiar_pagina()
                page.controls.append(
                    ft.Container(
                        expand=True, bgcolor="#0b0d0f",
                        content=ft.Column(
                            alignment="center",
                            horizontal_alignment="center",
                            expand=True,
                            controls=[
                                ft.Icon("local_bar", size=64, color="amber"),
                                ft.Text("Smart-Liquor", size=28,
                                        weight="bold", color="white"),
                                ft.Text("Cargando catálogo...", color="grey"),
                                ft.ProgressRing(color="amber"),
                            ]
                        )
                    )
                )
                await page.update_async()
        else:
            print("[ROUTE] Sin parámetros de cliente → Login administrativo")
            page.session.set("modo_catalogo", "admin")
            await mostrar_login()

    page.on_route_change = evaluar_ruta_y_desplegar
    await evaluar_ruta_y_desplegar(None)


app.mount("/", flet_fastapi.app(app_con_login))

if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor en http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")