# app/ui.py
import asyncio
from datetime import datetime
import flet as ft
from sqlalchemy.orm import Session, joinedload
from database import engine
import models
import crud
from reports import generar_pdf_pedidos
from utils import parsear_fecha, filtrar_pedidos_por_fecha
from componentes import (
    build_metricas,
    build_filtro_fecha,
    build_modal_suministro,
    build_modal_producto,
    build_modal_editar,
    build_tarjeta_pedido,
    build_fila_inventario,
)


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


async def main(page: ft.Page):
    page.title = "Smart-Liquor DevOps - Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0d0f"
    page.padding = 25

    # ── Listas principales ────────────────────────────────────
    lista_pedidos_ui    = ft.Column(spacing=10, scroll="always")
    lista_inventario_ui = ft.Column(spacing=10, scroll="always")
    _todos_los_pedidos  = []

    # ── Metricas ──────────────────────────────────────────────
    txt_ventas, txt_pedidos, txt_alertas, row_metricas = build_metricas()

    # ── Modales ───────────────────────────────────────────────
    modal_suministro, abrir_suministro = build_modal_suministro(
        page=page,
        run_db=run_db,
        crud=crud,
        refrescar_datos=lambda: refrescar_datos(),
    )

    modal_crear, modal_eliminar, abrir_crear, abrir_eliminar = build_modal_producto(
        page=page,
        run_db=run_db,
        crud=crud,
        refrescar_datos=lambda: refrescar_datos(),
    )

    modal_editar, cargar_modal_editar = build_modal_editar(
        page=page,
        run_db=run_db,
        crud=crud,
        models=models,
        refrescar_datos=lambda: refrescar_datos(),
    )

    page.overlay.extend([modal_suministro, modal_crear, modal_eliminar, modal_editar])

    # ── Cambio de estado ──────────────────────────────────────
    async def cambiar_estado(pedido_id: int, nuevo_estado: str):
        await run_db(lambda db: crud.actualizar_estado_pedido(db, pedido_id, nuevo_estado))
        peds   = await run_db(lambda db: db.query(models.Pedido).all())
        ventas = sum(p.total_pedido for p in peds if p.total_pedido)
        txt_ventas.value  = f"S/ {ventas:,.2f}"
        txt_pedidos.value = str(len(peds))
        await page.update_async()

    # ── Construir lista de pedidos ────────────────────────────
    async def construir_lista_pedidos(peds):
        lista_pedidos_ui.controls.clear()
        if not peds:
            lista_pedidos_ui.controls.append(ft.Container(
                content=ft.Text(
                    "No hay pedidos en ese rango de fechas.",
                    color="grey", italic=True
                ),
                padding=20,
            ))
            return

        for p in peds:
            lista_pedidos_ui.controls.append(
                build_tarjeta_pedido(
                    p=p,
                    cambiar_estado=cambiar_estado,
                    cargar_modal_editar=cargar_modal_editar,
                    page=page,
                )
            )

    # ── Filtro por fecha ──────────────────────────────────────
    async def aplicar_filtro(e=None):
        txt_error_fecha.value = ""
        desde = parsear_fecha(inp_fecha_inicio.value)
        hasta = parsear_fecha(inp_fecha_fin.value)
        if desde and hasta and desde > hasta:
            txt_error_fecha.value = "La fecha inicio no puede ser mayor que la fecha fin."
            await page.update_async()
            return
        await construir_lista_pedidos(
            filtrar_pedidos_por_fecha(
                _todos_los_pedidos,
                inp_fecha_inicio.value,
                inp_fecha_fin.value,
            )
        )
        await page.update_async()

    async def ejecutar_reporte_pdf(e):
        txt_error_fecha.value = "Generando reporte..."
        await page.update_async()
        try:
            pedidos_para_pdf = filtrar_pedidos_por_fecha(
                _todos_los_pedidos,
                inp_fecha_inicio.value,
                inp_fecha_fin.value,
            )
            if not pedidos_para_pdf:
                txt_error_fecha.value = "No hay pedidos en este rango."
                await page.update_async()
                return
            rango = (
                f"{inp_fecha_inicio.value} a {inp_fecha_fin.value}"
                if inp_fecha_inicio.value else "General"
            )
            nombre_archivo = generar_pdf_pedidos(pedidos_para_pdf, rango)
            await page.launch_url_async(f"http://localhost:8000/static/{nombre_archivo}")
            txt_error_fecha.value = "Reporte generado."
        except Exception as ex:
            txt_error_fecha.value = f"Error PDF: {ex}"
        await page.update_async()

    async def limpiar_filtro(e=None):
        inp_fecha_inicio.value = inp_fecha_fin.value = txt_error_fecha.value = ""
        await construir_lista_pedidos(_todos_los_pedidos)
        await page.update_async()

    inp_fecha_inicio, inp_fecha_fin, txt_error_fecha, row_filtro = build_filtro_fecha(
        on_filtrar=aplicar_filtro,
        on_pdf=ejecutar_reporte_pdf,
        on_limpiar=limpiar_filtro,
    )

    # ── Refresco principal ────────────────────────────────────
    async def refrescar_datos(e=None):
        nonlocal _todos_los_pedidos
        try:
            prods = await run_db(lambda db: db.query(models.Producto).all())
            peds  = await run_db(lambda db: (
                db.query(models.Pedido)
                .options(
                    joinedload(models.Pedido.cliente),
                    joinedload(models.Pedido.items)
                        .joinedload(models.DetallePedido.producto),
                )
                .order_by(models.Pedido.id.desc())
                .all()
            ))

            _todos_los_pedidos = peds

            # Actualizar metricas
            criticos = [
                p for p in prods
                if (p.stock_actual or 0) <= (p.stock_minimo or 10)
            ]
            txt_alertas.value = str(len(criticos))
            txt_pedidos.value = str(len(peds))
            ventas = sum(p.total_pedido for p in peds if p.total_pedido)
            txt_ventas.value  = f"S/ {ventas:,.2f}"

            # Construir pedidos con filtro activo
            await construir_lista_pedidos(
                filtrar_pedidos_por_fecha(
                    peds,
                    inp_fecha_inicio.value,
                    inp_fecha_fin.value,
                )
            )

            # Construir inventario
            lista_inventario_ui.controls.clear()
            for pr in prods:
                lista_inventario_ui.controls.append(
                    build_fila_inventario(
                        pr=pr,
                        abrir_suministro=abrir_suministro,
                        abrir_eliminar=abrir_eliminar,
                    )
                )

            await page.update_async()

        except Exception as ex:
            print(f"[UI ERROR] {ex}")

    # ── Layout ────────────────────────────────────────────────
    await page.add_async(
        # Header
        ft.Row(controls=[
            ft.Column([
                ft.Text("Smart-Liquor Dashboard", size=28, weight="bold"),
                ft.Text("Logistica Chincha  •  Supabase Cloud", color="grey"),
            ]),
            ft.IconButton("refresh", on_click=refrescar_datos, tooltip="Actualizar"),
        ], alignment="spaceBetween"),

        ft.Divider(height=20, color="#232629"),

        # Metricas
        row_metricas,

        ft.Divider(height=20, color="#232629"),

        # Contenido principal
        ft.Row(controls=[
            # Columna pedidos
            ft.Column([
                ft.Text("Pedidos Recientes", size=18, weight="bold"),
                row_filtro,
                txt_error_fecha,
                ft.Container(content=lista_pedidos_ui, height=400),
            ], expand=2),

            # Columna inventario
            ft.Column([
                ft.Row([
                    ft.Text("Inventario", size=18, weight="bold", expand=True),
                    ft.ElevatedButton(
                        "+ Nuevo",
                        bgcolor="green",
                        color="white",
                        height=32,
                        on_click=lambda e: asyncio.ensure_future(abrir_crear()),
                    ),
                ], vertical_alignment="center"),
                ft.Container(content=lista_inventario_ui, height=450),
            ], expand=1),
        ], vertical_alignment="start", spacing=30),
    )

    await refrescar_datos()