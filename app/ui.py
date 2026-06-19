# app/ui.py
import asyncio
import os
import urllib.parse
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

NUMERO_BOT_WHATSAPP = "14155238886"
BASE_URL            = os.getenv("BASE_URL", "http://localhost:8000")


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


async def main(page: ft.Page):
    page.title      = "Smart-Liquor"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0
    page.scroll     = ft.ScrollMode.ADAPTIVE

    try:
        telefono_cliente = page.session.get("telefono_cliente_whatsapp") if page.session else None
        modo_catalogo    = page.session.get("modo_catalogo") if page.session else "ver"
        if not telefono_cliente and page.query:
            telefono_cliente = page.query.get("telefono")
            modo_catalogo    = page.query.get("modo", "ver")
    except Exception as e:
        print(f"[UI SESSION WARNING] {e}")
        telefono_cliente = None
        modo_catalogo    = "ver"

    es_modo_cliente = telefono_cliente is not None and str(telefono_cliente).strip() != ""

    if es_modo_cliente:
        print(f"[UI] Modo Cliente: {telefono_cliente} | {modo_catalogo}")
        await cargar_interfaz_cliente(page, str(telefono_cliente), str(modo_catalogo))
        return

    # ── INTERFAZ ADMINISTRATIVA ───────────────────────────────
    lista_pedidos_ui    = ft.Column(spacing=12, scroll=ft.ScrollMode.ADAPTIVE)
    lista_inventario_ui = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE)
    _todos_los_pedidos  = []

    txt_ventas, txt_pedidos, txt_alertas, txt_pendientes, txt_entregados, row_metricas, actualizar_metricas = build_metricas()

    panel_clientes, refrescar_clientes = build_panel_clientes(
        page=page, run_db=run_db, models=models, crud=crud
    )

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

    def safe_cargar_modal_editar(pedido_id):
        page.run_task(cargar_modal_editar, pedido_id)

    def safe_abrir_suministro(producto_id):
        page.run_task(abrir_suministro, producto_id)

    def safe_abrir_eliminar(producto_id, producto_nombre):
        page.run_task(abrir_eliminar, producto_id, producto_nombre)

    async def cambiar_estado(pedido_id: int, nuevo_estado: str):
        await run_db(lambda db: crud.actualizar_estado_pedido(db, pedido_id, nuevo_estado))
        peds   = await run_db(lambda db: db.query(models.Pedido).all())
        ventas = sum(p.total_pedido for p in peds if p.total_pedido)
        txt_ventas.value  = f"S/ {ventas:,.2f}"
        txt_pedidos.value = str(len(peds))
        await page.update_async()

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
        print("[CERRAR SESION] Iniciando...")
        try:
            from auth import logout
            logout()
        except Exception:
            pass
        page.session.set("telefono_cliente_whatsapp", None)
        page.session.set("modo_catalogo", "admin")
        page.controls.clear()
        page.overlay.clear()
        page.bottom_appbar = None
        page.scroll  = None
        page.padding = 0
        page.bgcolor = "#0b0d0f"
        from componentes.login_screen import build_login_screen
        async def on_login(usuario=None):
            from ui import main as build_dashboard
            page.controls.clear()
            page.overlay.clear()
            page.bottom_appbar = None
            page.session.set("telefono_cliente_whatsapp", None)
            page.session.set("modo_catalogo", "admin")
            page.session.set("mostrar_login", cerrar_sesion)
            await build_dashboard(page)
        page.controls.append(
            build_login_screen(page=page, on_login_exitoso=on_login)
        )
        await page.update_async()
        print("[CERRAR SESION] Done")

    tab_index = {"actual": 0}
    contenido_central = ft.Container(
        padding=ft.padding.all(16),
        expand=True,
    )

    # ── Vistas ────────────────────────────────────────────────
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
                ft.Text("Control de Inventario", size=22, weight="bold",
                        color="white", expand=True),
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
                    border_color="#232629", border_radius=12, height=45,
                    text_size=14, content_padding=12,
                    prefix_icon=ft.icons.SEARCH, bgcolor="#111416"
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
        for i, item in enumerate(sidebar_items.controls):
            if isinstance(item, ft.Container):
                is_selected = i == idx
                item.bgcolor = "#1a1f26" if is_selected else "transparent"
                item.content.controls[0].icon_color = "#2196f3" if is_selected else "grey"
                item.content.controls[1].color = "white" if is_selected else "grey"
        for i, btn in enumerate(btn_tabs):
            btn.bgcolor = "#1a1f26" if i == idx else "#111416"
            btn.border  = ft.border.all(1, "#2196f3" if i == idx else "#232629")
        contenido_central.content = vistas[idx]()
        await page.update_async()

    def handler_cambio_seccion(idx):
        return lambda e: page.run_task(cambiar_seccion, idx)

    sidebar_items = ft.Column(spacing=8)
    menu_opciones = [
        ("Pedidos Recientes",   ft.icons.RECEIPT_LONG),
        ("Inventario de Stock", ft.icons.INVENTORY_2),
        ("Base de Clientes",    ft.icons.PEOPLE),
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
            ft.Divider(height=20, color="#1a1d20"),
            sidebar_items,
            ft.Divider(height=20, color="#1a1d20"),
            # Boton Panel WhatsApp en sidebar
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.CHAT, color="#25D366", size=18),
                    ft.Text("Panel WhatsApp", color="#25D366", size=14),
                ], spacing=12),
                padding=ft.padding.all(10),
                border_radius=8,
                bgcolor="#0b2a1a",
                border=ft.border.all(1, "#25D366"),
                on_click=lambda e: asyncio.ensure_future(
                    page.launch_url_async(f"{BASE_URL}/whatsapp")
                ),
            ),
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

    # Boton WhatsApp para movil
    btn_whatsapp_movil = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.CHAT, size=16, color="#25D366"),
            ft.Text("WA", size=12, color="#25D366", weight="bold"),
        ], alignment="center", spacing=4),
        bgcolor="#0b2a1a",
        padding=ft.padding.symmetric(horizontal=10, vertical=10),
        border_radius=8,
        border=ft.border.all(1, "#25D366"),
        on_click=lambda e: asyncio.ensure_future(
            page.launch_url_async(f"{BASE_URL}/whatsapp")
        ),
    )

    btn_cerrar_sesion_movil = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.LOGOUT, color="red_accent", size=16),
            ft.Text("Salir", color="red_accent", size=12),
        ], spacing=4),
        bgcolor="#111416",
        padding=ft.padding.symmetric(horizontal=10, vertical=8),
        border_radius=8,
        border=ft.border.all(1, "#c62828"),
        on_click=lambda e: page.run_task(cerrar_sesion),
    )

    layout_movil = ft.Column([
        ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=5),
            content=ft.Row([
                *btn_tabs,
                btn_whatsapp_movil,
                btn_cerrar_sesion_movil,
            ], spacing=4, wrap=True)
        ),
        ft.Divider(height=1, color="#1a1d20"),
        contenido_central,
    ], spacing=4, expand=True)

    layout_sistema = ft.ResponsiveRow(
        controls=[
            ft.Container(content=sidebar_panel, col={"sm": 0, "md": 3, "lg": 2.5}),
            ft.Container(content=contenido_central, col={"sm": 12, "md": 9, "lg": 9.5})
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
            ft.Column([
                ft.Text("Smart-Liquor", size=18, weight="bold"),
                ft.Text("Panel de Administración", color="grey", size=10),
            ]),
            ft.Row([
                ft.ElevatedButton(
                    "Crear Pedido", bgcolor="#1565c0", color="white",
                    height=38, icon=ft.icons.ADD_SHOPPING_CART,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: page.run_task(abrir_modal_pedido),
                ),
                ft.ElevatedButton(
                    "WhatsApp", bgcolor="#25D366", color="white",
                    height=38, icon=ft.icons.CHAT,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=lambda e: asyncio.ensure_future(
                        page.launch_url_async(f"{BASE_URL}/whatsapp")
                    ),
                ),
                ft.IconButton(ft.icons.REFRESH,
                              on_click=lambda e: page.run_task(refrescar_datos),
                              bgcolor="#111416", icon_color="white", icon_size=18),
                ft.IconButton(
                    ft.icons.LOGOUT,
                    icon_color="red_accent", icon_size=18,
                    tooltip="Cerrar sesión",
                    on_click=lambda e: page.run_task(cerrar_sesion),
                ),
            ], spacing=8),
        ], alignment="spaceBetween"),
    )

    page.controls.clear()
    page.controls.extend([
        header_acciones,
        ft.Container(content=row_metricas,
                     padding=ft.padding.symmetric(horizontal=20, vertical=10)),
        ft.Divider(height=1, color="#1a1d20"),
        ft.Container(content=layout_sistema, expand=True, height=730),
    ])

    actualizar_metricas(1200)
    actualizar_layout()
    await cambiar_seccion(0)
    await refrescar_datos()


# ── INTERFAZ DEL CLIENTE ──────────────────────────────────────
async def cargar_interfaz_cliente(page: ft.Page, telefono: str, modo: str = "ver"):
    page.scroll = ft.ScrollMode.ADAPTIVE

    grid_productos_ui      = ft.Column(spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    carrito_compra         = {}
    txt_checkout           = ft.Text("", color="white", size=14, weight="bold")
    btn_checkout_container = ft.Container(visible=False)

    async def enviar_carrito_a_whatsapp(e):
        if not carrito_compra:
            return
        lineas = []
        for prod_id, item in carrito_compra.items():
            lineas.append(f"PEDIDO_WEB:ID={prod_id}|CANT={item['cantidad']}")
        mensaje_formateado = "\n".join(lineas)
        mensaje_encoded    = urllib.parse.quote(mensaje_formateado)
        url_whatsapp       = f"https://wa.me/{NUMERO_BOT_WHATSAPP}?text={mensaje_encoded}"
        await page.launch_url_async(url_whatsapp)

    async def actualizar_ui_checkout():
        if modo == "ver" or not carrito_compra:
            btn_checkout_container.visible = False
        else:
            total_items  = sum(i["cantidad"] for i in carrito_compra.values())
            total_precio = sum(i["precio"] * i["cantidad"] for i in carrito_compra.values())
            txt_checkout.value = (
                f"🛒 {total_items} item(s) — S/ {total_precio:.2f}  |  Confirmar Pedido"
            )
            btn_checkout_container.visible = True
        await page.update_async()

    def modificar_unidades(producto, operacion, txt_contador):
        p_id = producto.id
        if p_id not in carrito_compra and operacion == "suma":
            carrito_compra[p_id] = {
                "nombre":   producto.nombre,
                "precio":   float(producto.precio_venta or 0.0),
                "cantidad": 1,
            }
            txt_contador.value   = "1"
            txt_contador.visible = True
        elif p_id in carrito_compra:
            cantidad_actual = carrito_compra[p_id]["cantidad"]
            if operacion == "suma" and cantidad_actual < 50:
                carrito_compra[p_id]["cantidad"] += 1
                txt_contador.value = str(carrito_compra[p_id]["cantidad"])
            elif operacion == "resta":
                if cantidad_actual > 1:
                    carrito_compra[p_id]["cantidad"] -= 1
                    txt_contador.value = str(carrito_compra[p_id]["cantidad"])
                else:
                    del carrito_compra[p_id]
                    txt_contador.value   = "0"
                    txt_contador.visible = False
        page.run_task(actualizar_ui_checkout)

    async def renderizar_catalogo_cliente(termino=""):
        try:
            grid_productos_ui.controls.clear()
            prods = await run_db(lambda db: db.query(models.Producto).filter(
                ~models.Producto.nombre.startswith("[DESCONTINUADO]")
            ).order_by(models.Producto.id.asc()).all())
            if termino:
                prods = [p for p in prods if termino in p.nombre.lower()]
            if not prods:
                grid_productos_ui.controls.append(ft.Container(
                    content=ft.Text("No se encontraron licores.", color="grey", italic=True),
                    padding=20, alignment=ft.alignment.center
                ))
                await page.update_async()
                return
            for p in prods:
                precio       = float(p.precio_venta or 0.0)
                txt_unidades = ft.Text("0", size=14, weight="bold",
                                       color="#fbbf24", visible=False)
                if p.id in carrito_compra:
                    txt_unidades.value   = str(carrito_compra[p.id]["cantidad"])
                    txt_unidades.visible = True
                controles_carrito = ft.Row([
                    ft.IconButton(
                        icon=ft.icons.REMOVE_CIRCLE_OUTLINE,
                        icon_color="grey_400", icon_size=20,
                        on_click=lambda e, prod=p, txt=txt_unidades:
                            modificar_unidades(prod, "resta", txt)
                    ),
                    txt_unidades,
                    ft.IconButton(
                        icon=ft.icons.ADD_CIRCLE,
                        icon_color="#fbbf24", icon_size=24,
                        on_click=lambda e, prod=p, txt=txt_unidades:
                            modificar_unidades(prod, "suma", txt)
                    )
                ], spacing=4) if modo == "pedido" else ft.Container()
                tarjeta = ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.icons.LOCAL_DRINK,
                                            color="#fbbf24", size=22),
                            bgcolor="#1c2430" if (p.stock_actual or 0) > (p.stock_minimo or 10)
                                    else "#3a1010",
                            padding=10, border_radius=8
                        ),
                        ft.Column([
                            ft.Text(p.nombre, size=14, weight="bold", color="white",
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"S/ {precio:.2f}", size=13,
                                    color="#fbbf24", weight="w600"),
                            ft.Text(f"Disponibles: {p.stock_actual} uds",
                                    size=10, color="grey"),
                        ], spacing=1, expand=True),
                        controles_carrito,
                    ], alignment="spaceBetween"),
                    padding=12, bgcolor="#0f1214",
                    border_radius=10, border=ft.border.all(1, "#1a1d20"),
                )
                grid_productos_ui.controls.append(tarjeta)
            await page.update_async()
        except Exception as err:
            grid_productos_ui.controls.clear()
            grid_productos_ui.controls.append(ft.Container(
                content=ft.Text(f"⚠️ Error: {str(err)}", color="red_accent", size=13),
                padding=20, bgcolor="#2a1010", border_radius=8
            ))
            await page.update_async()

    async def buscar_licor_cliente(e):
        await renderizar_catalogo_cliente(e.control.value.lower())

    header_cliente = ft.Container(
        padding=ft.padding.symmetric(horizontal=16, vertical=14),
        bgcolor="#0f1214",
        border=ft.Border(bottom=ft.BorderSide(1, "#1a1d20")),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Smart-Liquor Express 🍾", size=17,
                            weight="bold", color="white"),
                    ft.Text(
                        "Modo Solo Lectura 👀" if modo == "ver"
                        else "Catálogo de Pedidos Activo 🛒",
                        color="grey", size=11
                    ),
                ]),
                ft.Container(
                    content=ft.Text("CHINCHA", color="#a7f3d0",
                                    size=9, weight="bold"),
                    bgcolor="#0b2a1a", padding=5, border_radius=5,
                    border=ft.border.all(1, "#14532d")
                )
            ], alignment="spaceBetween"),
            ft.Container(height=4),
            ft.TextField(
                hint_text="Buscar licor o bebida...",
                on_change=buscar_licor_cliente,
                border_color="#232629", border_radius=10, height=40,
                text_size=13, content_padding=10,
                prefix_icon=ft.icons.SEARCH, bgcolor="#111416"
            )
        ])
    )

    btn_checkout_container.content = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SHOPPING_BAG, color="white", size=20),
            txt_checkout,
        ], alignment="center", spacing=10),
        bgcolor="#1e7e34",
        padding=ft.padding.symmetric(horizontal=20, vertical=14),
        border_radius=12,
        on_click=enviar_carrito_a_whatsapp,
    )

    page.controls.clear()
    page.controls.extend([
        header_cliente,
        ft.Container(content=grid_productos_ui, padding=16, expand=True),
    ])
    page.bottom_appbar = ft.BottomAppBar(
        content=ft.Container(content=btn_checkout_container,
                             padding=10, bgcolor="#0b0d0f"),
        bgcolor="#0b0d0f", height=90,
    )
    await renderizar_catalogo_cliente()