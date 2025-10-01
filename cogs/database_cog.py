# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any
import coc
from discord.ext import commands

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
                    "cwl_status": note_doc.get("cwl_status", "active") # Adiciona o status da CWL
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

    def _sanitize_keys_for_mongo(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): self._sanitize_keys_for_mongo(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize_keys_for_mongo(elem) for elem in obj]
        return obj

    async def save_war_to_history(self, war_data: Dict[str, Any]):
        if self.bot.maintenance_mode or self.db is None:
            return
        try:
            war_collection = self.db.war_history
            sanitized_war_data = self._sanitize_keys_for_mongo(war_data)
            if 'war_data' in sanitized_war_data and 'end_time_iso' in sanitized_war_data['war_data'] and sanitized_war_data['war_data']['end_time_iso']:
                sanitized_war_data['_id'] = sanitized_war_data['war_data']['end_time_iso']
                
                await war_collection.replace_one({'_id': sanitized_war_data['_id']}, sanitized_war_data, upsert=True)
                logger.info(f"Guerra finalizada em {sanitized_war_data['_id']} salva no histórico.")

                count = await war_collection.count_documents({})
                if count > 50: 
                    oldest_wars_cursor = war_collection.find().sort("war_data.end_time_iso", 1).limit(count - 50)
                    async for old_war in oldest_wars_cursor:
                        await war_collection.delete_one({"_id": old_war["_id"]})
                        logger.info(f"Guerra mais antiga ({old_war['_id']}) removida do histórico para manter o limite de 50.")
            else:
                logger.error("Tentativa de salvar guerra no histórico sem 'end_time_iso'. Dados incompletos.")
        except Exception as e:
            logger.error(f"Erro ao salvar guerra no histórico do MongoDB: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseCog(bot))

