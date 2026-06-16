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

# Configuración del Número del Bot para el redireccionamiento (Formato Internacional sin el +)
NUMERO_BOT_WHATSAPP = "51977860423"  

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

    # ── 🔍 DETECCIÓN DE PARÁMETROS EN LA URL (MODO CLIENTE) ──
    # Flet expone los parámetros de la URL a través de page.route
    url_params = {}
    if "?" in page.route:
        raw_params = page.route.split("?")[1]
        for param in raw_params.split("&"):
            if "=" in param:
                k, v = param.split("=")
                url_params[k] = v

    telefono_cliente = url_params.get("telefono", None)
    es_modo_cliente = telefono_cliente is not None

    # Si es un cliente real desde WhatsApp, cargamos la experiencia del Catálogo Digital Interactivo
    if es_modo_cliente:
        await cargar_interfaz_cliente(page, telefono_cliente)
        return

    # ─────────────────────────────────────────────────────────────────────────────────────────
    # ── ⚙️ INTERFAZ ADMINISTRATIVA COMPLETA (ROL: ADMIN / LOGÍSTICA CHINCHA) ──────────────────
    # ─────────────────────────────────────────────────────────────────────────────────────────
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
        for i, item in enumerate(sidebar_items.controls):
            if isinstance(item, ft.Container):
                is_selected = i == idx
                item.bgcolor = "#1a1f26" if is_selected else "transparent"
                item.content.controls[0].icon_color = "#2196f3" if is_selected else "grey"
                item.content.controls[1].color = "white" if is_selected else "grey"
        
        for i, btn in enumerate(btn_tabs):
            btn.bgcolor = "#1a1f26" if i == idx else "#111416"
            btn.border = ft.border.all(1, "#2196f3" if i == idx else "#232629")

        contenido_central.content = vistas[idx]()
        await page.update_async()

    def handler_cambio_seccion(idx):
        return lambda e: page.run_task(cambiar_seccion, idx)

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


# ─────────────────────────────────────────────────────────────────────────────────────────
# ── 🛒 INTERFAZ DEL CLIENTE (MODO: CATÁLOGO DIGITAL INTERACTIVO VIA WHATSAPP) ─────────────
# ─────────────────────────────────────────────────────────────────────────────────────────
async def cargar_interfaz_cliente(page: ft.Page, telefono: str):
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    # Lista reactiva que contendrá las tarjetas de licores optimizadas
    grid_productos_ui = ft.Column(spacing=14, scroll=ft.ScrollMode.ADAPTIVE)
    
    # Diccionario en memoria de la pestaña del cliente para controlar las cantidades elegidas
    # Llave: producto_id -> Valor: {nombre, cantidad, precio}
    carrito_compra = {}

    # Texto flotante inferior del botón que indica los licores sumados
    txt_checkout = ft.Text("Tu carrito está vacío", color="white", size=14, weight="bold")
    btn_checkout = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.SHOPPING_BAG, color="white", size=20),
            txt_checkout
        ], alignment="center"),
        bgcolor="#1e7e34", padding=14, border_radius=10,
        visible=False,
        on_click=lambda e: page.run_task(enviar_carrito_a_whatsapp)
    )

    async def enviar_carrito_a_whatsapp(e):
        if not carrito_compra:
            return
        # Para mantener la simplicidad y acoplamiento con la estructura del bot, 
        # tomamos el primer producto agregado del carrito para este MVP interactivo.
        prod_id = list(carrito_compra.keys())[0]
        item = carrito_compra[prod_id]
        
        # Formateamos la cadena de retorno idéntica a la que espera el interceptor de bot.py
        mensaje_formateado = f"PEDIDO_WEB:ID={prod_id}|CANT={item['cantidad']}"
        
        # Enlace profundo hacia WhatsApp
        url_whatsapp = f"https://wa.me/{NUMERO_BOT_WHATSAPP}?text={mensaje_formateado}"
        await page.launch_url_async(url_whatsapp)

    def actualizar_ui_checkout():
        if not carrito_compra:
            btn_checkout.visible = False
        else:
            prod_id = list(carrito_compra.keys())[0]
            item = carrito_compra[prod_id]
            txt_checkout.value = f"Pedir: {item['cantidad']} x {item['nombre']} (S/ {item['cantidad'] * item['precio']:.2f})"
            btn_checkout.visible = True

    def cambiar_cantidad(producto, delta):
        p_id = producto.id
        if p_id not in carrito_compra and delta > 0:
            carrito_compra[p_id] = {
                "nombre": producto.nombre,
                "precio": float(producto.precio_venta or 0.0),
                "cantidad": 0
            }
        
        if p_id in carrito_compra:
            # Reemplazamos carritos anteriores para asegurar una única compra directa limpia por WhatsApp
            carrito_compra.clear()
            carrito_compra[p_id] = {
                "nombre": producto.nombre,
                "precio": float(producto.precio_venta or 0.0),
                "cantidad": max(1, delta)  # Fijamos la selección directa
            }
        
        actualizar_ui_checkout()
        page.update()

    async def renderizar_catalogo_cliente(termino=""):
        grid_productos_ui.controls.clear()
        prods = await run_db(lambda db: db.query(models.Producto).filter(
            ~models.Producto.nombre.startswith("[DESCONTINUADO]")
        ).all())
        
        # Filtro reactivo en base al cuadro de búsqueda express
        if termino:
            prods = [p for p in prods if termino in p.nombre.lower()]

        if not prods:
            grid_productos_ui.controls.append(
                ft.Container(
                    content=ft.Text("No se encontraron licores con ese nombre.", color="grey", italic=True),
                    padding=20, alignment=ft.alignment.center
                )
            )
            await page.update_async()
            return

        for p in prods:
            precio = float(p.precio_venta or 0.0)
            tarjeta_licor = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.LOCAL_DRINK, color="#fbbf24", size=24),
                        bgcolor="#1a1ffd" if (p.stock_actual or 0) > (p.stock_minimo or 10) else "#3a1010",
                        padding=12, border_radius=8
                    ),
                    ft.Column([
                        ft.Text(p.nombre, size=15, weight="bold", color="white", max_lines=1),
                        ft.Text(f"S/ {precio:.2f}", size=14, color="#fbbf24", weight="w600"),
                        ft.Text(f"Disponible en Chincha: {p.stock_actual} uds", size=11, color="grey")
                    ], spacing=2, expand=True),
                    ft.IconButton(
                        icon=ft.icons.ADD_SHOPPING_CART,
                        icon_color="white",
                        bgcolor="#1565c0",
                        icon_size=18,
                        on_click=lambda e, prod=p: cambiar_cantidad(prod, 1)
                    )
                ], alignment="spaceBetween"),
                padding=14,
                bgcolor="#0f1214",
                border_radius=12,
                border=ft.border.all(1, "#1a1d20")
            )
            grid_productos_ui.controls.append(tarjeta_licor)
        await page.update_async()

    async def buscar_licor_cliente(e):
        await renderizar_catalogo_cliente(e.control.value.lower())

    # --- DISEÑO UI EXCLUSIVO PARA SMARTPHONES DE CLIENTES ---
    header_cliente = ft.Container(
        padding=ft.padding.symmetric(horizontal=16, vertical=16),
        bgcolor="#0f1214",
        border=ft.Border(bottom=ft.BorderSide(1, "#1a1d20")),
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Smart-Liquor Express 🍾", size=18, weight="bold", color="white"),
                    ft.Text("Delivery rápido directo a tu casa", color="grey", size=11),
                ]),
                ft.Container(
                    content=ft.Text("CHINCHA", color="#a7f3d0", size=10, weight="bold"),
                    bgcolor="#0b2a1a", padding=6, border_radius=6, border=ft.border.all(1, "#14532d")
                )
            ], alignment="spaceBetween"),
            ft.Container(height=6),
            ft.TextField(
                hint_text="¿Qué te provoca tomar hoy? Buscar...",
                on_change=buscar_licor_cliente,
                border_color="#232629",
                border_radius=10, height=42,
                text_size=13, content_padding=10,
                prefix_icon=ft.icons.SEARCH,
                bgcolor="#111416"
            )
        ])
    )

    page.controls.clear()
    page.controls.extend([
        header_cliente,
        ft.Container(
            content=grid_productos_ui,
            padding=16,
            expand=True
        ),
        ft.Container(
            content=btn_checkout,
            padding=16,
            bgcolor="#0b0d0f"
        )
    ])
    
    await renderizar_catalogo_cliente()