# Imagen base de Python
FROM python:3.11-slim

# Instalar dependencias del sistema: Tesseract y Poppler
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de la app
WORKDIR /app

# Copiar requirements e instalarlos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código
COPY . .

# Exponer puerto (Render usa $PORT)
EXPOSE 10000

# Comando de inicio
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
