"""
config/settings.py - Configurações centralizadas do bot.

Carrega variáveis de ambiente do arquivo .env (desenvolvimento local)
ou do ambiente do sistema (Railway/Render em produção).

Padrão de design: Singleton via dataclass.
Todas as configurações são validadas no startup — se algo faltar,
o bot falha imediatamente com mensagem clara, em vez de falhar
silenciosamente depois.

Uso:
    from config.settings import settings
    print(settings.TELEGRAM_BOT_TOKEN)
"""

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

# Carrega .env apenas se existir (em produção, vars vêm do ambiente)
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    Configurações imutáveis do bot.

    Atributos:
        TELEGRAM_BOT_TOKEN: Token do bot obtido via @BotFather.
        OPENAI_API_KEY: Chave da API OpenAI para Whisper.
        BOT_PASSWORD: Senha para autenticação de usuários.
        MAX_AUDIO_SIZE_MB: Tamanho máximo de áudio em MB (padrão: 25).
        WHISPER_TEMPERATURE: Temperatura do Whisper (0 = máxima precisão).
        DATA_DIR: Diretório para dados persistentes (authorized_users.json).
        TEMP_DIR: Diretório para arquivos temporários de áudio.
    """

    TELEGRAM_BOT_TOKEN: str
    OPENAI_API_KEY: str
    BOT_PASSWORD: str
    MAX_AUDIO_SIZE_MB: int = 25
    WHISPER_TEMPERATURE: float = 0.0
    DATA_DIR: str = "data"
    TEMP_DIR: str = "temp"

    @property
    def max_audio_size_bytes(self) -> int:
        """Retorna o tamanho máximo em bytes (para comparação direta)."""
        return self.MAX_AUDIO_SIZE_MB * 1024 * 1024


def _load_settings() -> Settings:
    """
    Carrega e valida todas as variáveis de ambiente obrigatórias.

    Retorna:
        Settings: Objeto imutável com todas as configurações.

    Raises:
        SystemExit: Se alguma variável obrigatória estiver ausente.
    """
    # --- Variáveis obrigatórias ---
    required_vars = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "BOT_PASSWORD": os.getenv("BOT_PASSWORD"),
    }

    # Verifica se todas estão presentes
    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        print(
            f"❌ ERRO FATAL: Variáveis de ambiente obrigatórias não configuradas: "
            f"{', '.join(missing)}\n"
            f"   → Configure no arquivo .env (local) ou nos secrets do Railway.\n"
            f"   → Veja .env.example para referência.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Variáveis opcionais (com valores padrão) ---
    max_size = int(os.getenv("MAX_AUDIO_SIZE_MB", "25"))
    temperature = float(os.getenv("WHISPER_TEMPERATURE", "0"))

    return Settings(
        TELEGRAM_BOT_TOKEN=required_vars["TELEGRAM_BOT_TOKEN"],
        OPENAI_API_KEY=required_vars["OPENAI_API_KEY"],
        BOT_PASSWORD=required_vars["BOT_PASSWORD"],
        MAX_AUDIO_SIZE_MB=max_size,
        WHISPER_TEMPERATURE=temperature,
    )


# Singleton: carregado uma única vez no import
settings = _load_settings()
