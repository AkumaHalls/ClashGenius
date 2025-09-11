# -*- coding: utf-8 -*-
import datetime
from typing import Dict, Any

def format_war_time_details(war: Any, now: datetime.datetime) -> Dict[str, str]:
    """Formata os detalhes de tempo de uma guerra para exibição no painel."""
    if war.state == 'preparation':
        time_key = "Começa em"
        time_delta = war.start_time.time - now
        time_value = war.start_time.time.strftime('%d/%m %H:%M')
    elif war.state == 'inWar':
        time_key = "Termina em"
        time_delta = war.end_time.time - now
        time_value = war.end_time.time.strftime('%d/%m %H:%M')
    else: # warEnded, notInWar, etc.
        time_key = "Terminou em"
        time_delta = now - war.end_time.time
        time_value = war.end_time.time.strftime('%d/%m %H:%M')

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
        "end_time_iso": war.end_time.time.isoformat() if hasattr(war, 'end_time') and hasattr(war.end_time, 'time') else None,
    }

