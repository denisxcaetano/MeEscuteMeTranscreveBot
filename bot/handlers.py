"""
bot/handlers.py - Handlers de comandos e mensagens do Telegram.

Define todos os handlers que o bot registra para responder a
eventos do Telegram. Cada handler é uma função async que recebe
o contexto do Telegram e processa a ação.

Handlers registrados:
    /start [senha] — Autenticação do usuário
    /help           — Instruções de uso
    (áudio/voz)     — Recebe e transcreve áudio

Fluxo principal de transcrição:
    1. Verifica autenticação do usuário
    2. Valida tamanho do arquivo
    3. Envia "🎙️ Processando..."
    4. Faz download e conversão do áudio
    5. Envia para Whisper API
    6. Retorna transcrição formatada

Uso:
    from bot.handlers import setup_handlers
    setup_handlers(application)
"""

import logging
import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.audio_processor import (
    AudioValidationError,
    download_and_prepare_audio,
    get_audio_duration,
    validate_audio_size,
)
from bot.auth import authenticate_user, is_authorized
from bot.transcription import TranscriptionError, transcribe_audio
from bot.utils import (
    cleanup_file,
    format_duration,
    format_file_size,
    get_language_name,
)

logger = logging.getLogger(__name__)


# ============================================================
# Mensagens do Bot (centralizadas para fácil manutenção)
# ============================================================
# Usar Markdown V2 do Telegram para formatação.
# Caracteres especiais precisam de escape com \.
# ============================================================

WELCOME_MESSAGE = (
    "🎙️ *Bot de Transcrição de Áudio*\n\n"
    "Envie um áudio ou mensagem de voz e eu transcrevo para texto\\!\n\n"
    "📌 *Idiomas*: Português \\(BR\\), Inglês, Espanhol \\+ auto\\-detect\n"
    "📏 *Limite*: 25MB por áudio\n"
    "🎯 *Precisão*: Máxima \\(temperatura 0\\)\n\n"
    "Basta enviar o áudio\\! 🎧"
)

AUTH_REQUIRED_MESSAGE = (
    "🔒 *Acesso protegido*\n\n"
    "Use `/start SUA_SENHA` para autenticar\\.\n\n"
    "_Este bot é de uso pessoal e requer senha\\._"
)

AUTH_SUCCESS_MESSAGE = (
    "✅ *Autenticado com sucesso\\!*\n\n"
    "🎙️ Agora é só enviar um áudio ou mensagem de voz\\!\n\n"
    "📌 *Idiomas suportados*: Português \\(BR\\), Inglês, Espanhol\n"
    "📏 *Limite*: 25MB por áudio\n"
    "🎯 *Precisão*: Máxima \\(sem alucinações\\)\n\n"
    "Use /help para mais informações\\."
)

AUTH_FAILED_MESSAGE = (
    "❌ *Senha incorreta*\n\n"
    "Tente novamente com `/start SUA_SENHA`\\.\n\n"
    "_Dica: a senha é definida na variável BOT\\_PASSWORD\\._"
)

HELP_MESSAGE = (
    "📖 *Como usar o bot*\n\n"
    "*Comandos:*\n"
    "  /start \\[senha\\] — Autenticar\n"
    "  /help — Esta mensagem\n\n"
    "*Transcrição:*\n"
    "  1\\. Envie um áudio ou mensagem de voz\n"
    "  2\\. Aguarde o processamento\n"
    "  3\\. Receba a transcrição\\!\n\n"
    "*Idiomas suportados:*\n"
    "  🇧🇷 Português \\(BR\\)\n"
    "  🇺🇸 Inglês\n"
    "  🇪🇸 Espanhol\n"
    "  \\+ 50\\+ idiomas com auto\\-detect\n\n"
    "*Formatos aceitos:*\n"
    "  MP3, OGG, WAV, M4A, FLAC, AAC, OPUS, WebM\n\n"
    "*Limites:*\n"
    "  📏 Tamanho: 25MB\n"
    "  ⏱️ Timeout: 5 minutos\n\n"
    "*Precisão:*\n"
    "  🎯 Temperatura 0 \\(zero alucinações\\)\n"
    "  🤖 Sem prompts indutivos\n"
    "  🌍 Detecção automática de idioma"
)

PROCESSING_MESSAGE = "🎙️ Processando áudio..."


# ============================================================
# Handlers
# ============================================================


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para o comando /start.

    Se receber senha como argumento, tenta autenticar.
    Se já autenticado, mostra mensagem de boas-vindas.
    Se não autenticado e sem senha, pede autenticação.

    Uso:
        /start              → Verifica se já autenticado
        /start minha_senha  → Tenta autenticar com a senha
    """
    user = update.effective_user
    user_id = user.id

    logger.info(f"[CMD] /start de {user.first_name} (ID: {user_id})")

    # Se já está autenticado, mostra boas-vindas
    if is_authorized(user_id):
        await update.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode="MarkdownV2",
        )
        return

    # Verifica se enviou senha como argumento
    args = context.args
    if not args:
        await update.message.reply_text(
            AUTH_REQUIRED_MESSAGE,
            parse_mode="MarkdownV2",
        )
        return

    # Tenta autenticar com a senha fornecida
    password = " ".join(args)  # Suporta senhas com espaços

    if authenticate_user(user_id, password):
        await update.message.reply_text(
            AUTH_SUCCESS_MESSAGE,
            parse_mode="MarkdownV2",
        )
    else:
        await update.message.reply_text(
            AUTH_FAILED_MESSAGE,
            parse_mode="MarkdownV2",
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para o comando /help.

    Mostra instruções de uso, idiomas suportados e limites.
    Disponível para todos (não requer autenticação).
    """
    logger.info(f"[CMD] /help de {update.effective_user.first_name}")

    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode="MarkdownV2",
    )


async def audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensagens de áudio e voz.

    Pipeline completo de transcrição:
        1. Verifica autenticação
        2. Valida tamanho do arquivo
        3. Envia indicador de processamento
        4. Download e conversão do áudio
        5. Transcrição via Whisper
        6. Formatação e envio da resposta
        7. Limpeza de arquivos temporários
    """
    user = update.effective_user
    user_id = user.id

    # ---------- 1. Verifica autenticação ----------
    if not is_authorized(user_id):
        await update.message.reply_text(
            AUTH_REQUIRED_MESSAGE,
            parse_mode="MarkdownV2",
        )
        return

    # ---------- 2. Identifica o tipo de mensagem ----------
    # Voice = mensagem de voz gravada direto no Telegram
    # Audio = arquivo de áudio enviado como documento
    # Document = pode ser um arquivo de áudio enviado como documento
    voice = update.message.voice
    audio = update.message.audio
    document = update.message.document

    if voice:
        file_id = voice.file_id
        file_size = voice.file_size or 0
        original_filename = None  # Voice messages não têm nome
        duration_hint = voice.duration or 0
    elif audio:
        file_id = audio.file_id
        file_size = audio.file_size or 0
        original_filename = audio.file_name
        duration_hint = audio.duration or 0
    elif document:
        file_id = document.file_id
        file_size = document.file_size or 0
        original_filename = document.file_name
        duration_hint = 0
    else:
        return  # Não deveria chegar aqui, mas segurança extra

    logger.info(
        f"[AUDIO] Recebido de {user.first_name} (ID: {user_id}): "
        f"tamanho={format_file_size(file_size)}, "
        f"arquivo={original_filename or 'voice_message'}"
    )

    # ---------- 3. Valida tamanho ----------
    try:
        validate_audio_size(file_size)
    except AudioValidationError as e:
        await update.message.reply_text(e.user_message)
        return

    # ---------- 4. Mensagem de processamento ----------
    processing_msg = await update.message.reply_text(
        PROCESSING_MESSAGE,
    )

    # Mostra indicador "digitando..." no chat
    await update.effective_chat.send_action(ChatAction.TYPING)

    # ---------- 5. Download e conversão ----------
    audio_path = None
    start_time = time.time()

    try:
        # Obtém o arquivo do Telegram
        telegram_file = await context.bot.get_file(file_id)

        # Download + conversão para MP3
        audio_path = await download_and_prepare_audio(
            telegram_file,
            original_filename=original_filename,
        )

        # Obtém duração real do áudio
        duration = get_audio_duration(audio_path)

        # Atualiza mensagem de processamento com duração estimada
        if duration > 0:
            est_time = max(10, duration * 0.1)  # ~10% da duração como estimativa
            await processing_msg.edit_text(
                f"🎙️ Transcrevendo áudio ({format_duration(duration)})...\n"
                f"⏱️ Estimativa: ~{format_duration(est_time)}",
            )

        # Manter indicador de digitando durante a transcrição
        await update.effective_chat.send_action(ChatAction.TYPING)

        # ---------- 6. Transcrição ----------
        result = await transcribe_audio(audio_path)

        elapsed = time.time() - start_time

        logger.info(
            f"[RESULTADO] Transcrição completa: "
            f"idioma={result.language}, "
            f"duração_audio={format_duration(result.duration)}, "
            f"tempo_processamento={format_duration(elapsed)}, "
            f"caracteres={len(result.text)}"
        )

        # ---------- 7. Formata e envia resposta ----------
        response = _format_transcription_response(result, elapsed)

        # Deleta a mensagem "Processando..."
        await processing_msg.delete()

        # Envia a transcrição
        # Se o texto for muito longo, divide em partes
        if len(response) > 4000:
            await _send_long_message(update, response)
        else:
            await update.message.reply_text(response)

    except AudioValidationError as e:
        await processing_msg.edit_text(e.user_message)
        logger.warning(f"[ERRO] Validação de áudio falhou: {e.user_message}")

    except TranscriptionError as e:
        await processing_msg.edit_text(e.user_message)
        logger.error(
            f"[ERRO] Transcrição falhou: {e.user_message} | "
            f"Detalhe: {e.technical_detail}"
        )

    except Exception as e:
        await processing_msg.edit_text(
            "❌ Erro inesperado ao processar o áudio.\n"
            "💡 Tente enviar novamente."
        )
        logger.exception(f"[ERRO] Erro inesperado no handler de áudio: {e}")

    finally:
        # ---------- 8. Limpeza ----------
        if audio_path:
            cleanup_file(audio_path)


def _format_transcription_response(result, elapsed: float) -> str:
    """
    Formata a resposta da transcrição para o Telegram.

    Usa texto puro (sem MarkdownV2) para evitar problemas
    de escape com conteúdo dinâmico da transcrição.

    Layout:
        📝 Transcrição
        ─────────────
        [texto transcrito]
        ─────────────
        🌐 Idioma: 🇧🇷 Português
        ⏱️ Duração: 2min 30s
        ⚡ Processado em: 15s

    Args:
        result: TranscriptionResult da transcrição.
        elapsed: Tempo de processamento em segundos.

    Retorna:
        String formatada em texto puro para o Telegram.
    """
    # Monta a resposta em texto puro (mais robusto que MarkdownV2)
    lines = [
        "📝 Transcrição",
        "─────────────────",
        "",
        result.text,
        "",
        "─────────────────",
    ]

    # Idioma detectado
    lines.append(f"🌐 Idioma: {result.language_name}")

    # Se multilíngue, mostrar todos os idiomas
    if result.is_multilingual:
        lang_list = ", ".join(
            get_language_name(lang)
            for lang in result.detected_languages
        )
        lines.append(f"🌍 Multilíngue: {lang_list}")

    # Duração do áudio
    if result.duration > 0:
        lines.append(f"⏱️ Duração: {format_duration(result.duration)}")

    # Tempo de processamento
    lines.append(f"⚡ Processado em: {format_duration(elapsed)}")

    return "\n".join(lines)


def _escape_markdown_v2(text: str) -> str:
    """
    Escapa caracteres especiais do MarkdownV2 do Telegram.

    O Telegram exige que certos caracteres sejam escapados
    com backslash no modo MarkdownV2.

    Referência: https://core.telegram.org/bots/api#markdownv2-style

    Args:
        text: Texto a ser escapado.

    Retorna:
        Texto com caracteres especiais escapados.
    """
    # Caracteres que precisam de escape no MarkdownV2
    special_chars = [
        '_', '*', '[', ']', '(', ')', '~', '`',
        '>', '#', '+', '-', '=', '|', '{', '}',
        '.', '!'
    ]

    for char in special_chars:
        text = text.replace(char, f"\\{char}")

    return text


async def _send_long_message(update: Update, text: str) -> None:
    """
    Envia mensagens longas divididas em partes de 4000 caracteres.

    O Telegram tem limite de 4096 caracteres por mensagem.
    Dividimos em partes menores sem cortar palavras.

    Args:
        update: Objeto Update do Telegram.
        text: Texto completo a ser enviado.
    """
    max_len = 4000

    while text:
        if len(text) <= max_len:
            await update.message.reply_text(text)
            break

        # Encontra o último espaço ou newline antes do limite
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_len)
        if split_pos == -1:
            split_pos = max_len

        chunk = text[:split_pos]
        text = text[split_pos:].lstrip()

        await update.message.reply_text(chunk)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global de erros não capturados.

    Loga o erro completo e tenta notificar o usuário.
    Importante para debugging em produção.
    """
    logger.exception(
        f"[ERRO GLOBAL] Exceção não tratada: {context.error}",
        exc_info=context.error,
    )

    # Tenta notificar o usuário
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Ocorreu um erro inesperado.\n"
                "💡 Tente novamente em alguns instantes."
            )
        except Exception:
            pass  # Se não conseguir notificar, apenas loga


def setup_handlers(application: Application) -> None:
    """
    Registra todos os handlers no application do Telegram.

    Ordem de registro importa! O Telegram processa handlers
    na ordem em que foram adicionados. Comandos específicos
    devem vir antes de handlers genéricos.

    Args:
        application: Objeto Application do python-telegram-bot.
    """
    # Comandos
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))

    # Mensagens de voz (gravadas no Telegram)
    application.add_handler(MessageHandler(filters.VOICE, audio_handler))

    # Arquivos de áudio (enviados como mídia)
    application.add_handler(MessageHandler(filters.AUDIO, audio_handler))

    # Documentos que podem ser áudio (enviados como arquivo)
    application.add_handler(
        MessageHandler(
            filters.Document.MimeType("audio/mpeg")
            | filters.Document.MimeType("audio/mp3")
            | filters.Document.MimeType("audio/ogg")
            | filters.Document.MimeType("audio/wav")
            | filters.Document.MimeType("audio/x-wav")
            | filters.Document.MimeType("audio/flac")
            | filters.Document.MimeType("audio/aac")
            | filters.Document.MimeType("audio/m4a")
            | filters.Document.MimeType("audio/mp4")
            | filters.Document.MimeType("audio/x-m4a")
            | filters.Document.MimeType("audio/webm")
            | filters.Document.MimeType("audio/opus")
            | filters.Document.MimeType("video/mp4")  # Vídeos podem ter áudio
            | filters.Document.MimeType("video/webm"),
            audio_handler,
        )
    )

    # Handler global de erros
    application.add_error_handler(error_handler)

    logger.info("[SETUP] Todos os handlers registrados com sucesso")
