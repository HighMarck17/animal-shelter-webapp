"""
Contacts app Views - Contact form with security and spam protections
"""
from django.views.generic import FormView, TemplateView # pyright: ignore[reportMissingModuleSource]
from django.contrib import messages # pyright: ignore[reportMissingModuleSource]
from django.urls import reverse_lazy # pyright: ignore[reportMissingModuleSource]
from django_ratelimit.decorators import ratelimit # pyright: ignore[reportMissingImports]
from django.utils.decorators import method_decorator # pyright: ignore[reportMissingModuleSource]
from django.core.cache import cache # pyright: ignore[reportMissingModuleSource]
from django.core.mail import send_mail # pyright: ignore[reportMissingModuleSource]
from django.conf import settings # pyright: ignore[reportMissingModuleSource]
from django.utils.translation import gettext as _ # pyright: ignore[reportMissingModuleSource]
import logging # pyright: ignore[reportMissingModuleSource]

from apps.core.client_ip import get_client_ip

from .forms import ContactForm

logger = logging.getLogger(__name__)

# Removed session-based rate limit for compatibility issues - only IP-based now. Maybe re-add later.
@method_decorator(ratelimit(key='ip', rate='3/h', method='POST', block=False), name='post')
# @method_decorator(ratelimit(key='session', rate='5/d', method='POST', block=False), name='post')
class ContactView(FormView):
    """
    Contact form view.
    Protections:
    - Rate limiting: 3/hour per IP
    - CAPTCHA: Google reCAPTCHA v2
    - Honeypot: hidden anti-bot field
    - Content validation: spam filters in the form
    - IP tracking: stores IP and User-Agent
    """
    template_name = 'contacts/contact.html'
    form_class = ContactForm
    success_url = reverse_lazy('contacts:success')

    def get_initial(self):
        """Pre-fill the dog field when passed as a GET parameter."""
        initial = super().get_initial()
        dog_id = self.request.GET.get('dog')
        if dog_id:
            initial['dog'] = dog_id
        return initial

    def get_context_data(self, **kwargs):
        """Add rate-limiting info to the context."""
        context = super().get_context_data(**kwargs)
        
        # Show how many messages sent today from this IP
        ip = get_client_ip(self.request)
        cache_key = f'contact_count_{ip}'
        sent_today = cache.get(cache_key, 0)
        context['messages_sent_today'] = sent_today
        context['messages_remaining'] = max(0, 3 - sent_today)
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle the rate limit before processing the form."""
        # Check if rate limit was hit
        was_limited_ip = getattr(request, 'limited', False)
        
        if was_limited_ip:
            # Log rate limit hit
            logger.warning(
                f"⚠️ RATE LIMIT - IP: {get_client_ip(request)} | "
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')[:100]} | "
                f"Endpoint: {request.path}"
            )
            
            messages.error(
                request,
                _(
                    '⚠️ Hai raggiunto il limite massimo di messaggi. '
                    'Per favore riprova tra qualche ora o contattaci telefonicamente al %(phone)s.'
                ) % {'phone': settings.CONTACT_PHONE}
            )
            return self.render_to_response(self.get_context_data())
        
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Save the message together with its security metadata."""
        # Create message but don't save yet
        message = form.save(commit=False)
        
        # Add security metadata
        message.ip_address = get_client_ip(self.request)
        message.user_agent = self.request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Score reCAPTCHA (if available)
        captcha_score = self.request.POST.get('g-recaptcha-response', '')
        message.spam_score = 1.0 if captcha_score else 0.0
        
        # Save the message
        message.save()

        # Send notification email to admin
        self.send_notification_email(message)
        
        # Increment cache counter for this IP
        ip = get_client_ip(self.request)
        cache_key = f'contact_count_{ip}'
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, 86400)  # 24 hours
        
        # Log successful message
        logger.info(
            f"✅ MESSAGE RECEIVED - Name: {message.name} | "
            f"Email: {message.email} | IP: {message.ip_address} | "
            f"Subject: {message.get_subject_display()}"
        )
        
        messages.success(
            self.request,
            _('✅ Grazie per averci contattato! Ti risponderemo entro 24-48 ore.')
        )
        
        return super().form_valid(form)
    
    def form_invalid(self, form):
        """Handle an invalid form submission."""

        # Log errors (could indicate spam)
        if 'website' in form.errors or 'message' in form.errors:
            logger.warning(
                f"⚠️ SPAM ATTEMPT - IP: {get_client_ip(self.request)} | "
                f"Errors: {form.errors}"
            )
        
        messages.error(
            self.request,
            _('❌ Errore nell\'invio del messaggio. Controlla i campi evidenziati.')
        )
        return super().form_invalid(form)
    
    def send_notification_email(self, message):
        """Send a notification email to the staff when a new message arrives."""
        try:
            recipient_email = settings.STAFF_EMAIL
            subject = f'🐾 Nuovo messaggio da {message.name} - {message.get_subject_display()}'
            
            email_body = f"""
Nuovo messaggio ricevuto dal form contatti del sito del {settings.SHELTER_NAME}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 MITTENTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nome: {message.name}
Email: {message.email}
Telefono: {message.phone or 'Non fornito'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DETTAGLI RICHIESTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Oggetto: {message.get_subject_display()}
Cane di interesse: {message.dog.name if message.dog else 'Nessuno specifico'}
Data/Ora: {message.created_at.strftime('%d/%m/%Y alle %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 MESSAGGIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{message.message}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 INFO TECNICHE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IP Address: {message.ip_address}
User Agent: {message.user_agent[:100]}
CAPTCHA Score: {message.spam_score}
ID Messaggio: #{message.id}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rispondi direttamente a: {message.email}

Per visualizzare nel pannello admin:
{self.request.build_absolute_uri(f'/{settings.ADMIN_URL}contacts/contactmessage/{message.id}/change/')}

---
Questo messaggio è stato generato automaticamente dal sito {settings.SHELTER_NAME}.
            """
            
            send_mail(
                subject=subject,
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            
            logger.info(f"📧 Notification email sent to {recipient_email} for message ID {message.id}")

        except Exception as e:
            logger.error(f"❌ Notification email failed: {str(e)}")


class ContactSuccessView(TemplateView):
    """Confirmation page shown after a message is sent."""
    template_name = 'contacts/success.html'
