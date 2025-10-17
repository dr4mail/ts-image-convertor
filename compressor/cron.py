"""
Cron задачи для очистки и обслуживания
"""

import os
import shutil
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from pathlib import Path
from .models import CompressionSession


def cleanup_old_sessions():
    """Удаляет файлы сессий старше 24 часов"""
    print(f"[{datetime.now()}] Starting cleanup old sessions...")
    
    temp_root = Path(settings.TEMP_ROOT)
    if not temp_root.exists():
        print("TEMP_ROOT does not exist")
        return
    
    deleted_count = 0
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    # Проходим по всем сессиям
    for session_dir in temp_root.iterdir():
        if not session_dir.is_dir():
            continue
        
        # Проверяем время модификации
        from django.utils.timezone import now as timezone_now
        import pytz
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime, tz=pytz.UTC)
        
        if mtime < cutoff_time:
            try:
                shutil.rmtree(session_dir)
                deleted_count += 1
                print(f"Deleted old session: {session_dir.name}")
            except Exception as e:
                print(f"Error deleting {session_dir.name}: {e}")
    
    print(f"Cleanup completed. Deleted {deleted_count} old sessions.")


def reset_stuck_sessions():
    """Сбрасывает зависшие сессии в статус error"""
    print(f"[{datetime.now()}] Checking for stuck sessions...")
    
    # Сессии в статусе processing старше 30 минут
    cutoff_time = timezone.now() - timedelta(minutes=30)
    
    stuck_sessions = CompressionSession.objects.filter(
        status='processing',
        created_at__lt=cutoff_time
    )
    
    count = stuck_sessions.count()
    
    if count > 0:
        stuck_sessions.update(
            status='error',
            error_message='Session timed out - possible connection loss during processing'
        )
        print(f"Reset {count} stuck sessions to error status")
    else:
        print("No stuck sessions found")