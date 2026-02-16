# ============================================================
# Dockerfile - Container para Bot de Transcrição
# ============================================================
# Este Dockerfile garante que o ambiente tenha:
# 1. Python 3.11+
# 2. FFmpeg (obrigatório para conversão de áudio)
# 3. Todas as dependências do projeto
#
# Compatível com: Railway, Render, Fly.io, etc.
# ============================================================

# Usa imagem oficial do Python (leve e segura)
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instala FFmpeg e dependências do sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configura diretório de trabalho
WORKDIR /app

# Copia e instala dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia o código do projeto
COPY . .

# Comando de inicialização
CMD ["python", "main.py"]
