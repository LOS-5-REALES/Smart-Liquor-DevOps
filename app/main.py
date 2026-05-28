# app/main.py
import os
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
            await build_dashboard(page)
            print(">>> Dashboard cargado OK")
        except Exception as ex:
            print(f">>> ERROR cargando dashboard: {ex}")
        import traceback
        traceback.print_exc()

    await mostrar_login()


app.mount("/", flet_fastapi.app(app_con_login))

if __name__ == "__main__":
    if esperar_y_crear_tablas():
        print("🚀 Iniciando Servidor en http://localhost:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("Error: No se pudo conectar a la base de datos.")