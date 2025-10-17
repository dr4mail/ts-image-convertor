"""
Модели для хранения истории сжатия
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CompressionSession(models.Model):
    """История сжатия изображений"""
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
        ('downloaded', 'Downloaded'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='compression_sessions')
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Основная информация
    prefix = models.CharField(max_length=100, blank=True, default='')
    archive_name = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    
    # Настройки сжатия
    compression_quality = models.IntegerField(null=True, blank=True)
    compression_max_dimension = models.IntegerField(null=True, blank=True)
    compression_no_resize = models.BooleanField(default=False)
    
    # Статистика
    files_count = models.IntegerField(default=0)
    files_successful = models.IntegerField(default=0)
    files_failed = models.IntegerField(default=0)
    
    total_original_mb = models.FloatField(default=0)
    total_compressed_mb = models.FloatField(default=0)
    savings_percent = models.FloatField(default=0)
    
    # Временные метки
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    
    # Ошибки
    error_message = models.TextField(blank=True, default='')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Compression Session'
        verbose_name_plural = 'Compression Sessions'
    
    def __str__(self):
        return f"{self.user.username} - {self.archive_name or self.session_id[:8]} ({self.status})"
    
    def mark_as_downloaded(self):
        """Отметить как скачанное"""
        if self.status == 'completed':
            self.status = 'downloaded'
            self.downloaded_at = timezone.now()
            self.save()
    
    def get_duration(self):
        """Время обработки в секундах"""
        if self.completed_at and self.created_at:
            return (self.completed_at - self.created_at).total_seconds()
        return None


class CompressionFile(models.Model):
    """Информация об отдельных файлах в сессии"""
    
    session = models.ForeignKey(CompressionSession, on_delete=models.CASCADE, related_name='files')
    
    original_name = models.CharField(max_length=255)
    output_name = models.CharField(max_length=255)
    
    original_size_mb = models.FloatField()
    compressed_size_mb = models.FloatField()
    savings_percent = models.FloatField()
    
    category = models.CharField(max_length=50, blank=True, default='')
    
    class Meta:
        ordering = ['original_name']
    
    def __str__(self):
        return f"{self.original_name} -> {self.output_name}"