# 1. Imagen base estable
FROM python:3.10-slim

# 2. Variables de entorno para Python (Sintaxis moderna ENV key=value)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo
WORKDIR /app

# 4. Dependencias del sistema (optimizadas en una sola capa)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Instalación de librerías (Usando caché de capas)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5b. Puente de compatibilidad para Flet Moderno y parche de Spacer
RUN mkdir -p /usr/local/lib/python3.10/site-packages/flet_fastapi && \
    echo "from flet.fastapi import *" > /usr/local/lib/python3.10/site-packages/flet_fastapi/__init__.py && \
    echo "import flet; flet.Spacer = lambda *args, **kwargs: flet.Container(expand=True)" >> /usr/local/lib/python3.10/site-packages/flet/__init__.py

# 6. Copia del código fuente
COPY . .

# 7. Puerto expuesto para el Monolito (API + Web)
EXPOSE 8000

# 8. Comando de arranque
CMD ["python", "app/main.py"]