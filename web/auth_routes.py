# -*- coding: utf-8 -*-
"""
Handlers de autenticação do painel web.
Login, registro, aprovação, gerenciamento de roles e status (banido/desativado).
"""
import datetime
import logging
import re
import secrets

import pytz
from aiohttp import web
from aiohttp_session import get_session

from web.auth import check_password, get_db, hash_password

logger = logging.getLogger("web.auth_routes")

# Valores aceitos pelo seletor "Ação" do painel admin.
# 'admin'/'viewer' alteram o CARGO (papel). 'desativado'/'banido' alteram o STATUS.
VALID_ROLES = ('admin', 'viewer')
BLOCKING_STATUSES = ('banned', 'disabled')

# Ações de bloqueio aceitas pelo seletor "Ação" do painel admin.
# Chave = rótulo enviado pelo front; valor = status gravado no MongoDB.
STATUS_ACTIONS = {
    'desativado': 'disabled',
    'banido': 'banned',
}

# Ação de senha: NÃO altera o status nem o cargo. Marca a conta para troca
# de senha no próximo login (campo must_change_password).
PASSWORD_ACTION = 'trocar_senha'
PASSWORD_PAGE = '/trocar-senha'
MIN_PASSWORD_LENGTH = 4

# Proteção contra força bruta.
# O bloqueio é POR CONTA (persistido no Mongo) e não só por IP: um atacante
# trocando de origem não contorna. As tentativas ficam na própria conta, então
# o limite tambem e valido em caso de reinicio do bot.
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MAX_PASSWORD_ATTEMPTS = 5

# Recuperação de senha esquecida: o usuário pede, o ADMIN aprova.
# NÃO existe reset automático por e-mail (o bot não tem servidor de e-mail),
# então o pedido só vira uma troca de senha depois que um admin aprova.
PASSWORD_RESET_ACTION = 'aprovar_reset_senha'
PASSWORD_RESET_DENY_ACTION = 'negar_reset_senha'
# Janela em que um pedido continua valendo para o admin ver.
PASSWORD_RESET_TTL_MINUTES = 60


def get_blocking_page(user_status: str) -> str:
    """Mapeia o status do usuário para a página informativa que ele deve ver.

    Retorna 'banido', 'desativado' ou None se o usuário pode acessar normalmente.
    """
    if user_status == 'banned':
        return 'banido'
    if user_status == 'disabled':
        return 'desativado'
    return None


async def api_auth_session_info(r):
    """Retorna info da sessao atual (para debug/test)."""
    session = await get_session(r)
    return web.json_response({
        "csrf_token": session.get("csrf_token", ""),
        "role": session.get("role", ""),
        "username": session.get("username", ""),
        "authenticated": session.get("authenticated", False)
    })

def register_auth_routes(admin_api_app, bot_instance):
    """Registra todas as rotas de auth no sub-app admin."""

    async def _get_lockout(db, username):
        """Retorna o instante do desbloqueio se a conta estiver bloqueada, ou None."""
        doc = await db.panel_users.find_one(
            {"_id": username}, {"locked_until": 1, "failed_login_attempts": 1}
        )
        if not doc:
            return None
        locked_until = doc.get("locked_until")
        if not locked_until:
            return None
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=pytz.utc)
        if locked_until > datetime.datetime.now(pytz.utc):
            return locked_until
        # Bloqueio expirado: limpa o documento para ele nao crescer sem parar.
        await db.panel_users.update_one(
            {"_id": username},
            {"$set": {"locked_until": None, "failed_login_attempts": 0}}
        )
        return None

    async def _register_failure(db, username):
        """Soma uma tentativa falha e bloqueia a conta ao atingir o limite."""
        doc = await db.panel_users.find_one(
            {"_id": username}, {"failed_login_attempts": 1}
        )
        if not doc:
            # Conta inexistente: nada a persistir (o 401 já é genérico).
            return
        attempts = int(doc.get("failed_login_attempts") or 0) + 1
        update = {"failed_login_attempts": attempts}
        if attempts >= MAX_LOGIN_ATTEMPTS:
            until = datetime.datetime.now(pytz.utc) + datetime.timedelta(minutes=LOCKOUT_MINUTES)
            update["locked_until"] = until
            logger.warning(
                "Conta '%s' bloqueada por %d tentativas malsucedidas (ate %s).",
                username, attempts, until.isoformat()
            )
        await db.panel_users.update_one({"_id": username}, {"$set": update})

    async def _clear_failures(db, username):
        await db.panel_users.update_one(
            {"_id": username},
            {"$set": {"failed_login_attempts": 0, "locked_until": None}}
        )

    async def api_auth_login(r):
        data = await r.json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        guild_id = data.get('guild_id', '')
        if not username or not password:
            return web.json_response({"status": "error", "message": "Usuário e senha obrigatórios."}, status=400)
        db, err = get_db(bot_instance)
        if err:
            return err

        # Bloqueio por tentativas excessivas (independe do IP de origem).
        locked_until = await _get_lockout(db, username)
        if locked_until:
            minutes = max(1, int((locked_until - datetime.datetime.now(pytz.utc)).total_seconds() // 60) + 1)
            return web.json_response({
                "status": "error",
                "message": f"Conta temporariamente bloqueada por excesso de tentativas. Tente em ~{minutes} min.",
            }, status=429)

        user = await db.panel_users.find_one({"_id": username})
        if not user:
            return web.json_response({"status": "error", "message": "Credenciais inválidas."}, status=401)

        # Usuário banido ou desativado: confere a senha para não vazar a
        # existência da conta, e então devolve o redirecionamento para a
        # página informativa correspondente.
        user_status = user.get('status', 'active')
        if user_status in BLOCKING_STATUSES:
            if not check_password(password, user['password_hash']):
                await _register_failure(db, username)
                return web.json_response({"status": "error", "message": "Credenciais inválidas."}, status=401)
            page = get_blocking_page(user_status)
            return web.json_response({
                "status": user_status,
                "page": f"/{page}",
                "message": (
                    "Sua conta foi BANIDA. Acesso ao painel permanentemente bloqueado."
                    if user_status == 'banned'
                    else "O acesso da sua conta foi DESATIVADO pela administração."
                ),
            }, status=403)

        if user_status != 'active':
            return web.json_response({"status": "error", "message": "Credenciais inválidas."}, status=401)
        if not check_password(password, user['password_hash']):
            await _register_failure(db, username)
            return web.json_response({"status": "error", "message": "Credenciais inválidas."}, status=401)
        await _clear_failures(db, username)
        session = await get_session(r)
        # Todo login bem-sucedido rotaciona a sessão (anti-fixação) e cria um
        # 'sid' server-side — sem ele o logout não teria nada para revogar.
        session.invalidate()
        session['sid'] = secrets.token_urlsafe(16)
        session['csrf_token'] = secrets.token_hex(32)
        session['authenticated'] = True
        session['username'] = username

        # Admin liberou a troca de senha: abre uma sessão LIMITADA (sem 'role'),
        # que dá acesso apenas à página e ao endpoint de troca de senha.
        if user.get('must_change_password'):
            session['password_change_required'] = True
            session['password_attempts'] = 0
            session.pop('role', None)
            session.pop('admin', None)
            return web.json_response({
                "status": "password_change_required",
                "page": PASSWORD_PAGE,
                "message": "Defina uma nova senha para continuar.",
            })

        session['role'] = user['role']
        session['guild_id'] = guild_id if guild_id else None
        session['password_change_required'] = False
        return web.json_response({"status": "success", "role": user['role'], "username": username})

    async def api_auth_change_password(r):
        """Troca de senha pela sessão limitada criada no login.

        Exige que a sessão tenha 'password_change_required' + 'username'.
        O CSRF continua válido: o middleware de CSRF não isenta esta rota,
        apenas o de autenticação (a sessão não tem 'role' de propósito).
        """
        session = await get_session(r)
        username = session.get('username', '')
        if not username or not session.get('password_change_required'):
            return web.json_response({"status": "error", "message": "Acesso negado."}, status=403)

        # Limite de tentativas por sessão: alguém que conseguiu o login não
        # fica testando combinações indefinidamente.
        attempts = int(session.get('password_attempts') or 0)
        if attempts >= MAX_PASSWORD_ATTEMPTS:
            for k in ['authenticated', 'username', 'role', 'admin', 'guild_id',
                      'password_change_required', 'password_attempts', 'csrf_token']:
                session.pop(k, None)
            logger.warning("Troca de senha de '%s' excedeu o limite de tentativas.", username)
            return web.json_response({
                "status": "error",
                "message": "Muitas tentativas. Entre novamente para continuar.",
            }, status=429)

        data = await r.json()
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')

        def _invalid(message, code=400):
            session['password_attempts'] = attempts + 1
            return web.json_response({"status": "error", "message": message}, status=code)

        if not new_password or not confirm_password:
            return _invalid("Preencha todos os campos.")
        if new_password != confirm_password:
            return _invalid("As senhas não conferem.")
        if len(new_password) < MIN_PASSWORD_LENGTH:
            return _invalid(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.")

        db, err = get_db(bot_instance)
        if err:
            return err

        user = await db.panel_users.find_one({"_id": username})
        if not user:
            return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

        # Conta bloqueada não troca senha por esta via.
        user_status = user.get('status', 'active')
        if user_status in BLOCKING_STATUSES:
            page = get_blocking_page(user_status)
            return web.json_response({
                "status": user_status,
                "page": f"/{page}",
                "message": "Esta conta está bloqueada e não pode alterar a senha.",
            }, status=403)

        # Impede que o usuário "troque" a senha para a mesma que já está em uso.
        if check_password(new_password, user.get('password_hash', '')):
            return _invalid("A nova senha deve ser diferente da atual.")

        await db.panel_users.update_one(
            {"_id": username},
            {"$set": {
                "password_hash": hash_password(new_password),
                "must_change_password": False,
                "password_changed_at": datetime.datetime.now(pytz.utc),
            }}
        )
        logger.info("Senha alterada pelo usuario '%s'", username)

        # Encerra a sessão limitada: o usuário entra novamente com a nova senha.
        for k in ['authenticated', 'username', 'role', 'admin', 'guild_id',
                  'password_change_required', 'password_attempts', 'csrf_token']:
            session.pop(k, None)
        return web.json_response({
            "status": "success",
            "message": "Senha alterada com sucesso! Entre com a nova senha.",
            "page": "/admin",
        })

    async def api_auth_register(r):
        data = await r.json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        discord_user = data.get('discord', '')
        if not username or not password or len(username) < 3 or len(password) < 4:
            return web.json_response({"status": "error", "message": "Usuário (3+ chars) e senha (4+ chars) obrigatórios."}, status=400)
        if not re.match(r'^[a-z0-9_]+$', username):
            return web.json_response({"status": "error", "message": "Usuário apenas letras minúsculas, números e underscore."}, status=400)
        db, err = get_db(bot_instance)
        if err:
            return err

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
        db, err = get_db(bot_instance)
        if err:
            return err

        cursor = db.panel_users.find({"status": "pending"}).limit(100)
        users = []
        async for doc in cursor:
            users.append({"username": doc["_id"], "discord": doc.get("discord", ""), "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else ""})
        await cursor.close()
        return web.json_response(users)

    async def api_auth_approve(r):
        username = r.match_info.get('username', '').strip().lower()
        db, err = get_db(bot_instance)
        if err:
            return err

        result = await db.panel_users.update_one(
            {"_id": username, "status": "pending"},
            {"$set": {"status": "active", "approved_at": datetime.datetime.now(pytz.utc)}}
        )
        if result.modified_count:
            return web.json_response({"status": "success", "message": f"{username} aprovado!"})
        return web.json_response({"status": "error", "message": "Usuário não encontrado ou já processado."}, status=404)

    async def api_auth_reject(r):
        username = r.match_info.get('username', '').strip().lower()
        db, err = get_db(bot_instance)
        if err:
            return err

        result = await db.panel_users.delete_one({"_id": username, "status": "pending"})
        if result.deleted_count:
            return web.json_response({"status": "success", "message": f"{username} rejeitado e removido."})
        return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

    async def api_auth_role(r):
        data = await r.json()
        target = data.get('username', '').strip().lower()
        new_action = data.get('role', '').strip().lower()
        valid_actions = (VALID_ROLES + tuple(STATUS_ACTIONS)
                         + (PASSWORD_ACTION, PASSWORD_RESET_ACTION, PASSWORD_RESET_DENY_ACTION))
        if not target or new_action not in valid_actions:
            return web.json_response({"status": "error", "message": "Parâmetros inválidos."}, status=400)
        session = await get_session(r)
        actor_role = session.get('role', '')
        if actor_role == 'viewer':
            return web.json_response({"status": "error", "message": "Membro Sênior não pode alterar usuários."}, status=403)
        if session.get('username', '').lower() == target:
            return web.json_response({"status": "error", "message": "Não pode alterar sua própria conta."}, status=400)
        db, err = get_db(bot_instance)
        if err:
            return err

        # Registro de auditoria: quem aplicou a ação e quando.
        update = {
            "last_action_by": session.get('username', ''),
            "last_action_at": datetime.datetime.now(pytz.utc),
        }

        if new_action in VALID_ROLES:
            # Trocar o cargo (Admin / Membro Sênior) também reativa a conta,
            # permitindo reverter um banimento ou desativação anterior.
            update["role"] = new_action
            update["status"] = 'active'
            message = f"{target} agora é {'Admin' if new_action == 'admin' else 'Membro Sênior'}."
        elif new_action == PASSWORD_ACTION:
            # Libera a troca de senha no próximo login. Não altera cargo nem status.
            # Também limpa o bloqueio por tentativas: sem isso uma conta travada
            # por força bruta nunca conseguiria entrar para trocar a senha.
            update["must_change_password"] = True
            update["password_reset_by"] = session.get('username', '')
            update["failed_login_attempts"] = 0
            update["locked_until"] = None
            message = (
                f"Troca de senha liberada para {target}. "
                "No próximo login ele deverá definir uma nova senha."
            )
        elif new_action == PASSWORD_RESET_ACTION:
            # Admin APROVA um pedido de "esqueci minha senha". O efeito é o mesmo
            # da troca forçada, mas registra que houve solicitacao do titular.
            update["must_change_password"] = True
            update["password_reset_by"] = session.get('username', '')
            update["password_reset_approved_at"] = datetime.datetime.now(pytz.utc)
            update["password_reset_pending"] = False
            update["failed_login_attempts"] = 0
            update["locked_until"] = None
            message = (
                f"Reset de senha APROVADO para {target}. "
                "No próximo login ele poderá definir uma nova senha."
            )
        elif new_action == PASSWORD_RESET_DENY_ACTION:
            # Admin NEGA o pedido: o titular continua com a senha antiga.
            update["password_reset_pending"] = False
            update["password_reset_denied_by"] = session.get('username', '')
            message = f"Reset de senha NEGADO para {target}."
        else:
            # Bloqueio de acesso: preserva o cargo atual do usuário.
            new_status = STATUS_ACTIONS[new_action]
            update["status"] = new_status
            message = (
                f"{target} foi BANIDO. O acesso ao painel está bloqueado."
                if new_status == 'banned'
                else f"O acesso de {target} foi DESATIVADO."
            )

        result = await db.panel_users.update_one(
            {"_id": target, "status": {"$ne": "pending"}},
            {"$set": update}
        )
        if result.matched_count:
            return web.json_response({"status": "success", "message": message})
        return web.json_response({"status": "error", "message": "Usuário não encontrado ou ainda aguardando aprovação."}, status=404)

    async def api_auth_delete(r):
        """Exclui definitivamente uma conta do painel.

        Destrutivo e sem volta: por isso exige o nome de usuario E a senha
        do proprio admin no corpo da requisicao. Um admin nao pode excluir a
        si mesmo, e o ultimo admin nunca pode ser removido (o acesso ainda
        seria possivel pela senha mestra, mas o painel ficaria sem gestao).

        Complementa 'desativado'/'banido', que sao reversiveis e preferiveis
        sempre que o objetivo for apenas Tirar o acesso da conta.
        """
        username = r.match_info.get('username', '').strip().lower()
        data = await r.json()
        session = await get_session(r)

        if session.get('username', '').lower() == username:
            return web.json_response({
                "status": "error",
                "message": "Você não pode excluir a própria conta.",
            }, status=400)

        db, err = get_db(bot_instance)
        if err:
            return err

        user = await db.panel_users.find_one({"_id": username})
        if not user:
            return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

        # Confere a senha de quem esta excluindo. Existem dois tipos de sessao
        # admin e cada uma tem uma credencial diferente:
        #   - conta real em panel_users -> confere o hash guardado dela;
        #   - login pela senha mestra ('root', sem documento no banco) ->
        #     confere a ADMIN_PASSWORD, que e a mesma credencial do login.
        # Sem esse desvio, quem entra pela senha mestra nunca conseguiria
        # excluir nada: nao ha hash de onde tirar.
        admin_username = session.get('username', '')
        admin_doc = await db.panel_users.find_one({"_id": admin_username}) if admin_username else None
        admin_hash = (admin_doc or {}).get('password_hash', '')

        confirm_name = (data.get('username') or '').strip()
        confirm_pass = data.get('password') or ''

        if admin_hash:
            password_ok = check_password(confirm_pass, admin_hash)
        else:
            # Import local, como em web/admin_routes.py, para nao acoplar a
            # importacao deste modulo ao config na hora do carregamento.
            from config import ADMIN_PASSWORD
            password_ok = bool(ADMIN_PASSWORD) and secrets.compare_digest(confirm_pass, ADMIN_PASSWORD)

        if confirm_name != username or not password_ok:
            return web.json_response({
                "status": "error",
                "message": "Confirmação inválida: digite exatamente o usuário e a sua senha atual.",
            }, status=403)

        # Guarda: a conta alvo precisa ser admin para a contagem abaixo importar.
        if user.get('role') == 'admin':
            remaining = await db.panel_users.count_documents({
                "role": "admin",
                "_id": {"$nin": [username, 'root']},
            })
            if remaining == 0:
                return web.json_response({
                    "status": "error",
                    "message": "Não é possível excluir o último administrador do painel.",
                }, status=400)

        result = await db.panel_users.delete_one({"_id": username})
        if result.deleted_count:
            logger.warning(
                "Conta '%s' EXCLUIDA por '%s'.", username, admin_username or 'desconhecido'
            )
            return web.json_response({
                "status": "success",
                "message": f"Conta {username} excluída definitivamente.",
            })
        return web.json_response({"status": "error", "message": "Usuário não encontrado."}, status=404)

    async def api_auth_forgot_password(r):
        """Pedido de recuperacao de senha. Aprovado por um admin, nao automatico.

        Sem servidor de e-mail, o unico caminho e um admin aprovar o pedido.
        A resposta e SEMPRE a mesma, exista ou nao a conta: caso contrario
        este endpoint viraria um oraculo para enumerar usuarios do painel.
        """
        data = await r.json()
        username = data.get('username', '').strip().lower()
        generic = {
            "status": "success",
            "message": "Se o usuario existir, a solicitacao foi registrada e sera analisada por um administrador.",
        }
        if not username or not re.match(r'^[a-z0-9_]{3,32}$', username):
            return web.json_response(generic)

        db, err = get_db(bot_instance)
        if err:
            return err

        user = await db.panel_users.find_one(
            {"_id": username}, {"status": 1, "password_reset_pending": 1}
        )
        # Conta inexistente, ainda pendente de aprovacao ou bloqueada: nao ha o que
        # recuperar, e a resposta generica evita revelar o que existe.
        if not user or user.get('status', 'active') in BLOCKING_STATUSES or user.get('status') == 'pending':
            return web.json_response(generic)

        # Reenvio do mesmo pedido renova o timestamp em vez de duplicar.
        await db.panel_users.update_one(
            {"_id": username},
            {"$set": {
                "password_reset_pending": True,
                "password_reset_requested_at": datetime.datetime.now(pytz.utc),
                "password_reset_request_ip": r.remote or '',
            }}
        )
        logger.info("Pedido de reset de senha para '%s' (aguarda aprovacao de um admin).", username)
        return web.json_response(generic)

    async def api_auth_users(r):
        db, err = get_db(bot_instance)
        if err:
            return err

        # Pendentes ficam no fim; dentro de cada grupo, em ordem alfabética.
        cursor = db.panel_users.find({}).sort([("status", 1), ("_id", 1)]).limit(200)
        users = []
        async for doc in cursor:
            users.append({
                "username": doc["_id"],
                "role": doc.get("role", "viewer"),
                "status": doc.get("status", "active"),
                "discord": doc.get("discord", ""),
                "must_change_password": bool(doc.get("must_change_password", False)),
                "password_reset_pending": bool(doc.get("password_reset_pending", False)),
                "password_reset_requested_at": (
                    doc["password_reset_requested_at"].isoformat()
                    if doc.get("password_reset_requested_at") else ""
                ),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
            })
        await cursor.close()
        return web.json_response(users)

    async def api_auth_me(r):
        session = await get_session(r)
        username = session.get('username', '')
        role = session.get('role', '')
        account_status = 'active'
        if username:
            db, err = get_db(bot_instance)
            if not err:
                doc = await db.panel_users.find_one({"_id": username}, {"status": 1})
                if doc:
                    account_status = doc.get("status", "active")
        blocking_page = get_blocking_page(account_status)
        return web.json_response({
            "username": username,
            "role": role,
            "status": account_status,
            "page": f"/{blocking_page}" if blocking_page else None,
            "authenticated": bool(role or session.get('admin')),
        })

    # Registrar rotas
    admin_api_app.router.add_post("/auth/login", api_auth_login)
    admin_api_app.router.add_post("/auth/change-password", api_auth_change_password)
    admin_api_app.router.add_post("/auth/forgot-password", api_auth_forgot_password)
    admin_api_app.router.add_post("/auth/register", api_auth_register)
    admin_api_app.router.add_get("/auth/pending", api_auth_pending)
    admin_api_app.router.add_post("/auth/approve/{username:[a-z0-9_]+}", api_auth_approve)
    admin_api_app.router.add_post("/auth/reject/{username:[a-z0-9_]+}", api_auth_reject)
    admin_api_app.router.add_post("/auth/delete/{username:[a-z0-9_]+}", api_auth_delete)
    admin_api_app.router.add_get("/auth/users", api_auth_users)
    admin_api_app.router.add_get("/auth/me", api_auth_me)
    admin_api_app.router.add_post("/auth/role", api_auth_role)
    admin_api_app.router.add_get("/auth/session-info", api_auth_session_info)
