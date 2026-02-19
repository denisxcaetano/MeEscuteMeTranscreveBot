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
    CallbackQueryHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Conflict

from bot.audio_processor import (
    AudioValidationError,
    download_and_prepare_audio,
    get_audio_duration,
    validate_audio_size,
)
from bot.auth import authenticate_user, is_authorized
from bot.transcription import TranscriptionError, transcribe_audio, post_process_transcription
from bot.utils import (
    cleanup_file,
    format_duration,
    format_file_size,
    get_language_name,
    mask_user_id,
)

# Rate limiting e anti-brute force (em memória)
# {user_id: [timestamps_das_requests]}
_user_requests: dict[int, list[float]] = {}
# {user_id: {"attempts": int, "lockout_until": float}}
_auth_attempts: dict[int, dict] = {}

# Cache temporário de áudio para seleção de formato
# {user_id: {"file_id": str, "timestamp": float, "original_filename": str}}
_audio_cache: dict[int, dict] = {}

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

    logger.info(f"[CMD] /start de {user.first_name} (ID: {mask_user_id(user_id)})")

    # ---------- 1. Verifica Lockout ----------
    is_locked, time_left = _check_auth_lockout(user_id)
    if is_locked:
        await update.message.reply_text(
            f"🚫 *Acesso Bloqueado*\n\n"
            f"Muitas tentativas incorretas\\.\n"
            f"Tente novamente em {format_duration(time_left)}\\.",
            parse_mode="MarkdownV2"
        )
        return

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
        # Sucesso: Limpa tentativas
        if user_id in _auth_attempts:
            _auth_attempts.pop(user_id)
            
        await update.message.reply_text(
            AUTH_SUCCESS_MESSAGE,
            parse_mode="MarkdownV2",
        )
    else:
        # Falha: Registra tentativa
        _register_auth_failure(user_id)
        
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


def _check_rate_limit(user_id: int) -> bool:
    """
    Verifica se o usuário atingiu o limite de requests (5 por minuto).

    Args:
        user_id: ID do usuário no Telegram.

    Retorna:
        True se estiver dentro do limite, False se excedeu.
    """
    now = time.time()
    if user_id not in _user_requests:
        _user_requests[user_id] = []

    # Remove timestamps antigos (> 60s)
    _user_requests[user_id] = [t for t in _user_requests[user_id] if now - t < 60]

    # Verifica o limite
    if len(_user_requests[user_id]) >= 5:
        return False

    # Registra a nova request
    _user_requests[user_id].append(now)
    return True


def _check_auth_lockout(user_id: int) -> tuple[bool, float]:
    """
    Verifica se o usuário está em lockout (bloqueado por muitas tentativas).

    Retorna:
        (is_locked, time_left_seconds)
    """
    if user_id not in _auth_attempts:
        return False, 0.0

    state = _auth_attempts[user_id]
    now = time.time()

    # Verifica se o tempo de bloqueio já passou
    if state.get("lockout_until", 0) > now:
        return True, state["lockout_until"] - now

    # Se passou do tempo e tinha bloqueio, reseta tentativas
    if state.get("lockout_until", 0) > 0:
        _auth_attempts.pop(user_id)
        return False, 0.0

    return False, 0.0


def _register_auth_failure(user_id: int) -> None:
    """Registra uma falha de autenticação e aplica lockout se necessário."""
    now = time.time()
    if user_id not in _auth_attempts:
        _auth_attempts[user_id] = {"attempts": 0, "lockout_until": 0}

    _auth_attempts[user_id]["attempts"] += 1

    # Após 5 tentativas, bloqueia por 10 minutos
    if _auth_attempts[user_id]["attempts"] >= 5:
        _auth_attempts[user_id]["lockout_until"] = now + 600  # 10 min
        logger.warning(f"[AUTH] Usuário {user_id} BLOQUEADO por 10 min (brute-force)")


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

    # ---------- 1.1 Rate Limiting ----------
    if not _check_rate_limit(user_id):
        logger.warning(f"[RATE-LIMIT] Usuário {user_id} excedeu o limite")
        await update.message.reply_text(
            "⏳ *Calma lá\\!*\n\n"
            "Você atingiu o limite de 5 áudios por minuto\\.\n"
            "Aguarde um instante antes de mandar o próximo\\.",
            parse_mode="MarkdownV2"
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
        f"[AUDIO] Recebido de {user.first_name} (ID: {mask_user_id(user_id)}): "
        f"tamanho={format_file_size(file_size)}, "
        f"arquivo={original_filename or 'voice_message'}"
    )

    # ---------- 3. Valida tamanho ----------
    try:
        validate_audio_size(file_size)
    except AudioValidationError as e:
        await update.message.reply_text(e.user_message)
        return

    # ---------- 4. Armazena em cache e pede formato ----------
    _audio_cache[user_id] = {
        "file_id": file_id,
        "timestamp": time.time(),
        "original_filename": original_filename,
    }

    keyboard = [
        [
            InlineKeyboardButton("📄 Resumo", callback_data="fmt_summary"),
            InlineKeyboardButton("📋 Ata", callback_data="fmt_minutes"),
        ],
        [
            InlineKeyboardButton("✍️ Correção", callback_data="fmt_corrected"),
            InlineKeyboardButton("📝 Crua", callback_data="fmt_raw"),
        ],
    ]

    try:
        await update.message.reply_text(
            "🎙️ <b>Áudio recebido!</b> Como deseja o texto?\n\n"
            "📄 <b>Resumo</b>: Pontos principais (BLUF)\n"
            "📋 <b>Ata</b>: Formato corporativo\n"
            "✍️ <b>Correção</b>: Texto corrigido e formatado\n"
            "📝 <b>Crua</b>: Transcrição exata do áudio",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"[ERROR] Falha ao enviar menu de opções: {e}")
        await update.message.reply_text("❌ Erro ao exibir opções. Tente novamente.")



async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a escolha do formato de transcrição.
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id
    
    # Extrai o formato (ex: "fmt_summary" -> "summary")
    format_type = query.data.replace("fmt_", "")

    # Valida Cache
    start_time = time.time()
    cached_data = _audio_cache.get(user_id)

    if not cached_data:
        await query.edit_message_text("❌ Erro: Áudio expirado ou não encontrado. Envie novamente.")
        return

    # Verifica TTL (1 hora)
    if start_time - cached_data["timestamp"] > 3600:
        _audio_cache.pop(user_id)
        await query.edit_message_text("❌ Erro: Áudio expirado. Envie novamente.")
        return

    file_id = cached_data["file_id"]
    original_filename = cached_data["original_filename"]

    # Limpa cache para economizar memória (já pegamos o que precisava enviando para processamento)
    _audio_cache.pop(user_id)

    # Feedback visual
    await query.edit_message_text(f"🎙️ Processando: {format_type.title()}...")
    
    # Processamento (reaproveitando lógica do audio_handler antigo)
    audio_path = None
    
    try:
        # Download e conversão
        telegram_file = await context.bot.get_file(file_id)
        audio_path = await download_and_prepare_audio(
            telegram_file,
            original_filename=original_filename,
        )

        # Transcrição Whisper
        result = await transcribe_audio(audio_path)
        
        # Pós-processamento GPT
        final_text = result.text
        if format_type != "raw":
            await query.edit_message_text(f"🤖 Gerando {format_type} com IA...")
            final_text = await post_process_transcription(result.text, format_type)

        elapsed = time.time() - start_time

        logger.info(
            f"[RESULTADO] Finalizado: {format_type} | "
            f"Duração áudio: {format_duration(result.duration)}"
        )

        response = _format_transcription_response(result, final_text, format_type, elapsed)
        
        # Envia resultado (apaga msg de status anterior se possível ou edita)
        # Editando a mensagem do botão para o resultado final
        # Se for muito longo, manda chunks
        if len(response) > 4000:
            await query.delete_message()
            await _send_long_message(query, response) # query tem message associada
        else:
            await query.edit_message_text(response)

    except Exception as e:
        logger.error(f"Erro no callback: {e}")
        await query.edit_message_text("❌ Ocorreu um erro no processamento.")
        
    finally:
        if audio_path:
            cleanup_file(audio_path)


def _format_transcription_response(result, final_text: str, format_type: str, elapsed: float) -> str:
    """
    Formata a resposta final.
    """
    titles = {
        "raw": "Transcrição Crua",
        "summary": "Resumo Executivo",
        "minutes": "Ata Profissional",
        "corrected": "Texto Corrigido"
    }
    
    header = f"📝 {titles.get(format_type, 'Resultado')}"
    
    lines = [
        header,
        "─────────────────",
        "",
        final_text,
        "",
        "─────────────────",
    ]

    lines.append(f"🌐 Idioma: {result.language_name}")
    if result.duration > 0:
        lines.append(f"⏱️ Duração: {format_duration(result.duration)}")
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


async def _send_long_message(update_or_query, text: str) -> None:
    """
    Envia mensagens longas divididas em partes de 4000 caracteres.
    Suporta tanto Update quanto CallbackQuery.
    """
    max_len = 4000
    
    # Define a função de envio baseada no tipo de objeto
    async def send_chunk(chunk):
        if hasattr(update_or_query, "message") and update_or_query.message:
             # É um CallbackQuery ou Update com message
             # Se for CallbackQuery, usamos message.reply_text
             target = update_or_query.message
             await target.reply_text(chunk)
        else:
             # É um Update direto
             await update_or_query.message.reply_text(chunk)

    while text:
        if len(text) <= max_len:
            await send_chunk(text)
            break
        
        # Encontra o último espaço ou newline antes do limite
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_len)
        if split_pos == -1:
            split_pos = max_len

        chunk = text[:split_pos]
        text = text[split_pos:].lstrip()
        
        await send_chunk(chunk)


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

    # Trata erro de conflito (múltiplas instâncias)
    if isinstance(context.error, Conflict):
        logger.critical(
            "🛑 CONFLITO DETECTADO: Outra instância do bot esta rodando com o mesmo token!\n"
            "   ⚠️ AÇÃO NECESSÁRIA: Feche outros terminais ou pare o bot antigo."
        )
        return

    # Tenta notificar o usuário para outros erros
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

    # Handler de Callback dos Botões
    application.add_handler(CallbackQueryHandler(callback_handler, pattern="^fmt_"))

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
