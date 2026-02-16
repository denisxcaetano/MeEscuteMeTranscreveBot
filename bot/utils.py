"""
bot/utils.py - Funções auxiliares compartilhadas.

Funções genéricas usadas por múltiplos módulos do bot.
Centralizar aqui evita duplicação de código.

Uso:
    from bot.utils import format_duration, sanitize_filename
"""

import logging
import os
import tempfile
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================
# Mapeamento de códigos de idioma para nomes legíveis
# ============================================================
# Whisper retorna códigos ISO 639-1 (ex: "pt", "en", "es").
# Este dicionário converte para nomes que o usuário entende.
# Foco nos 3 idiomas principais + outros comuns para cobertura.
# ============================================================
LANGUAGE_NAMES: dict[str, str] = {
    "pt": "🇧🇷 Português",
    "en": "🇺🇸 Inglês",
    "es": "🇪🇸 Espanhol",
    "fr": "🇫🇷 Francês",
    "de": "🇩🇪 Alemão",
    "it": "🇮🇹 Italiano",
    "ja": "🇯🇵 Japonês",
    "ko": "🇰🇷 Coreano",
    "zh": "🇨🇳 Chinês",
    "ru": "🇷🇺 Russo",
    "ar": "🇸🇦 Árabe",
    "hi": "🇮🇳 Hindi",
    "nl": "🇳🇱 Holandês",
    "pl": "🇵🇱 Polonês",
    "tr": "🇹🇷 Turco",
    "uk": "🇺🇦 Ucraniano",
    "sv": "🇸🇪 Sueco",
    "da": "🇩🇰 Dinamarquês",
    "fi": "🇫🇮 Finlandês",
    "no": "🇳🇴 Norueguês",
}


def get_language_name(code: str) -> str:
    """
    Converte código de idioma para nome legível.

    Args:
        code: Código ISO 639-1 (ex: "pt", "en").

    Retorna:
        Nome do idioma com emoji da bandeira.
        Se não mapeado, retorna o código em maiúsculas.

    Exemplos:
        >>> get_language_name("pt")
        '🇧🇷 Português'
        >>> get_language_name("xyz")
        'XYZ'
    """
    return LANGUAGE_NAMES.get(code, code.upper())


def format_duration(seconds: float) -> str:
    """
    Formata duração em segundos para formato legível.

    Args:
        seconds: Duração em segundos.

    Retorna:
        String formatada (ex: "2min 30s", "45s").

    Exemplos:
        >>> format_duration(150.7)
        '2min 30s'
        >>> format_duration(45.3)
        '45s'
        >>> format_duration(3661)
        '1h 1min 1s'
    """
    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)

    if minutes < 60:
        return f"{minutes}min {secs}s" if secs else f"{minutes}min"

    hours, mins = divmod(minutes, 60)
    parts = [f"{hours}h"]
    if mins:
        parts.append(f"{mins}min")
    if secs:
        parts.append(f"{secs}s")
    return " ".join(parts)


def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho em bytes para formato legível.

    Args:
        size_bytes: Tamanho em bytes.

    Retorna:
        String formatada (ex: "2.5MB", "512KB").

    Exemplos:
        >>> format_file_size(2621440)
        '2.5MB'
        >>> format_file_size(524288)
        '512.0KB'
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"


def get_temp_filepath(extension: str = "mp3") -> str:
    """
    Gera um caminho temporário seguro para arquivos de áudio.

    Usa o diretório temp/ do projeto (configurável via settings).
    Arquivos temporários são nomeados com sufixo único pelo OS.

    Args:
        extension: Extensão do arquivo (sem ponto). Padrão: "mp3".

    Retorna:
        Caminho absoluto para o arquivo temporário.
    """
    temp_dir = Path(settings.TEMP_DIR)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # tempfile gera nome único automaticamente
    fd, filepath = tempfile.mkstemp(suffix=f".{extension}", dir=str(temp_dir))
    os.close(fd)  # Fecha o file descriptor (só precisamos do path)

    return filepath


def cleanup_file(filepath: str) -> None:
    """
    Remove um arquivo temporário de forma segura.

    Não levanta exceção se o arquivo não existir.
    Loga erro se falhar por outro motivo.

    Args:
        filepath: Caminho do arquivo a ser removido.
    """
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"Arquivo temporário removido: {filepath}")
    except OSError as e:
        logger.warning(f"Falha ao remover arquivo temporário {filepath}: {e}")
