"""
bot/auth.py - Sistema de autenticação por senha.

Controle de acesso simples para uso pessoal do bot.
Apenas usuários que souberem a senha (definida em BOT_PASSWORD)
podem enviar áudios para transcrição.

Como funciona:
    1. Usuário envia: /start MINHA_SENHA
    2. Bot compara com BOT_PASSWORD do .env
    3. Se correto, user_id é salvo em authorized_users.json
    4. Nas próximas interações, bot verifica se user_id está na lista
    5. Não precisa autenticar novamente (persistente)

Segurança:
    - Senha comparada com hmac.compare_digest (resistente a timing attacks)
    - Arquivo JSON salvo localmente (funciona sem banco de dados)
    - Em produção (Railway), o arquivo persiste entre restarts
      dentro do mesmo deploy (não entre redeploys)

Uso:
    from bot.auth import is_authorized, authenticate_user

    if is_authorized(user_id):
        # processar áudio
    else:
        # pedir autenticação
"""

import json
import hmac
import logging
import os
from pathlib import Path

from bot.utils import mask_user_id
from config.settings import settings

logger = logging.getLogger(__name__)

# Caminho do arquivo de usuários autorizados
_AUTH_FILE = Path(settings.DATA_DIR) / "authorized_users.json"


def _ensure_data_dir() -> None:
    """Cria o diretório de dados se não existir."""
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)


def _load_authorized_users() -> set[int]:
    """
    Carrega a lista de user_ids autorizados do arquivo JSON.

    Retorna:
        set[int]: Conjunto de IDs de usuários autorizados.
                  Retorna set vazio se o arquivo não existir.
    """
    if not _AUTH_FILE.exists():
        return set()

    try:
        with open(_AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("authorized_users", []))
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao ler arquivo de autorizados: {e}")
        return set()


def _save_authorized_users(users: set[int]) -> None:
    """
    Salva a lista de user_ids autorizados no arquivo JSON.

    Args:
        users: Conjunto de IDs de usuários autorizados.
    """
    _ensure_data_dir()

    try:
        with open(_AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"authorized_users": sorted(users)},
                f,
                indent=2,
            )
        logger.info(f"Lista de autorizados atualizada: {len(users)} usuário(s)")
    except IOError as e:
        logger.error(f"Erro ao salvar arquivo de autorizados: {e}")


def is_authorized(user_id: int) -> bool:
    """
    Verifica se um usuário está autorizado a usar o bot.

    Args:
        user_id: ID do usuário no Telegram.

    Retorna:
        True se o usuário já se autenticou com a senha correta.
    """
    authorized = _load_authorized_users()
    return user_id in authorized


def authenticate_user(user_id: int, password: str) -> bool:
    """
    Tenta autenticar um usuário com a senha fornecida.

    Usa hmac.compare_digest para comparação segura da senha
    (resistente a timing attacks — um atacante não consegue
    descobrir a senha medindo o tempo de resposta).

    Args:
        user_id: ID do usuário no Telegram.
        password: Senha fornecida pelo usuário.

    Retorna:
        True se a senha está correta e o usuário foi autorizado.
    """
    # Comparação segura contra timing attacks
    is_valid = hmac.compare_digest(password.strip(), settings.BOT_PASSWORD)

    if is_valid:
        users = _load_authorized_users()
        users.add(user_id)
        _save_authorized_users(users)
        logger.info(f"[AUTH] Usuário {mask_user_id(user_id)} autenticado com sucesso")
        return True

    logger.warning(f"[AUTH] Tentativa de autenticação falhou para usuário {mask_user_id(user_id)}")
    return False


def revoke_user(user_id: int) -> bool:
    """
    Remove a autorização de um usuário.

    Útil caso você precise bloquear alguém que tenha
    descoberto a senha.

    Args:
        user_id: ID do usuário a ser removido.

    Retorna:
        True se o usuário estava autorizado e foi removido.
    """
    users = _load_authorized_users()

    if user_id in users:
        users.discard(user_id)
        _save_authorized_users(users)
        logger.info(f"[AUTH] Usuário {mask_user_id(user_id)} teve acesso revogado")
        return True

    return False
