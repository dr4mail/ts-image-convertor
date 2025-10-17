"""
Admin панель для управления пользователями и сессиями
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import CompressionSession, CompressionFile


class CompressionFileInline(admin.TabularInline):
    model = CompressionFile
    extra = 0
    readonly_fields = ['original_name', 'output_name', 'original_size_mb', 'compressed_size_mb', 'savings_percent', 'category']
    can_delete = False


@admin.register(CompressionSession)
class CompressionSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'archive_name', 'status', 'files_count', 'savings_percent', 'created_at', 'downloaded_at']
    list_filter = ['status', 'created_at', 'user']
    search_fields = ['session_id', 'archive_name', 'user__username']
    readonly_fields = ['session_id', 'created_at', 'completed_at', 'downloaded_at']
    inlines = [CompressionFileInline]
    
    fieldsets = (
        ('User & Session', {
            'fields': ('user', 'session_id', 'status')
        }),
        ('Archive Info', {
            'fields': ('prefix', 'archive_name')
        }),
        ('Compression Settings', {
            'fields': ('compression_quality', 'compression_max_dimension', 'compression_no_resize')
        }),
        ('Statistics', {
            'fields': ('files_count', 'files_successful', 'files_failed', 
                      'total_original_mb', 'total_compressed_mb', 'savings_percent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at', 'downloaded_at')
        }),
        ('Errors', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )


# Расширяем стандартный UserAdmin для удобства
class UserAdminExtended(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined', 'get_sessions_count']
    
    def get_sessions_count(self, obj):
        return obj.compression_sessions.count()
    get_sessions_count.short_description = 'Sessions'


# Перерегистрируем User с расширенным admin
admin.site.unregister(User)
admin.site.register(User, UserAdminExtended)