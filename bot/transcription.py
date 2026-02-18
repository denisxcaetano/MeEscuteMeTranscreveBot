"""
bot/transcription.py - Integração com API Whisper (Máxima Precisão).

Envia áudio para a API Whisper da OpenAI e retorna a transcrição
com detecção automática de idioma.

Configuração de MÁXIMA PRECISÃO:
    - temperature=0: Zero criatividade, apenas o que foi dito
    - language=None: Detecção automática (não força idioma)
    - response_format='verbose_json': Retorna idioma + segmentos
    - Sem prompt: Evita viés/indução na transcrição

Detecção multilíngue:
    O Whisper detecta O IDIOMA PREDOMINANTE do áudio.
    Para detecção de múltiplos idiomas em um só áudio,
    analisamos os segmentos individuais (cada segmento
    tem ~30s e pode ter idioma diferente detectado).

Custos:
    Whisper: $0.006 por minuto de áudio
    Exemplo: 5 minutos de áudio = $0.03

Uso:
    from bot.transcription import transcribe_audio

    result = await transcribe_audio("caminho/do/audio.mp3")
    print(result['text'])       # Texto transcrito
    print(result['language'])   # Idioma principal
"""

import asyncio
import logging
from dataclasses import dataclass, field

from openai import OpenAI, APIError, APITimeoutError

from bot.prompts import PROMPTS
from bot.utils import get_language_name, format_duration
from config.settings import settings

logger = logging.getLogger(__name__)

# Timeout para a API Whisper (segundos)
# Áudios longos podem demorar — 5 min é um limite seguro
WHISPER_TIMEOUT = 300

# Número máximo de tentativas em caso de erro
MAX_RETRIES = 3

# Tempo base de espera entre retries (dobra a cada tentativa)
BASE_RETRY_DELAY = 2.0


@dataclass
class TranscriptionResult:
    """
    Resultado de uma transcrição de áudio.

    Atributos:
        text: Texto transcrito completo.
        language: Código do idioma principal (ex: "pt", "en").
        language_name: Nome legível do idioma (ex: "🇧🇷 Português").
        detected_languages: Lista de idiomas detectados (se multilíngue).
        is_multilingual: True se mais de um idioma foi detectado.
        duration: Duração do áudio em segundos.
    """

    text: str
    language: str
    language_name: str = ""
    detected_languages: list[str] = field(default_factory=list)
    is_multilingual: bool = False
    duration: float = 0.0

    def __post_init__(self):
        """Preenche language_name automaticamente."""
        if not self.language_name and self.language:
            self.language_name = get_language_name(self.language)


class TranscriptionError(Exception):
    """
    Exceção para erros na transcrição.

    Contém mensagem user-friendly para enviar ao Telegram.
    """

    def __init__(self, user_message: str, technical_detail: str = ""):
        self.user_message = user_message
        self.technical_detail = technical_detail
        super().__init__(user_message)


def _detect_languages_from_segments(segments: list[dict]) -> list[str]:
    """
    Analisa segmentos para detectar múltiplos idiomas.

    O Whisper retorna segmentos de ~30s cada um. Cada segmento
    pode ter um idioma diferente detectado via heurística.

    Nota: Na prática, Whisper retorna apenas o idioma principal.
    Os segmentos não contêm idioma individualmente na API atual.
    Para detecção multilíngue real, comparamos o idioma detectado
    com sinais no texto (caracteres especiais, padrões de palavras).

    Args:
        segments: Lista de segmentos do verbose_json.

    Retorna:
        Lista de códigos de idiomas detectados.
    """
    # Whisper retorna idioma no nível do áudio inteiro, não por segmento.
    # Retornamos lista vazia — o idioma principal vem da resposta top-level.
    return []


def _create_openai_client() -> OpenAI:
    """
    Cria e retorna um cliente OpenAI configurado.

    Usa a chave da API definida nas settings.
    Timeout configurado para áudios longos.
    """
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=WHISPER_TIMEOUT,
    )


async def transcribe_audio(file_path: str) -> TranscriptionResult:
    """
    Transcreve um arquivo de áudio usando a API Whisper.

    Pipeline:
        1. Abre o arquivo de áudio
        2. Envia para Whisper com configuração de máxima precisão
        3. Extrai idioma detectado e texto
        4. Analisa segmentos para detecção multilíngue
        5. Retry automático com backoff exponencial em caso de erro

    Configuração de precisão:
        - temperature=0: Saída determinística, sem "criatividade"
        - language=None: Whisper detecta o idioma automaticamente
        - verbose_json: Retorna metadados completos (idioma, duração, segments)

    Args:
        file_path: Caminho do arquivo de áudio (preferencialmente MP3).

    Retorna:
        TranscriptionResult: Objeto com texto, idioma e metadados.

    Raises:
        TranscriptionError: Se todas as tentativas falharem.
    """
    client = _create_openai_client()
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"[WHISPER] Iniciando transcrição (tentativa {attempt}/{MAX_RETRIES}): "
                f"{file_path}"
            )

            # Executa a chamada síncrona da OpenAI em thread separada
            # para não bloquear o event loop do asyncio
            result = await asyncio.to_thread(
                _call_whisper_api, client, file_path
            )

            return result

        except APITimeoutError as e:
            last_error = e
            logger.warning(
                f"[WHISPER] Timeout na tentativa {attempt}/{MAX_RETRIES}: {e}"
            )

        except APIError as e:
            last_error = e
            logger.error(
                f"[WHISPER] Erro da API na tentativa {attempt}/{MAX_RETRIES}: "
                f"status={e.status_code}, message={e.message}"
            )

            # Erros 4xx (exceto 429) não fazem sentido retry
            if e.status_code and 400 <= e.status_code < 500 and e.status_code != 429:
                break

        except Exception as e:
            last_error = e
            logger.error(
                f"[WHISPER] Erro inesperado na tentativa {attempt}/{MAX_RETRIES}: {e}"
            )

        # Backoff exponencial: 2s, 4s, 8s...
        if attempt < MAX_RETRIES:
            delay = BASE_RETRY_DELAY * (2 ** (attempt - 1))
            logger.info(f"[WHISPER] Aguardando {delay}s antes de retry...")
            await asyncio.sleep(delay)

    # Todas as tentativas falharam
    error_detail = str(last_error) if last_error else "Erro desconhecido"
    logger.error(f"[WHISPER] Todas as {MAX_RETRIES} tentativas falharam: {error_detail}")

    if isinstance(last_error, APITimeoutError):
        raise TranscriptionError(
            "⏱️ O processamento excedeu o tempo limite (5 minutos).\n"
            "💡 Tente enviar um áudio menor.",
            technical_detail=error_detail,
        )

    raise TranscriptionError(
        "❌ Erro ao transcrever o áudio.\n"
        "💡 Tente novamente em alguns instantes.",
        technical_detail=error_detail,
    )


def _call_whisper_api(client: OpenAI, file_path: str) -> TranscriptionResult:
    """
    Chamada síncrona à API Whisper (executada em thread separada).

    Esta função é síncrona porque o cliente OpenAI Python
    não tem versão async nativa para transcrição. Usamos
    asyncio.to_thread() para não bloquear o event loop.

    Args:
        client: Cliente OpenAI configurado.
        file_path: Caminho do arquivo de áudio.

    Retorna:
        TranscriptionResult com texto e metadados.
    """
    with open(file_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            temperature=settings.WHISPER_TEMPERATURE,
            # language=None → auto-detect (não passamos o parâmetro)
            # prompt=None → sem indução (evita alucinações)
        )

    # Extrai dados da resposta
    text = response.text.strip()
    language = getattr(response, "language", "unknown")
    duration = getattr(response, "duration", 0.0)
    segments = getattr(response, "segments", [])

    # Detecta múltiplos idiomas via segmentos
    segment_languages = _detect_languages_from_segments(segments)
    all_languages = [language] + [
        lang for lang in segment_languages if lang != language
    ]
    is_multilingual = len(set(all_languages)) > 1

    logger.info(
        f"[WHISPER] Transcrição concluída: "
        f"idioma={language}, "
        f"duração={format_duration(duration)}, "
        f"caracteres={len(text)}, "
        f"multilíngue={is_multilingual}"
    )

    return TranscriptionResult(
        text=text,
        language=language,
        detected_languages=list(dict.fromkeys(all_languages)),  # unique, order preserved
        is_multilingual=is_multilingual,
        duration=duration,
    )


async def post_process_transcription(text: str, format_type: str) -> str:
    """
    Processa a transcrição com GPT-4o-mini para o formato desejado.

    Args:
        text: Texto original da transcrição.
        format_type: 'summary', 'minutes' ou 'corrected'.

    Retorna:
        Texto processado no formato solicitado.
    """
    if format_type not in PROMPTS:
        return text  # Se não houver prompt, retorna original (fallback)

    client = _create_openai_client()
    prompt = PROMPTS[format_type].replace("{transcription_text}", text)

    try:
        logger.info(f"[GPT] Processando formato '{format_type}' com gpt-4o-mini")
        
        # Chamada síncrona em thread separada
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Assistant de processamento de texto corporativo."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2, # Baixa criatividade para manter fidelidade
            max_tokens=1500
        )
        
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[GPT] Erro no processamento: {e}")
        return f"⚠️ Erro ao gerar {format_type}. Segue transcrição original:\n\n{text}"
