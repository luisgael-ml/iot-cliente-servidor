# Imagen común para los tres clientes (simulador, consumidor y cliente de consultas)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .
ENV PYTHONUNBUFFERED=1
