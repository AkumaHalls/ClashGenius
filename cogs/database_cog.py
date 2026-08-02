# -*- coding: utf-8 -*-
import logging
import datetime
from typing import Dict, Any
import geniuslib as coc
from discord.ext import commands
import pytz

logger = logging.getLogger("database_cog")

class DatabaseCog(commands.Cog, name="Banco de Dados"):
    """Cog para gerenciar todas as interações com o banco de dados MongoDB."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def load_player_notes_from_db(self) -> Dict[str, Dict[str, str]]:
        if self.db is None:
            logger.warning("Banco de dados não disponível, não é possível carregar as notas.")
            return {}
        try:
            notes_cursor = self.db.player_notes.find({})
            notes_from_db = {
                note_doc["_id"]: {
                    "text": note_doc.get("text", ""),
                    "priority": note_doc.get("priority", "none"),
                    "cwl_status": note_doc.get("cwl_status", "active"),
                    "admin_border": note_doc.get("admin_border", False)
                } 
                async for note_doc in notes_cursor if "_id" in note_doc
            }
            logger.info(f"Carregadas {len(notes_from_db)} notas/preferências do MongoDB.")
            return notes_from_db
        except Exception as e:
            logger.error(f"Erro ao carregar notas do MongoDB: {e}", exc_info=True)
            return {}

    async def save_player_note_to_db(self, player_tag: str, text: str, priority: str):
        if self.db is None:
            logger.error("Banco de dados não disponível, não é possível salvar a nota.")
            raise ConnectionError("Banco de dados não conectado.")
        try:
            player_tag_decoded = coc.utils.correct_tag(player_tag)
            # ATUALIZADO: Usamos $set para não sobrescrever o cwl_status ao salvar a nota.
            await self.db.player_notes.update_one(
                {"_id": player_tag_decoded},
                {"$set": {"text": text, "priority": priority}},
                upsert=True
            )
            logger.info(f"Nota salva no MongoDB para {player_tag_decoded}.")
        except Exception as e:
            logger.error(f"Erro ao salvar nota no MongoDB para {player_tag}: {e}", exc_info=True)
            raise

    async def update_player_cwl_status(self, player_tag: str, status: str):
        """Atualiza o status de participação na CWL de um jogador."""
        if self.db is None:
            raise ConnectionError("Banco de dados não conectado.")
        try:
            player_tag_decoded = coc.utils.correct_tag(player_tag)
            await self.db.player_notes.update_one(
                {"_id": player_tag_decoded},
                {"$set": {"cwl_status": status}},
                upsert=True
            )
            logger.info(f"Status CWL de {player_tag_decoded} atualizado para '{status}'.")
        except Exception as e:
            logger.error(f"Erro ao atualizar status CWL para {player_tag}: {e}", exc_info=True)
            raise

    async def update_player_admin_border(self, player_tag: str, enabled: bool):
        """Ativa/desativa a borda animada de administrador para um jogador."""
        if self.db is None:
            raise ConnectionError("Banco de dados não conectado.")
        try:
            player_tag_decoded = coc.utils.correct_tag(player_tag)
            await self.db.player_notes.update_one(
                {"_id": player_tag_decoded},
                {"$set": {"admin_border": enabled}},
                upsert=True
            )
            logger.info(f"Borda admin de {player_tag_decoded} atualizada para '{enabled}'.")
        except Exception as e:
            logger.error(f"Erro ao atualizar borda admin para {player_tag}: {e}", exc_info=True)
            raise

    async def record_member_join(self, player_tag: str):
        """Registra a entrada de um membro no clã (reinicia o tempo de casa a cada entrada)."""
        if self.db is None:
            logger.error("Banco de dados não disponível, não é possível registrar entrada.")
            raise ConnectionError("Banco de dados não conectado.")
        try:
            player_tag_decoded = coc.utils.correct_tag(player_tag)
            now = datetime.datetime.now(pytz.utc)
            existing = await self.db.clan_membership.find_one({"_id": player_tag_decoded})
            is_active = existing is not None and not existing.get("left_at") and existing.get("joined_at")
            if is_active:
                return
            await self.db.clan_membership.update_one(
                {"_id": player_tag_decoded},
                {"$set": {"joined_at": now, "left_at": None, "source": "event", "updated_at": now}},
                upsert=True
            )
            logger.info(f"Entrada registrada para {player_tag_decoded}.")
        except Exception as e:
            logger.error(f"Erro ao registrar entrada para {player_tag}: {e}", exc_info=True)

    async def record_member_leave(self, player_tag: str):
        """Registra a saída de um membro do clã."""
        if self.db is None:
            logger.error("Banco de dados não disponível, não é possível registrar saída.")
            raise ConnectionError("Banco de dados não conectado.")
        try:
            player_tag_decoded = coc.utils.correct_tag(player_tag)
            now = datetime.datetime.now(pytz.utc)
            await self.db.clan_membership.update_one(
                {"_id": player_tag_decoded, "left_at": None},
                {"$set": {"left_at": now, "updated_at": now}}
            )
            logger.info(f"Saída registrada para {player_tag_decoded}.")
        except Exception as e:
            logger.error(f"Erro ao registrar saída para {player_tag}: {e}", exc_info=True)

    async def load_membership_records(self, tags=None) -> Dict[str, Dict[str, Any]]:
        """Carrega registros de entrada/saída. Se tags for informado, filtra por elas."""
        if self.db is None:
            logger.warning("Banco de dados não disponível, não é possível carregar registros de membros.")
            return {}
        try:
            query = {"_id": {"$in": list(tags)}} if tags else {}
            cursor = self.db.clan_membership.find(query)
            records = {doc["_id"]: doc async for doc in cursor if "_id" in doc}
            return records
        except Exception as e:
            logger.error(f"Erro ao carregar registros de membros: {e}", exc_info=True)
            return {}

    def _sanitize_keys_for_mongo(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): self._sanitize_keys_for_mongo(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_keys_for_mongo(elem) for elem in obj]
        return obj

    async def save_war_to_history(self, war_data: Dict[str, Any], war_id: str):
        if self.bot.maintenance_mode or self.db is None:
            return
        try:
            war_collection = self.db.war_history
            sanitized_war_data = self._sanitize_keys_for_mongo(war_data)
            
            # CORRIGIDO: Recebe o ID único diretamente e usa como _id
            if war_id:
                sanitized_war_data['_id'] = war_id
                
                await war_collection.replace_one({'_id': sanitized_war_data['_id']}, sanitized_war_data, upsert=True)
                logger.info(f"Guerra (ID: {war_id}) salva/atualizada no histórico.")
            else:
                logger.error("Tentativa de salvar guerra no histórico sem um ID de guerra válido.")
        except Exception as e:
            logger.error(f"Erro ao salvar guerra no histórico do MongoDB: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseCog(bot))
