#!/bin/bash
set -e

if [ ! -f .env ]; then
    echo "Errore: file .env non trovato."
    exit 1
fi

export $(grep -v '^#' .env | grep -v '^$' | xargs)

USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
EMAIL="${DJANGO_SUPERUSER_EMAIL:-${ADMIN_EMAIL:-admin@example.com}}"
PASSWORD="${DJANGO_SUPERUSER_PASSWORD}"

if [ -z "$PASSWORD" ]; then
    echo "Errore: DJANGO_SUPERUSER_PASSWORD non impostata nel .env"
    exit 1
fi

echo "→ Creazione/reset superuser: $USERNAME ($EMAIL)"

docker compose exec -T web python manage.py shell <<PYEOF
from django.contrib.auth import get_user_model
User = get_user_model()
user, created = User.objects.get_or_create(
    username='${USERNAME}',
    defaults={'email': '${EMAIL}', 'is_staff': True, 'is_superuser': True}
)
if not created:
    user.email = '${EMAIL}'
    user.is_staff = True
    user.is_superuser = True
user.set_password('${PASSWORD}')
user.save()
print(f"{'Creato' if created else 'Aggiornato'} superuser: {user.username} ({user.email})")
PYEOF
