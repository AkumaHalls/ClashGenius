# -*- coding: utf-8 -*-
import datetime
import pytz
import geniuslib as coc
from typing import Dict, Any

def format_war_time_details(war: Any, now: datetime.datetime) -> Dict[str, str]:
    """Formata os detalhes de tempo de uma guerra para exibição no painel."""
    
    # Garante que os tempos da API (que são 'naive' em UTC) se tornem 'aware'
    start_time_utc = war.start_time.time.replace(tzinfo=pytz.utc) if hasattr(war.start_time, 'time') else None
    end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc) if hasattr(war.end_time, 'time') else None

    if war.state == coc.WarState.preparation and start_time_utc:
        time_key = "Começa em"
        time_delta = start_time_utc - now
        time_value = start_time_utc.astimezone(now.tzinfo).strftime('%d/%m %H:%M')
    elif war.state == coc.WarState.in_war and end_time_utc:
        time_key = "Termina em"
        time_delta = end_time_utc - now
        time_value = end_time_utc.astimezone(now.tzinfo).strftime('%d/%m %H:%M')
    elif end_time_utc: # warEnded, notInWar, etc.
        time_key = "Terminou em"
        time_delta = now - end_time_utc
        time_value = end_time_utc.astimezone(now.tzinfo).strftime('%d/%m %H:%M')
    else: # Fallback
        return {
            "time_key": "Tempo", "time_value": "-", "time_remaining": "-", "end_time_iso": None
        }

    total_seconds = time_delta.total_seconds()
    
    if total_seconds < 0:
        time_remaining = "Finalizada"
    else:
        days = int(total_seconds // 86400)
        hours = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        parts = []
        if days > 0: parts.append(f"{days}d")
        if hours > 0: parts.append(f"{hours}h")
        if minutes > 0: parts.append(f"{minutes}m")
        time_remaining = " ".join(parts) if parts else "Menos de um minuto"

    return {
        "time_key": time_key,
        "time_value": time_value,
        "time_remaining": time_remaining,
        "end_time_iso": end_time_utc.isoformat() if end_time_utc else None
    }

