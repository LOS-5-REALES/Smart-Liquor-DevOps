# app/constants.py
"""
Módulo de constantes y configuraciones globales.

Centraliza los valores estáticos utilizados en la aplicación para mantener
la consistencia entre la lógica de negocio (CRUD) y la interfaz gráfica (UI).
"""

# Diccionario central que define los estados logísticos válidos,
# sus colores de interfaz y etiquetas legibles.
ESTADOS_LOGISTICOS = {
    "recibido": {"color": "#f57c00", "label": "Recibido"},
    "en ruta": {"color": "#1565c0", "label": "En Ruta"},
    "en camino": {"color": "#1565c0", "label": "En Camino"},
    "entregado": {"color": "#2e7d32", "label": "Entregado"},
    "cancelado": {"color": "#c62828", "label": "Cancelado"},
}

# Conjunto de llaves de estados para validaciones rápidas en la base de datos O(1).
ESTADOS_VALIDOS = set(ESTADOS_LOGISTICOS.keys())