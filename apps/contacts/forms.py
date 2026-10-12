"""
Contacts app forms - with security and spam protections
"""
from django import forms # pyright: ignore[reportMissingModuleSource]
from django_recaptcha.fields import ReCaptchaField # pyright: ignore[reportMissingImports]
from django_recaptcha.widgets import ReCaptchaV2Checkbox # pyright: ignore[reportMissingImports]
from .models import ContactMessage


class ContactForm(forms.ModelForm):
    """Contact message form with spam protections."""
    
    # === CAPTCHA (Google reCAPTCHA) ===
    captcha = ReCaptchaField(
        widget=ReCaptchaV2Checkbox(
            attrs={
                'data-theme': 'light',
                'data-size': 'normal',
            }
        ),
        label='Verifica di sicurezza',
        error_messages={
            'required': 'Per favore completa la verifica CAPTCHA',
            'invalid': 'CAPTCHA non valido, riprova'
        }
    )
    
    # === HONEYPOT (hidden field to catch bots) ===
    website = forms.URLField(
        required=False,
        assume_scheme='https',
        widget=forms.TextInput(attrs={
            'style': 'position:absolute;left:-5000px;',
            'tabindex': '-1',
            'autocomplete': 'off',
            'aria-hidden': 'true',
        }),
        label='Sito web (non compilare)'
    )
    
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'dog', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Il tuo nome completo',
                'class': 'form-control',
                'required': True,
                'minlength': 3,
                'maxlength': 100,
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'la.tua@email.com',
                'class': 'form-control',
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+39 123 456 7890 (opzionale)',
                'class': 'form-control',
                'pattern': r'[\d\s\+\-\(\)]+',
            }),
            'subject': forms.Select(attrs={
                'class': 'form-control',
                'required': True,
            }),
            'dog': forms.Select(attrs={
                'class': 'form-control'
            }),
            'message': forms.Textarea(attrs={
                'placeholder': 'Scrivi qui il tuo messaggio...',
                'rows': 6,
                'class': 'form-control',
                'required': True,
                'minlength': 20, # TODO: move this value to settings / the env file? (see clean_message)
                'maxlength': 2000,
            }),
        }
        labels = {
            'name': 'Nome completo *',
            'email': 'Email *',
            'phone': 'Telefono',
            'subject': 'Oggetto *',
            'dog': 'Cane di interesse',
            'message': 'Messaggio *',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.dogs.models import Dog
        self.fields['dog'].queryset = Dog.objects.filter(
            status='available',
            is_published=True
        ).order_by('name')
        self.fields['dog'].empty_label = 'Nessun cane specifico'
    
    def clean_website(self):
        """Honeypot validation - if filled in = BOT."""
        website = self.cleaned_data.get('website')
        if website:
            raise forms.ValidationError('Spam rilevato')
        return website
    
    def clean_message(self):
        """Validate the message content."""
        message = self.cleaned_data.get('message')

        # Prevent short messages
        if len(message) < 20: # TODO: move this value to settings / the env file?
            raise forms.ValidationError('Il messaggio è troppo corto (minimo 20 caratteri)')
        
        # Prevent links (spam indicator)
        link_count = message.lower().count('http')
        if link_count >= 1:
            raise forms.ValidationError('Link nel messaggio')
        
        # Common spam words (only a few; TODO: maintain a fuller list in a dedicated file)
        spam_words = ['viagra', 'casino', 'lottery', 'prize',
                      'crypto', 'bitcoin', 'free money', 'merda', 
                      'cazzo', 'sex', 'porco dio', 'sesso', 
                      'dio cane', 'click here', 'subscribe', 'buy now']
        message_lower = message.lower()
        for word in spam_words:
            if word in message_lower:
                raise forms.ValidationError('Contenuto non consentito rilevato')
        
        return message
    
    def clean_email(self):
        """Validate the email."""
        email = self.cleaned_data.get('email')

        # Block disposable/spam email domains (only a few; TODO: maintain a fuller list in a dedicated file)
        spam_domains = [
            'tempmail.com', 'guerrillamail.com', '10minutemail.com',
            'throwaway.email', 'mailinator.com', 'trashmail.com'
        ]
        
        email_domain = email.split('@')[-1].lower()
        if email_domain in spam_domains:
            raise forms.ValidationError('Dominio email non consentito')
        
        return email
