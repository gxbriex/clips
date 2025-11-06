# Dockerfile otimizado para Koyeb
FROM python:3.11-slim

# Instalar FFmpeg e dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências Python (versão CPU do PyTorch)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Comando para iniciar
CMD ["python", "bot.py"]
