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
    page.title      = "Smart-Liquor Admin Panel"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0
    page.scroll     = ft.ScrollMode.ADAPTIVE

    lista_pedidos_ui    = ft.Column(spacing=12, scroll=ft.ScrollMode.ADAPTIVE)
    lista_inventario_ui = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    _todos_los_pedidos  = []

    # ── Métricas ─────────────────────────────────────────────────────────────────────────────
    txt_ventas, txt_pedidos, txt_alertas, txt_pendientes, txt_entregados, row_metricas, actualizar_metricas = build_metricas()

    # ── Panel clientes ────────────────────────────────────────
    panel_clientes, refrescar_clientes = build_panel_clientes(
        page=page, run_db=run_db, models=models, crud=crud
    )

    # ── Modales ───────────────────────────────────────────────
    modal_suministro, abrir_suministro = build_modal_suministro(
        page=page, run_db=run_db, crud=crud,
        refrescar_datos=lambda e=None: page.run_task(refrescar_datos),
    )
    modal_crear, modal_eliminar, abrir_crear, abrir_eliminar = build_modal_producto(
        page=page, run_db=run_db, crud=crud,
        refrescar_datos=lambda e=None: page.run_task(refrescar_datos),
    )
    modal_editar, cargar_modal_editar = build_modal_editar(
        page=page, run_db=run_db, crud=crud, models=models,
        refrescar_datos=lambda e=None: page.run_task(refrescar_datos),
    )
    modal_pedido, abrir_modal_pedido = build_modal_pedido(
        page=page, run_db=run_db, crud=crud, models=models,
        refrescar_datos=lambda e=None: page.run_task(refrescar_datos),
    )
    page.overlay.extend([
        modal_suministro, modal_crear, modal_eliminar,
        modal_editar, modal_pedido,
    ])

    # ── Interceptores de Hilo Seguros (FastAPI Async Patch) ──
    def safe_cargar_modal_editar(pedido_id):
        page.run_task(cargar_modal_editar, pedido_id)

    def safe_abrir_suministro(producto_id):
        page.run_task(abrir_suministro, producto_id)

    def safe_abrir_eliminar(producto_id, producto_nombre):
        page.run_task(abrir_eliminar, producto_id, producto_nombre)

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
                                     cargar_modal_editar=safe_cargar_modal_editar, page=page)
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
            
            criticos = [p for p in prods if (p.stock_actual or 0) <= (p.stock_minimo or 10)]
            
            # ── 🛠️ UNIFICACIÓN LOGÍSTICA: Se removió "en ruta" para evitar duplicados ──
            pendientes = [p for p in peds_filtrados if p.estado_logistico in ("recibido", "en camino")]
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
                    build_fila_inventario(pr=pr, abrir_suministro=safe_abrir_suministro,
                                          abrir_eliminar=safe_abrir_eliminar)
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
                build_fila_inventario(pr, safe_abrir_suministro, safe_abrir_eliminar))
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

    # ── CONTROL DE VISTAS ────────────────────────────────────────────────────────────────────
    tab_index = {"actual": 0}
    contenido_central = ft.Container(padding=ft.padding.all(20), expand=True)

    def vista_pedidos():
        return ft.Column([
            ft.Text("Gestión de Pedidos", size=22, weight="bold", color="white"),
            ft.Container(content=col_filtro, padding=ft.padding.only(top=10, bottom=10)),
            txt_error_fecha,
            ft.Container(content=lista_pedidos_ui, expand=True)
        ], spacing=10, expand=True)

    def vista_inventario():
        return ft.Column([
            ft.Row([
                ft.Text("Control de Inventario", size=22, weight="bold", color="white", expand=True),
                # 🛠️ Corrección visual del doble más
                ft.ElevatedButton(
                    "Nuevo Producto", bgcolor="#2e7d32", color="white", height=40,
                    icon=ft.icons.ADD,
                    on_click=lambda e: page.run_task(abrir_crear)
                ),
            ], vertical_alignment="center"),
            ft.Container(
                content=ft.TextField(
                    hint_text="Buscar por nombre de licor...",
                    on_change=buscar_en_inventario,
                    border_color="#232629",
                    border_radius=12, height=45,
                    text_size=14, content_padding=12,
                    prefix_icon=ft.icons.SEARCH,
                    bgcolor="#111416"
                ),
                padding=ft.padding.only(top=10, bottom=10)
            ),
            ft.Container(content=lista_inventario_ui, expand=True)
        ], spacing=10, expand=True)

    def vista_clientes():
        return ft.Column([
            ft.Text("Directorio de Clientes", size=22, weight="bold", color="white"),
            ft.Container(height=10),
            ft.Container(content=panel_clientes, expand=True)
        ], expand=True)

    vistas = [vista_pedidos, vista_inventario, vista_clientes]

    async def cambiar_seccion(idx):
        tab_index["actual"] = idx
        
        # Sincronizar Sidebar (Desktop)
        for i, item in enumerate(sidebar_items.controls):
            if isinstance(item, ft.Container):
                is_selected = i == idx
                item.bgcolor = "#1a1f26" if is_selected else "transparent"
                item.content.controls[0].icon_color = "#2196f3" if is_selected else "grey"
                item.content.controls[1].color = "white" if is_selected else "grey"
        
        # Sincronizar Tabs (Mobile)
        for i, btn in enumerate(btn_tabs):
            btn.bgcolor = "#1a1f26" if i == idx else "#111416"
            btn.border = ft.border.all(1, "#2196f3" if i == idx else "#232629")

        contenido_central.content = vistas[idx]()
        await page.update_async()

    def handler_cambio_seccion(idx):
        return lambda e: page.run_task(cambiar_seccion, idx)

    # ── CONSTRUCCIÓN DE COMPONENTES DE ENTORNO ───────────────────────────────────────────────
    sidebar_items = ft.Column(spacing=8)
    menu_opciones = [
        ("Pedidos Recientes", ft.icons.RECEIPT_LONG),
        ("Inventario de Stock", ft.icons.INVENTORY_2),
        ("Base de Clientes", ft.icons.PEOPLE),
    ]

    for index, (label, icon) in enumerate(menu_opciones):
        sidebar_items.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(icon, color="grey", size=20),
                    ft.Text(label, color="grey", size=14, weight="w500"),
                ], spacing=12),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border_radius=8,
                bgcolor="transparent",
                on_click=handler_cambio_seccion(index)
            )
        )

    sidebar_panel = ft.Container(
        width=240,
        bgcolor="#0f1214",
        padding=ft.padding.all(16),
        border=ft.Border(right=ft.BorderSide(1, "#1a1d20")),
        content=ft.Column([
            ft.Column([
                ft.Text("Smart-Liquor", size=20, weight="bold", color="white"),
                ft.Text("Logística Chincha v2", color="grey", size=11),
            ], spacing=2),
            ft.Divider(height=30, color="#1a1d20"),
            sidebar_items,
            ft.Spacer(),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.LOGOUT, color="red_accent", size=18),
                    ft.Text("Cerrar Sesión", color="red_accent", size=14),
                ], spacing=12),
                padding=ft.padding.all(10),
                border_radius=8,
                on_click=lambda e: page.run_task(cerrar_sesion)
            )
        ])
    )

    btn_tabs = []
    for i, (label, icon) in enumerate(menu_opciones):
        btn = ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=16, color="white"),
                ft.Text(label, size=12, color="white", weight="bold")
            ], alignment="center", spacing=6),
            bgcolor="#111416",
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=8,
            border=ft.border.all(1, "#232629"),
            on_click=handler_cambio_seccion(i),
            expand=True
        )
        btn_tabs.append(btn)

    layout_movil = ft.Column([
        ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            content=ft.Row(btn_tabs, spacing=6)
        ),
        ft.Divider(height=1, color="#1a1d20"),
        contenido_central
    ], spacing=4, expand=True)

    layout_desktop = ft.Row([
        sidebar_panel,
        contenido_central
    ], spacing=0, expand=True)

    # ── SISTEMA RESPONSIVO INTEGRADO ──
    layout_sistema = ft.ResponsiveRow(
        controls=[
            ft.Container(
                content=sidebar_panel,
                col={"sm": 0, "md": 3, "lg": 2.5},
            ),
            ft.Container(
                content=contenido_central,
                col={"sm": 12, "md": 9, "lg": 9.5},
            )
        ],
        spacing=0
    )

    def actualizar_layout():
        ancho = page.width if (page.width and page.width > 0) else 1200
        if ancho >= 950:
            layout_sistema.controls[0].visible = True
            contenido_central.content = vistas[tab_index["actual"]]()
        else:
            layout_sistema.controls[0].visible = False
            contenido_central.content = layout_movil

    async def on_resize(e):
        actualizar_metricas(page.width)
        actualizar_layout()
        await page.update_async()

    page.on_resize = on_resize

    header_acciones = ft.Container(
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        bgcolor="#0f1214",
        border=ft.Border(bottom=ft.BorderSide(1, "#1a1d20")),
        content=ft.Row([
            ft.Container(
                content=ft.Column([
                    ft.Text("Smart-Liquor", size=18, weight="bold"),
                    ft.Text("Panel de Administración", color="grey", size=10),
                ]),
            ),
            ft.Row([
                ft.ElevatedButton(
                    "Crear Pedido", bgcolor="#1565c0", color="white",
                    height=38, icon=ft.icons.ADD_SHOPPING_CART,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: page.run_task(abrir_modal_pedido),
                ),
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: page.run_task(refrescar_datos),
                              bgcolor="#111416", icon_color="white", icon_size=18),
            ], spacing=8),
        ], alignment="spaceBetween"),
    )

    page.controls.clear()
    page.controls.extend([
        header_acciones,
        ft.Container(content=row_metricas, padding=ft.padding.symmetric(horizontal=20, vertical=10)),
        ft.Divider(height=1, color="#1a1d20"),
        ft.Container(content=layout_sistema, expand=True, height=730),
    ])

    actualizar_metricas(1200)
    actualizar_layout()

    await cambiar_seccion(0)
    await refrescar_datos()