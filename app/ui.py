# app/ui.py
import asyncio
import os
import flet as ft
from sqlalchemy.orm import Session, joinedload
from database import engine
import models
import crud
from reports import generar_pdf_pedidos
from utils import parsear_fecha, filtrar_pedidos_por_fecha
from constants import ESTADOS_LOGISTICOS
from componentes import (
    build_metricas,
    build_filtro_fecha,
    build_modal_suministro,
    build_modal_producto,
    build_modal_editar,
    build_tarjeta_pedido,
    build_fila_inventario,
    build_panel_clientes,
    build_modal_pedido,
)


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


async def main(page: ft.Page):
    page.title      = "Smart-Liquor Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0
    page.scroll     = ft.ScrollMode.ADAPTIVE

    lista_pedidos_ui    = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    lista_inventario_ui = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    _todos_los_pedidos  = []

    # ── Metricas ──────────────────────────────────────────────
    txt_ventas, txt_pedidos, txt_alertas, txt_pendientes, txt_entregados, row_metricas, actualizar_metricas = build_metricas()

    # ── Panel clientes ────────────────────────────────────────
    panel_clientes, refrescar_clientes = build_panel_clientes(
        page=page, run_db=run_db, models=models, crud=crud
    )

    # ── Modales ───────────────────────────────────────────────
    modal_suministro, abrir_suministro = build_modal_suministro(
        page=page, run_db=run_db, crud=crud,
        refrescar_datos=lambda e=None: asyncio.create_task(refrescar_datos()),
    )
    modal_crear, modal_eliminar, abrir_crear, abrir_eliminar = build_modal_producto(
        page=page, run_db=run_db, crud=crud,
        refrescar_datos=lambda e=None: asyncio.create_task(refrescar_datos()),
    )
    modal_editar, cargar_modal_editar = build_modal_editar(
        page=page, run_db=run_db, crud=crud, models=models,
        refrescar_datos=lambda e=None: asyncio.create_task(refrescar_datos()),
    )
    modal_pedido, abrir_modal_pedido = build_modal_pedido(
        page=page, run_db=run_db, crud=crud, models=models,
        refrescar_datos=lambda e=None: asyncio.create_task(refrescar_datos()),
    )
    page.overlay.extend([
        modal_suministro, modal_crear, modal_eliminar,
        modal_editar, modal_pedido,
    ])

    # ── Cambio de estado ──────────────────────────────────────
    async def cambiar_estado(pedido_id: int, nuevo_estado: str):
        await run_db(lambda db: crud.actualizar_estado_pedido(db, pedido_id, nuevo_estado))
        peds   = await run_db(lambda db: db.query(models.Pedido).all())
        ventas = sum(p.total_pedido for p in peds if p.total_pedido)
        txt_ventas.value  = f"S/ {ventas:,.2f}"
        txt_pedidos.value = str(len(peds))
        await page.update_async()

    # ── Lista de pedidos ──────────────────────────────────────
    async def construir_lista_pedidos(peds):
        lista_pedidos_ui.controls.clear()
        if not peds:
            lista_pedidos_ui.controls.append(ft.Container(
                content=ft.Text("No hay pedidos en ese rango.", color="grey", italic=True),
                padding=20,
            ))
            return
        for p in peds:
            lista_pedidos_ui.controls.append(
                build_tarjeta_pedido(p=p, cambiar_estado=cambiar_estado,
                                     cargar_modal_editar=cargar_modal_editar, page=page)
            )

    # ── Filtro fecha ──────────────────────────────────────────
    async def aplicar_filtro(e=None):
        txt_error_fecha.value = ""
        desde = parsear_fecha(inp_fecha_inicio.value)
        hasta = parsear_fecha(inp_fecha_fin.value)
        if desde and hasta and desde > hasta:
            txt_error_fecha.value = "La fecha inicio no puede ser mayor que la fecha fin."
            await page.update_async()
            return
        await construir_lista_pedidos(
            filtrar_pedidos_por_fecha(_todos_los_pedidos,
                                      inp_fecha_inicio.value, inp_fecha_fin.value)
        )
        await page.update_async()

    async def ejecutar_reporte_pdf(e):
        txt_error_fecha.value = "Generando reporte..."
        await page.update_async()
        try:
            pedidos_para_pdf = filtrar_pedidos_por_fecha(
                _todos_los_pedidos, inp_fecha_inicio.value, inp_fecha_fin.value)
            if not pedidos_para_pdf:
                txt_error_fecha.value = "No hay pedidos en este rango."
                await page.update_async()
                return
            rango = (f"{inp_fecha_inicio.value} a {inp_fecha_fin.value}"
                     if inp_fecha_inicio.value else "General")
            nombre_archivo = generar_pdf_pedidos(pedidos_para_pdf, rango)
            BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
            await page.launch_url_async(f"{BASE_URL}/static/{nombre_archivo}")
            txt_error_fecha.value = "Reporte generado."
        except Exception as ex:
            txt_error_fecha.value = f"Error PDF: {ex}"
        await page.update_async()

    async def limpiar_filtro(e=None):
        inp_fecha_inicio.value = inp_fecha_fin.value = txt_error_fecha.value = ""
        await construir_lista_pedidos(_todos_los_pedidos)
        await page.update_async()

    inp_fecha_inicio, inp_fecha_fin, txt_error_fecha, col_filtro = build_filtro_fecha(
        on_filtrar=aplicar_filtro, on_pdf=ejecutar_reporte_pdf, on_limpiar=limpiar_filtro,
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
                .order_by(models.Pedido.id.desc()).all()
            ))
            _todos_los_pedidos = peds
            peds_filtrados = filtrar_pedidos_por_fecha(
                peds, inp_fecha_inicio.value, inp_fecha_fin.value)
            criticos   = [p for p in prods if (p.stock_actual or 0) <= (p.stock_minimo or 10)]
            pendientes = [p for p in peds_filtrados if p.estado_logistico in ("recibido", "en camino", "en ruta")]
            entregados = [p for p in peds_filtrados if p.estado_logistico == "entregado"]
            ventas     = sum(p.total_pedido for p in peds_filtrados if p.total_pedido)
            txt_alertas.value    = str(len(criticos))
            txt_pedidos.value    = str(len(peds_filtrados))
            txt_ventas.value     = f"S/ {ventas:,.2f}"
            txt_pendientes.value = str(len(pendientes))
            txt_entregados.value = str(len(entregados))
            await construir_lista_pedidos(peds_filtrados)
            lista_inventario_ui.controls.clear()
            for pr in prods:
                lista_inventario_ui.controls.append(
                    build_fila_inventario(pr=pr, abrir_suministro=abrir_suministro,
                                         abrir_eliminar=abrir_eliminar)
                )
            await refrescar_clientes()
            await page.update_async()
        except Exception as ex:
            print(f"[UI ERROR] {ex}")

    async def buscar_en_inventario(e):
        termino = e.control.value.lower()
        prods   = await run_db(lambda db: db.query(models.Producto).all())
        prods_f = prods if not termino else [p for p in prods if termino in p.nombre.lower()]
        lista_inventario_ui.controls.clear()
        for pr in prods_f:
            lista_inventario_ui.controls.append(
                build_fila_inventario(pr, abrir_suministro, abrir_eliminar))
        await page.update_async()

    async def cerrar_sesion(e=None):
        try:
            from auth import logout
            logout()
        except Exception:
            pass
        mostrar_login = page.session.get("mostrar_login")
        if mostrar_login:
            await mostrar_login()

    # ── Pestañas para movil ───────────────────────────────────
    tab_index = {"actual": 0}
    contenido_tab = ft.Container(padding=ft.padding.all(12))

    def vista_pedidos():
        return ft.Column([
            col_filtro,
            txt_error_fecha,
            lista_pedidos_ui,
        ], spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)

    def vista_inventario():
        return ft.Column([
            ft.Row([
                ft.Text("Inventario", size=18, weight="bold", expand=True),
                ft.ElevatedButton(
                    "+ Nuevo", bgcolor="green", color="white", height=32,
                    on_click=lambda e: asyncio.create_task(abrir_crear())
                ),
            ], vertical_alignment="center"),
            ft.TextField(
                hint_text="Buscar producto...",
                on_change=buscar_en_inventario,
                border_radius=20, height=40,
                text_size=14, content_padding=10,
                prefix_icon=ft.icons.SEARCH,
            ),
            lista_inventario_ui,
        ], spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)

    def vista_clientes():
        return ft.Column([panel_clientes], expand=True)

    vistas = [vista_pedidos, vista_inventario, vista_clientes]

    # Botones de pestaña
    btn_tabs = []

    async def cambiar_tab(idx):
        tab_index["actual"] = idx
        # Actualizar estilos de botones
        for i, btn in enumerate(btn_tabs):
            btn.bgcolor  = "#1F4E79" if i == idx else "#16191c"
            btn.color    = "white"
        contenido_tab.content = vistas[idx]()
        await page.update_async()

    tabs_config = [
        ("Pedidos",    "receipt_long"),
        ("Inventario", "inventory_2"),
        ("Clientes",   "people"),
    ]
    for i, (label, icon) in enumerate(tabs_config):
        idx = i
        btn = ft.ElevatedButton(
            label, icon=icon,
            bgcolor="#1F4E79" if i == 0 else "#16191c",
            color="white",
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
            on_click=lambda e, i=idx: asyncio.create_task(cambiar_tab(i)),
        )
        btn_tabs.append(btn)

    # Vista inicial
    contenido_tab.content = vista_pedidos()

    # ── Layout desktop (>= 900px) ─────────────────────────────
    layout_desktop = ft.Row([
        ft.Column([
            ft.Text("Pedidos Recientes", size=16, weight="bold"),
            col_filtro,
            txt_error_fecha,
            ft.Container(content=lista_pedidos_ui, expand=True),
        ], spacing=10, expand=2),
        ft.Column([
            ft.Row([
                ft.Text("Inventario", size=16, weight="bold", expand=True),
                ft.ElevatedButton(
                    "+ Nuevo", bgcolor="green", color="white", height=30,
                    on_click=lambda e: asyncio.create_task(abrir_crear())
                ),
            ], vertical_alignment="center"),
            ft.TextField(
                hint_text="Buscar producto...", on_change=buscar_en_inventario,
                border_radius=20, height=38, text_size=13,
                content_padding=8, prefix_icon=ft.icons.SEARCH,
            ),
            ft.Container(content=lista_inventario_ui, expand=True),
        ], spacing=10, expand=1),
        ft.Column([panel_clientes], expand=1),
    ], vertical_alignment="start", spacing=20, expand=True)

    # ── Layout movil (< 900px) con pestañas ───────────────────
    layout_movil = ft.Column([
        ft.Row(btn_tabs, spacing=6, wrap=True),
        ft.Divider(height=8, color="#232629"),
        contenido_tab,
    ], spacing=8, expand=True)

    # Contenedor que cambia entre desktop y movil
    layout_wrapper = ft.Container(
        padding=ft.padding.all(12),
        expand=True,
    )

    def actualizar_layout():
        ancho = page.width or 1200
        if ancho >= 900:
            layout_wrapper.content = layout_desktop
        else:
            layout_wrapper.content = layout_movil

    async def on_resize(e):
        actualizar_metricas(page.width)
        actualizar_layout()
        await page.update_async()

    page.on_resize = on_resize
    actualizar_metricas(page.width)
    actualizar_layout()

    # ── Header ────────────────────────────────────────────────
    header = ft.Container(
        padding=ft.padding.symmetric(horizontal=15, vertical=10),
        bgcolor="#0f1214",
        content=ft.Row([
            ft.Column([
                ft.Text("Smart-Liquor", size=20, weight="bold"),
                ft.Text("Logistica Chincha • Supabase", color="grey", size=10),
            ]),
            ft.Row([
                ft.ElevatedButton(
                    "+ Pedido", bgcolor="#1565c0", color="white",
                    height=30, icon="add_shopping_cart",
                    on_click=lambda e: asyncio.create_task(abrir_modal_pedido()),
                ),
                ft.IconButton("refresh", on_click=refrescar_datos,
                              tooltip="Actualizar", icon_size=20),
                ft.IconButton("logout", icon_color="red",
                              tooltip="Cerrar sesion", icon_size=20,
                              on_click=lambda e: asyncio.create_task(cerrar_sesion(e))),
            ], spacing=4),
        ], alignment="spaceBetween"),
    )

    # ── Metricas compactas ────────────────────────────────────
    metricas_container = ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        content=row_metricas,
    )

    page.controls.extend([
        header,
        ft.Divider(height=1, color="#1a1d20"),
        metricas_container,
        ft.Divider(height=1, color="#1a1d20"),
        layout_wrapper,
    ])

    await page.update_async()
    await refrescar_datos()