"""
bot/audio_processor.py - Download, conversão e validação de áudio.

Responsável por todo o pipeline de preparação do áudio antes
de enviar para a API Whisper:

    1. Validação (tamanho, formato)
    2. Download do Telegram
    3. Conversão para formato compatível (se necessário)

A API Whisper aceita: mp3, mp4, mpeg, mpga, m4a, wav, webm.
Porém, o Telegram envia voice messages em formato .ogg (Opus codec).
Para máxima compatibilidade, convertemos tudo para MP3 mono 16kHz,
que é o formato ideal para speech-to-text.

Dependência externa: FFmpeg
    - Local: instalar via apt/brew/choco
    - Railway: instalado automaticamente via nixpacks.toml

Uso:
    from bot.audio_processor import download_and_prepare_audio, validate_audio_size
"""

import logging
import os
from pathlib import Path

from pydub import AudioSegment

from bot.utils import cleanup_file, format_file_size, get_temp_filepath
from config.settings import settings

logger = logging.getLogger(__name__)


# ============================================================
# Formatos de áudio suportados pelo Whisper
# ============================================================
# Referência: https://platform.openai.com/docs/guides/speech-to-text
# ============================================================
SUPPORTED_FORMATS: set[str] = {
    "mp3", "mp4", "mpeg", "mpga", "m4a",
    "wav", "webm", "ogg", "oga", "flac",
    "aac", "opus", "wma", "amr",
}

# Formatos que o Whisper aceita diretamente (não precisa converter)
WHISPER_NATIVE_FORMATS: set[str] = {
    "mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm",
}


class AudioValidationError(Exception):
    """
    Exceção para erros de validação de áudio.

    Contém uma mensagem user-friendly que pode ser enviada
    diretamente ao usuário no Telegram.

    Atributos:
        user_message: Mensagem formatada para o usuário.
    """

    def __init__(self, user_message: str):
        self.user_message = user_message
        super().__init__(user_message)


def validate_audio_size(file_size: int) -> None:
    """
    Valida se o tamanho do arquivo está dentro do limite.

    O limite da API Whisper é 25MB. Validamos antes do download
    para economizar banda e tempo.

    Args:
        file_size: Tamanho do arquivo em bytes.

    Raises:
        AudioValidationError: Se o arquivo excede o limite.
    """
    max_size = settings.max_audio_size_bytes

    if file_size > max_size:
        size_str = format_file_size(file_size)
        max_str = f"{settings.MAX_AUDIO_SIZE_MB}MB"
        raise AudioValidationError(
            f"❌ Arquivo muito grande ({size_str}).\n"
            f"📏 Limite: {max_str}.\n"
            f"💡 Tente comprimir o áudio ou enviar um trecho menor."
        )


def _get_file_extension(file_path: str) -> str:
    """
    Extrai a extensão do arquivo (sem o ponto, lowercase).
    Aplica sanitização básica para evitar caracteres maliciosos.

    Args:
        file_path: Caminho ou nome do arquivo.

    Retorna:
        Extensão em lowercase (ex: "ogg", "mp3").
    """
    # Remove qualquer tentativa de path traversal ou caracteres estranhos
    safe_name = os.path.basename(file_path)
    ext = Path(safe_name).suffix.lstrip(".").lower()
    
    # Filtra apenas caracteres alfanuméricos simples
    return "".join(c for c in ext if c.isalnum())


def _needs_conversion(file_path: str) -> bool:
    """
    Verifica se o arquivo precisa ser convertido.

    Voice messages do Telegram vêm em .ogg (Opus codec),
    que o Whisper aceita mas pode ter problemas.
    Convertemos tudo para MP3 para garantir compatibilidade.

    Args:
        file_path: Caminho do arquivo de áudio.

    Retorna:
        True se o arquivo precisa ser convertido para MP3.
    """
    ext = _get_file_extension(file_path)
    # Sempre convertemos para MP3 para máxima compatibilidade
    # O Whisper performa melhor com MP3 mono 16kHz
    return ext != "mp3"


def convert_to_mp3(input_path: str) -> str:
    """
    Converte qualquer formato de áudio para MP3 mono 16kHz.

    Parâmetros de conversão otimizados para speech-to-text:
        - Mono (1 canal): Voz humana não precisa de estéreo
        - 16kHz: Frequência padrão para reconhecimento de fala
        - 64kbps: Suficiente para voz, mantém arquivo pequeno

    Args:
        input_path: Caminho do arquivo de áudio original.

    Retorna:
        Caminho do arquivo MP3 convertido.

    Raises:
        AudioValidationError: Se a conversão falhar.
    """
    output_path = get_temp_filepath("mp3")

    try:
        logger.info(f"[AUDIO] Convertendo {input_path} → MP3")

        # Carrega o áudio (pydub detecta formato automaticamente via ffmpeg)
        audio = AudioSegment.from_file(input_path)

        # Converte para parâmetros ideais de speech-to-text
        audio = audio.set_channels(1)         # Mono
        audio = audio.set_frame_rate(16000)    # 16kHz  (padrão STT)
        audio = audio.set_sample_width(2)      # 16-bit (padrão STT)

        # Exporta como MP3 com bitrate baixo (voz não precisa de mais)
        audio.export(
            output_path,
            format="mp3",
            bitrate="64k",
        )

        input_size = os.path.getsize(input_path)
        output_size = os.path.getsize(output_path)
        logger.info(
            f"[AUDIO] Conversão OK: {format_file_size(input_size)} → "
            f"{format_file_size(output_size)}"
        )

        return output_path

    except Exception as e:
        cleanup_file(output_path)
        logger.error(f"[AUDIO] Erro na conversão: {e}")
        raise AudioValidationError(
            "❌ Erro ao processar o áudio.\n"
            "💡 O formato pode não ser suportado. "
            "Tente enviar em MP3, M4A ou WAV."
        ) from e


async def download_and_prepare_audio(
    telegram_file,
    original_filename: str | None = None,
) -> str:
    """
    Pipeline completo: download do Telegram → conversão → pronto para Whisper.

    Etapas:
        1. Faz download do arquivo do Telegram para diretório temp
        2. Verifica se precisa de conversão
        3. Se sim, converte para MP3 mono 16kHz
        4. Retorna caminho do arquivo pronto para transcrição

    Args:
        telegram_file: Objeto File do python-telegram-bot.
        original_filename: Nome original do arquivo (para detectar formato).

    Retorna:
        Caminho do arquivo de áudio pronto para enviar ao Whisper.

    Raises:
        AudioValidationError: Se download ou conversão falharem.
    """
    # Determina extensão do arquivo
    if original_filename:
        ext = _get_file_extension(original_filename)
    else:
        # Voice messages do Telegram não têm nome de arquivo
        ext = "ogg"

    # Valida formato suportado
    if ext not in SUPPORTED_FORMATS:
        raise AudioValidationError(
            f"❌ Formato '.{ext}' não suportado.\n"
            f"📋 Formatos aceitos: MP3, OGG, WAV, M4A, FLAC, AAC, OPUS, WebM"
        )

    # Download para arquivo temporário
    download_path = get_temp_filepath(ext)

    try:
        logger.info(f"[AUDIO] Baixando arquivo do Telegram (formato: .{ext})")
        await telegram_file.download_to_drive(download_path)

        file_size = os.path.getsize(download_path)
        logger.info(f"[AUDIO] Download concluído: {format_file_size(file_size)}")

        # Validação extra: tenta carregar o cabeçalho do áudio para ver se é válido
        # Se não for um áudio real, pydub/ffmpeg vai disparar erro aqui
        try:
            AudioSegment.from_file(download_path).duration_seconds
        except Exception as e:
            logger.error(f"[SECURITY] Arquivo baixado não parece ser um áudio válido: {e}")
            raise AudioValidationError(
                "❌ O arquivo enviado não é um áudio válido ou está corrompido.\n"
                "💡 Tente enviar o áudio novamente."
            )

        # Converte para MP3 se necessário
        if _needs_conversion(download_path):
            mp3_path = convert_to_mp3(download_path)
            cleanup_file(download_path)  # Remove o arquivo original
            return mp3_path

        return download_path

    except AudioValidationError:
        cleanup_file(download_path)
        raise
    except Exception as e:
        cleanup_file(download_path)
        logger.error(f"[AUDIO] Erro no download: {e}")
        raise AudioValidationError(
            "❌ Erro ao baixar o áudio do Telegram.\n"
            "💡 Tente enviar novamente."
        ) from e


def get_audio_duration(file_path: str) -> float:
    """
    Retorna a duração do áudio em segundos.

    Args:
        file_path: Caminho do arquivo de áudio.

    Retorna:
        Duração em segundos (float).
        Retorna 0.0 se não conseguir determinar.
    """
    try:
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0  # pydub retorna em milissegundos
    except Exception as e:
        logger.warning(f"[AUDIO] Não foi possível obter duração: {e}")
        return 0.0
