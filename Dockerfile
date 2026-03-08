FROM python:3.10-slim

# Met a jour la liste des paquets et installe ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Definit le repertoire de travail
WORKDIR /app

# Copie requirements.txt en premier pour utiliser le cache Docker
COPY requirements.txt .

# Installe les dependances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le reste de l'application
COPY . .

# Expose le port 8000 pour DigitalOcean
EXPOSE 8000

# Lance l'application FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
