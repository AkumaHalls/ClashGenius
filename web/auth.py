# -*- coding: utf-8 -*-
"""
Helpers de autenticação e acesso ao banco de dados.
"""
import hashlib
import secrets
import logging

from aiohttp import web
from aiohttp_session import get_session

logger = logging.getLogger("web.auth")


def get_db(bot_instance):
    """Obtém a referência ao banco de dados do bot.
    Retorna None se o banco não estiver disponível — o caller deve
    verificar antes de usar.
    """
    return getattr(bot_instance, 'db', None)


def hash_password(password: str) -> str:
    """Gera hash da senha com PBKDF2 + salt aleatório."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${pwd_hash}"


def check_password(password: str, stored: str) -> bool:
    """Verifica se a senha confere com o hash armazenado."""
    try:
        salt, pwd_hash = stored.split('$', 1)
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex() == pwd_hash
    except (ValueError, AttributeError) as e:
        logger.warning("check_password: formato de hash inválido — %s", e)
        return False


async def require_admin(request, bot_instance):
    """Verifica se a sessão tem permissão de admin.
    Retorna (session, None) se OK, ou (None, json_response) se negado.
    """
    session = await get_session(request)
    role = session.get('role')
    if not role and not session.get('admin'):
        return None, web.json_response({"status": "unauthorized", "message": "Acesso negado."}, status=403)
    return session, None
