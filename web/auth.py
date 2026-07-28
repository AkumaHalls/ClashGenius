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
    Retorna uma tupla (db, None) se OK, ou (None, json_response) se o banco
    não estiver disponível — os callers devem usar:
        db, err = get_db(bot_instance)
        if err: return err
    """
    db = getattr(bot_instance, 'db', None)
    if db is None:
        return None, web.json_response(
            {"status": "error", "message": "Banco de dados não disponível."},
            status=503
        )
    return db, None


def hash_password(password: str) -> str:
    """Gera hash da senha com PBKDF2 + salt aleatório."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f"{salt}${pwd_hash}"


def check_password(password: str, stored: str) -> bool:
    """Verifica se a senha confere com o hash armazenado (comparação timing-safe)."""
    try:
        salt, pwd_hash = stored.split('$', 1)
        computed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
        return secrets.compare_digest(computed, pwd_hash)
    except (ValueError, AttributeError) as e:
        logger.warning("check_password: formato de hash inválido — %s", e)
        return False
