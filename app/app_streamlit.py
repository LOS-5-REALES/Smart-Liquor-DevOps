import streamlit as st
import pandas as pd
from app.database import SessionLocal 
import app.models as models
from datetime import datetime, date

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Smart-Liquor DevOps - Dashboard",
    page_icon="🍾",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ESTILOS PERSONALIZADOS (CSS) ---
st.markdown("""
    <style>
    .main { background-color: #0f1113; }
    div[data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #fbbf24; }
    div[data-testid="stMetricDelta"] { font-size: 14px; }
    .stDataTable { border: 1px solid #20252a; border-radius: 12px; }
    .status-live { 
        background-color: #0b2a1a; color: #a7f3d0; 
        padding: 4px 12px; border-radius: 20px; 
        border: 1px solid #14532d; font-size: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE DATOS ---
def obtener_datos():
    db = SessionLocal()
    try:
        # 1. Metas y métricas de hoy
        inicio_hoy = datetime.combine(date.today(), datetime.min.time())
        pedidos_hoy_q = db.query(models.Pedido).filter(models.Pedido.fecha_hora >= inicio_hoy)
        
        count_pedidos = pedidos_hoy_q.count()
        total_ventas = sum((p.total_pedido or 0) for p in pedidos_hoy_q.all())
        ticket_medio = total_ventas / count_pedidos if count_pedidos > 0 else 0
        
        # 2. Stock Crítico
        productos_alerta = db.query(models.Producto).filter(
            models.Producto.stock_actual <= models.Producto.stock_minimo
        ).all()
        
        # 3. Pedidos Recientes
        pedidos_recientes = db.query(models.Pedido).order_by(
            models.Pedido.fecha_hora.desc()
        ).limit(10).all()
        
        data_pedidos = []
        for p in pedidos_recientes:
            cliente_nom = p.cliente.nombre_completo if p.cliente else "Final"
            prod_nom = p.items[0].producto.nombre if p.items and p.items[0].producto else "Varios/Sin Prod"
            
            data_pedidos.append({
                "ID": f"#{p.id}",
                "Cliente": cliente_nom,
                "Producto": prod_nom,
                "Monto": f"S/ {p.total_pedido:,.2f}",
                "Estado": p.estado_pago.upper()
            })

        # 4. CONSULTA NUEVA: Todos los productos para el Inventario
        todos_productos = db.query(models.Producto).all()
        data_inventario = []
        for prod in todos_productos:
            data_inventario.append({
                "Producto": prod.nombre,
                "Marca": prod.marca or "Genérico",
                "Stock Actual": prod.stock_actual,
                "Stock Mínimo": prod.stock_minimo,
                "Precio Venta": f"S/ {prod.precio_venta:,.2f}"
            })

        return {
            "ventas": total_ventas,
            "pedidos": count_pedidos,
            "alertas": len(productos_alerta),
            "ticket": ticket_medio,
            "tabla": pd.DataFrame(data_pedidos),
            "productos_alerta": productos_alerta,
            "tabla_inventario": pd.DataFrame(data_inventario) # Agregado
        }
    except Exception as e:
        st.error(f"❌ Error al consultar Supabase: {e}")
        return None
    finally:
        db.close()

# --- UI - ENCABEZADO ---
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.title("🚀 Smart-Liquor Dashboard")
    st.caption(f"Operación en tiempo real • {datetime.now().strftime('%d/%m/%Y %H:%M')}")

with col_t2:
    st.markdown('<br><span class="status-live">● SINCRONIZADO CON SUPABASE</span>', unsafe_allow_html=True)
    if st.button("🔄 Actualizar Datos"):
        st.rerun()

st.divider()

# --- BLOQUE 1: MÉTRICAS ---
datos = obtener_datos()

if datos is not None:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventas de Hoy", f"S/ {datos['ventas']:,.2f}")
    m2.metric("Pedidos Hoy", datos['pedidos'])
    m3.metric("Stock Crítico", datos['alertas'], delta_color="inverse")
    m4.metric("Ticket Promedio", f"S/ {datos['ticket']:,.2f}")

    st.write("") 

    # --- BLOQUE 2: TABLAS Y ALERTAS ---
    col_tabla, col_alertas = st.columns([2, 1])

    with col_tabla:
        st.subheader("📝 Pedidos Recientes")
        if not datos['tabla'].empty:
            st.dataframe(datos['tabla'], use_container_width=True, hide_index=True)
        else:
            st.info("No se registraron pedidos hoy.")

    with col_alertas:
        st.subheader("⚠️ Alertas de Stock")
        if not datos['productos_alerta']:
            st.success("✅ Todo el inventario está en niveles óptimos.")
        else:
            for p in datos['productos_alerta'][:5]:
                porcentaje = min(1.0, p.stock_actual / p.stock_minimo) if p.stock_minimo > 0 else 0
                with st.container(border=True):
                    st.write(f"**{p.nombre}**")
                    st.progress(porcentaje)
                    st.caption(f"Actual: {p.stock_actual} | Mínimo: {p.stock_minimo}")

    st.divider()

    # --- UI - VISTA PRINCIPAL (Pestañas) ---
    tab1, tab2 = st.tabs(["📈 Dashboard General", "📦 Inventario y Stock"])

    with tab1:
        st.subheader("📦 Inventario Total en Base de Datos")
        if not datos['tabla_inventario'].empty:
            st.dataframe(
                datos['tabla_inventario'],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No hay productos registrados en la base de datos.")

    with tab2:
        st.header("Gestión de Inventario")

        # --- BUSCADOR ---
        termino_busqueda = st.text_input(
            " Buscar producto por nombre...",
            placeholder="Ej: Ron, Pisco, Cerveza...",
            key="buscador_inventario"
        )

        # Filtrar el DataFrame de inventario
        tabla_filtrada = datos["tabla_inventario"]
        if termino_busqueda:
            tabla_filtrada = tabla_filtrada[
                tabla_filtrada["Producto"].str.contains(termino_busqueda, case=False, na=False)
            ]

        st.dataframe(
            tabla_filtrada,
            use_container_width=True,
            hide_index=True,
            height=500
        )

else:
    st.warning("⚠️ Esperando conexión con la base de datos...")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.caption("Smart-Liquor DevOps v2.0")