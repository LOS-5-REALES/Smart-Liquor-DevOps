# app/componentes/panel_clientes.py
import asyncio
import flet as ft


def build_panel_clientes(page: ft.Page, run_db, models, crud):
    """
    Panel de busqueda y listado de clientes con autocompletado.
    Retorna (panel, refrescar_clientes) para integrarlo en ui.py.
    """
    lista_clientes_ui = ft.Column(spacing=8, scroll="always")
    txt_total_clientes = ft.Text("0 clientes", size=12, color="grey")
    _todos_los_clientes = []

    # ── Buscador con autocompletado ───────────────────────────
    inp_busqueda = ft.TextField(
        hint_text="Buscar cliente por nombre o telefono...",
        border_radius=20,
        height=42,
        text_size=14,
        content_padding=10,
        prefix_icon=ft.icons.SEARCH,
        bgcolor="#16191c",
        border_color="#2a2d30",
    )

    def filtrar_clientes(termino: str):
        if not termino.strip():
            return _todos_los_clientes
        t = termino.lower()
        return [
            c for c in _todos_los_clientes
            if t in (c.nombre_completo or "").lower()
            or t in (c.telefono or "").lower()
        ]

    async def on_busqueda(e):
        clientes_filtrados = filtrar_clientes(e.control.value)
        await construir_lista(clientes_filtrados)
        await page.update_async()

    inp_busqueda.on_change = on_busqueda

    # ── Construir lista de clientes ───────────────────────────
    async def construir_lista(clientes):
        lista_clientes_ui.controls.clear()
        txt_total_clientes.value = f"{len(clientes)} cliente{'s' if len(clientes) != 1 else ''}"

        if not clientes:
            lista_clientes_ui.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No se encontraron clientes.",
                        color="grey", italic=True, size=13
                    ),
                    padding=20,
                )
            )
            return

        for c in clientes:
            # Contar pedidos del cliente
            total_pedidos  = len(c.pedidos) if c.pedidos else 0
            total_gastado  = sum(
                p.total_pedido for p in c.pedidos if p.total_pedido
            ) if c.pedidos else 0.0

            # Fuente del cliente
            es_whatsapp = (c.telefono or "").startswith("whatsapp:")
            tel_limpio  = (c.telefono or "").replace("whatsapp:", "")
            fuente_icon = "chat" if es_whatsapp else "person"
            fuente_color = "#25D366" if es_whatsapp else "#1565c0"
            fuente_label = "WhatsApp" if es_whatsapp else "Manual"

            lista_clientes_ui.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(fuente_icon, color=fuente_color, size=18),
                            ft.Column([
                                ft.Text(
                                    c.nombre_completo or "Sin nombre",
                                    weight="bold", size=14,
                                ),
                                ft.Text(
                                    tel_limpio,
                                    color="grey", size=12,
                                ),
                            ], expand=True, spacing=2),
                            ft.Container(
                                content=ft.Text(fuente_label, size=10, color="white"),
                                bgcolor=fuente_color,
                                border_radius=4,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            ),
                        ], vertical_alignment="center", spacing=10),

                        ft.Divider(height=6, color="#2a2d30"),

                        ft.Row([
                            ft.Column([
                                ft.Text("DIRECCION", size=9, color="#555"),
                                ft.Text(
                                    c.direccion_exacta or "No registrada",
                                    size=12,
                                    color="white" if c.direccion_exacta else "grey",
                                    italic=not c.direccion_exacta,
                                ),
                            ], expand=True, spacing=2),
                            ft.Column([
                                ft.Text("PEDIDOS", size=9, color="#555"),
                                ft.Text(
                                    str(total_pedidos),
                                    size=14, weight="bold", color="amber",
                                ),
                            ], spacing=2),
                            ft.Column([
                                ft.Text("TOTAL GASTADO", size=9, color="#555"),
                                ft.Text(
                                    f"S/ {total_gastado:.2f}",
                                    size=13, color="green",
                                ),
                            ], spacing=2),
                        ], spacing=16),

                        # Referencia si existe
                        ft.Text(
                            f"📍 Ref: {c.referencia_ubicacion}",
                            size=11, color="#555",
                            visible=bool(c.referencia_ubicacion),
                        ),
                    ], spacing=6),
                    bgcolor="#16191c",
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                )
            )

    # ── Refresco de clientes ──────────────────────────────────
    async def refrescar_clientes():
        nonlocal _todos_los_clientes
        try:
            clientes = await run_db(lambda db: (
                db.query(models.Cliente)
                .options(__import__('sqlalchemy.orm', fromlist=['joinedload'])
                         .joinedload(models.Cliente.pedidos))
                .order_by(models.Cliente.id.desc())
                .all()
            ))
            _todos_los_clientes = clientes
            termino = inp_busqueda.value or ""
            await construir_lista(filtrar_clientes(termino))
            await page.update_async()
        except Exception as ex:
            print(f"[CLIENTES ERROR] {ex}")

    # ── Panel completo ────────────────────────────────────────
    panel = ft.Column([
        ft.Row([
            ft.Text("Clientes", size=18, weight="bold", expand=True),
            txt_total_clientes,
            ft.IconButton(
                "refresh",
                icon_color="grey",
                icon_size=18,
                tooltip="Actualizar clientes",
                on_click=lambda e: asyncio.ensure_future(refrescar_clientes()),
            ),
        ], vertical_alignment="center"),
        inp_busqueda,
        ft.Container(content=lista_clientes_ui, height=400),
    ], spacing=8)

    return panel, refrescar_clientes