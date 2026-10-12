"""
Admin configuration for ContactMessage model - With security and spam indicators
"""
from django.contrib import admin # pyright: ignore[reportMissingModuleSource]
from django.utils.html import format_html # pyright: ignore[reportMissingModuleSource]
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'email', 'subject', 'dog',
        'is_spam_indicator', 'spam_score_display',
        'ip_address', 'is_read', 'created_at'
    ]
    list_filter = ['is_read', 'is_spam', 'subject', 'created_at']
    search_fields = ['name', 'email', 'message', 'ip_address']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at', 'ip_address', 'user_agent', 'spam_score']
    
    fieldsets = (
        ('Mittente', {
            'fields': ('name', 'email', 'phone')
        }),
        ('Messaggio', {
            'fields': ('subject', 'dog', 'message')
        }),
        ('Gestione', {
            'fields': ('is_read', 'is_spam', 'notes')
        }),
        ('Security Info', {
            'fields': ('ip_address', 'user_agent', 'spam_score', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread', 'mark_as_spam', 'mark_as_not_spam']
    
    def is_spam_indicator(self, obj):
        """Visual spam indicator."""
        if obj.is_spam:
            return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 'red', '⚠️ SPAM')
        return format_html('<span style="color: {};">{}</span>', 'green', '✓ OK')
    is_spam_indicator.short_description = 'Status'
    
    def spam_score_display(self, obj):
        """Display the spam score with a color and icon."""
        try:
            score = float(obj.spam_score)
        except (ValueError, TypeError):
            return format_html('<span style="color: {};">{}</span>', 'gray', 'N/A')
        
        if score >= 0.7:
            color = '#28a745'  # Green
            icon = '✅'
        elif score >= 0.4:
            color = '#ffc107'  # Orange
            icon = '⚠️'
        else:
            color = '#dc3545'  # Red
            icon = '❌'
        
        # Format as string with 2 decimal places before returning
        score_text = '{:.2f}'.format(score)
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            score_text
        )
    spam_score_display.short_description = 'CAPTCHA Score'

    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'{updated} messaggi segnati come letti.')
    mark_as_read.short_description = 'Segna come letti'
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'{updated} messaggi segnati come non letti.')
    mark_as_unread.short_description = 'Segna come non letti'
    
    def mark_as_spam(self, request, queryset):
        updated = queryset.update(is_spam=True)
        self.message_user(request, f'{updated} messaggi marcati come spam.')
    mark_as_spam.short_description = '⚠️ Marca come SPAM'
    
    def mark_as_not_spam(self, request, queryset):
        updated = queryset.update(is_spam=False)
        self.message_user(request, f'{updated} messaggi rimossi da spam.')
    mark_as_not_spam.short_description = '✓ NON è spam'
