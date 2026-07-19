# -*- coding: utf-8 -*-
"""
Handlers de autenticação do painel web.
Login, registro, aprovação, gerenciamento de roles.
"""
import datetime
import re
import secrets
import logging

import pytz
from aiohttp import web
from aiohttp_session import get_session

from web.auth import get_db, hash_password, check_password

logger = logging.getLogger("web.auth_routes")


def register_auth_routes(admin_api_app, bot_instance):
    """Registra todas as rotas de auth no sub-app admin."""

    async def api_auth_login(r):
        data = await r.json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        guild_id = data.get('guild_id', '')
        if not username or not password:
            return web.json_response({"status": "error", "message": "Usuário e senha obrigatórios."}, status=400)
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        user = await db.panel_users.find_one({"_id": username})
        if not user or user.get('status') != 'active':
            return web.json_response({"status": "error", "message": "Usuário não encontrado ou inativo."}, status=401)
        if not check_password(password, user['password_hash']):
            return web.json_response({"status": "error", "message": "Senha incorreta."}, status=401)
        session = await get_session(r)
        session['authenticated'] = True
        session['username'] = username
        session['role'] = user['role']
        session['guild_id'] = guild_id if guild_id else None
        session['csrf_token'] = secrets.token_hex(32)
        return web.json_response({"status": "success", "role": user['role'], "username": username})

    async def api_auth_register(r):
        data = await r.json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        discord_user = data.get('discord', '')
        if not username or not password or len(username) < 3 or len(password) < 4:
            return web.json_response({"status": "error", "message": "Usuário (3+ chars) e senha (4+ chars) obrigatórios."}, status=400)
        if not re.match(r'^[a-z0-9_]+$', username):
            return web.json_response({"status": "error", "message": "Usuário apenas letras minúsculas, números e underscore."}, status=400)
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        existing = await db.panel_users.find_one({"_id": username})
        if existing:
            return web.json_response({"status": "error", "message": "Usuário já existe."}, status=409)
        await db.panel_users.insert_one({
            "_id": username,
            "password_hash": hash_password(password),
            "role": "viewer",
            "status": "pending",
            "discord": discord_user,
            "created_at": datetime.datetime.now(pytz.utc),
            "approved_by": None,
            "approved_at": None,
        })
        return web.json_response({"status": "success", "message": "Solicitação enviada! Aguarde aprovação do administrador."})

    async def api_auth_pending(r):
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        cursor = db.panel_users.find({"status": "pending"})
        users = []
        async for doc in cursor:
            users.append({"username": doc["_id"], "discord": doc.get("discord", ""), "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else ""})
        return web.json_response(users)

    async def api_auth_approve(r):
        username = r.match_info.get('username', '').strip().lower()
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        result = await db.panel_users.update_one(
            {"_id": username, "status": "pending"},
            {"$set": {"status": "active", "approved_at": datetime.datetime.now(pytz.utc)}}
        )
        if result.modified_count:
            return web.json_response({"status": "success", "message": f"{username} aprovado!"})
        return web.json_response({"status": "error", "message": "Usuário não encontrado ou já processado."}, status=404)

    async def api_auth_reject(r):
        username = r.match_info.get('username', '').strip().lower()
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        result = await db.panel_users.delete_one({"_id": username, "status": "pending"})
        if result.deleted_count:
            return web.json_response({"status": "success", "message": f"{username} rejeitado e removido."})
        return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

    async def api_auth_role(r):
        data = await r.json()
        target = data.get('username', '').strip().lower()
        new_role = data.get('role', '').strip().lower()
        if not target or new_role not in ('admin', 'viewer'):
            return web.json_response({"status": "error", "message": "Parâmetros inválidos."}, status=400)
        session = await get_session(r)
        actor_role = session.get('role', '')
        if actor_role == 'viewer':
            return web.json_response({"status": "error", "message": "Visualizador não pode alterar roles."}, status=403)
        if session.get('username', '').lower() == target:
            return web.json_response({"status": "error", "message": "Não pode alterar sua própria role."}, status=400)
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        result = await db.panel_users.update_one(
            {"_id": target},
            {"$set": {"role": new_role}}
        )
        if result.modified_count:
            return web.json_response({"status": "success", "message": f"{target} agora é {new_role}."})
        return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

    async def api_auth_users(r):
        db = get_db(bot_instance)
        if isinstance(db, web.Response):
            return db

        cursor = db.panel_users.find({})
        users = []
        async for doc in cursor:
            users.append({
                "username": doc["_id"],
                "role": doc.get("role", "viewer"),
                "status": doc.get("status", "active"),
                "discord": doc.get("discord", ""),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
            })
        return web.json_response(users)

    async def api_auth_me(r):
        session = await get_session(r)
        username = session.get('username', '')
        role = session.get('role', '')
        return web.json_response({"username": username, "role": role, "authenticated": bool(role or session.get('admin'))})

    # Registrar rotas
    admin_api_app.router.add_post("/auth/login", api_auth_login)
    admin_api_app.router.add_post("/auth/register", api_auth_register)
    admin_api_app.router.add_get("/auth/pending", api_auth_pending)
    admin_api_app.router.add_post("/auth/approve/{username:.*}", api_auth_approve)
    admin_api_app.router.add_post("/auth/reject/{username:.*}", api_auth_reject)
    admin_api_app.router.add_get("/auth/users", api_auth_users)
    admin_api_app.router.add_get("/auth/me", api_auth_me)
    admin_api_app.router.add_post("/auth/role", api_auth_role)
