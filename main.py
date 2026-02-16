"""
main.py - Entry point do Bot de Transcrição de Áudio.

Este é o ponto de entrada principal do bot. Ele:
    1. Configura o sistema de logging
    2. Cria a instância do bot Telegram
    3. Registra todos os handlers
    4. Inicia o polling (escuta de mensagens)

Modo de operação: Long Polling
    O bot se conecta ao Telegram e "pergunta" periodicamente
    se há novas mensagens. Mais simples que webhooks e não
    requer URL pública ou certificado SSL.

Para rodar:
    # Localmente (com .env configurado):
    python main.py

    # Em produção (Railway/Render):
    Configurado automaticamente via railway.toml
"""

import logging
import sys

from telegram.ext import Application

from bot.handlers import setup_handlers
from config.settings import settings


def setup_logging() -> None:
    """
    Configura o sistema de logging.

    Formato:
        2026-02-16 18:30:00 | INFO | bot.handlers | Mensagem aqui

    Níveis:
        - INFO: Operações normais (início, transcrição OK, etc)
        - WARNING: Situações recuperáveis (retry, arquivo grande)
        - ERROR: Falhas (API down, conversão falhou)
        - DEBUG: Detalhes extras (só para desenvolvimento)

    Em produção (Railway), logs aparecem no dashboard automaticamente.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduz ruído de libs externas (só mostra warnings+)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def start_health_check_server() -> None:
    """
    Inicia um servidor HTTP simples para satisfazer o health check do Render.
    
    O Render (e outros PaaS) exige que serviços web escutem em uma porta.
    Como este bot usa polling (não webhook), criamos este servidor dummy
    apenas para responder "200 OK" e manter o serviço vivo.
    """
    import os
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class HealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running!")
        
        # Silencia logs de requisição para não poluir o terminal
        def log_message(self, format, *args):
            pass

    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    logging.getLogger(__name__).info(f"🌍 Health check server rodando na porta {port}")


def main() -> None:
    """
    Função principal — configura e inicia o bot.

    Etapas:
        1. Configura logging
        2. Inicia servidor dummy (para Render/Railway)
        3. Verifica configurações (falha rápido se algo estiver errado)
        4. Cria instância do bot
        5. Registra handlers
        6. Inicia polling (loop infinito de escuta)
    """
    # 1. Configura logging
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("🎙️ Bot de Transcrição de Áudio — Iniciando")
    logger.info("=" * 50)

    # 2. Inicia servidor de health check (necessário para deploy gratuito)
    start_health_check_server()

    # 3. Verifica configurações (sem expor chaves!)
    logger.info(f"📏 Tamanho máximo de áudio: {settings.MAX_AUDIO_SIZE_MB}MB")
    logger.info(f"🎯 Temperatura Whisper: {settings.WHISPER_TEMPERATURE}")
    logger.info(f"📂 Diretório de dados: {settings.DATA_DIR}")
    logger.info(f"📂 Diretório temporário: {settings.TEMP_DIR}")

    # 3. Cria o Application do python-telegram-bot
    #    - Application é a classe principal que gerencia o bot
    #    - .builder() usa o pattern Builder para configuração
    #    - .token() configura o token de autenticação
    #    - .build() cria a instância final (imutável)
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # 4. Registra handlers (comandos + mensagens de áudio)
    setup_handlers(application)

    # 5. Inicia polling (loop infinito)
    #    - poll_interval=1.0: verifica novas mensagens a cada 1s
    #    - drop_pending_updates=True: ignora mensagens antigas no startup
    #    - allowed_updates: tipos de updates a receber
    logger.info("🚀 Bot iniciado! Aguardando mensagens...")
    logger.info("   Pressione Ctrl+C para parar")

    application.run_polling(
        poll_interval=1.0,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
