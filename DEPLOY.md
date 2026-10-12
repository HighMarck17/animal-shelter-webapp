# Deploy — Animal Shelter WebApp

## VPS prerequisites

- Ubuntu 22.04 / Debian 12 (recommended)
- RAM: 1 GB minimum, 2 GB recommended
- **Docker CE** + **Docker Compose plugin** installed
- Ports **80** and **443** open in the firewall
- DNS **A** records for `yourdomain.com` and `www.yourdomain.com` → VPS IP
  (DNS propagation can take up to 24h — verify with `dig yourdomain.com` before proceeding)

### Installing Docker (Ubuntu/Debian)
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # then log out and back in
docker compose version          # check: should show v2.x
```

---

## Initial setup

```bash
git clone <repo-url>
cd animal-shelter-webapp
cp .env.example .env
chmod +x deploy.sh setup_admin.sh
```

### Configure .env

Open `.env` and set **all** the real values:

| Variable | Production value |
|---|---|
| `DJANGO_ENVIRONMENT` | `production` |
| `SECRET_KEY` | random string (50+ chars) — `python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | `False` |
| `IS_LOCAL` | `False` |
| `ALLOWED_HOSTS` | `yourdomain.com,www.yourdomain.com` |
| `DB_HOST` | `db` |
| `REDIS_URL` | `redis://redis:6379/1` |
| `REDIS_PASSWORD` | random string — `openssl rand -hex 32` (required by the redis container) |
| `CSRF_TRUSTED_ORIGINS` | `https://yourdomain.com,https://www.yourdomain.com` |
| `SECURE_SSL_REDIRECT` | `True` |
| `CLOUDINARY_*` | Cloudinary account credentials |
| `RECAPTCHA_*` | keys from Google reCAPTCHA v2 |
| `EMAIL_*` | Brevo SMTP credentials |
| `DJANGO_SUPERUSER_PASSWORD` | secure admin password |

Also fill in your shelter's public data in `config/shelter_config.py`.

---

## First deploy

```bash
./deploy.sh first-deploy
```

The script runs, in order:

1. **Prerequisites** — checks Docker, `.env` and critical variables
2. **Domain** — reads the domain from `ALLOWED_HOSTS`, updates `nginx/conf.d/default.conf`
3. **Build** — builds the production image and starts db, redis, web
4. **SSL** — obtains the Let's Encrypt certificate via Certbot (webroot challenge)
5. **Cron** — optionally adds automatic renewal to the crontab
6. **Admin** — creates the Django superuser from the credentials in `.env`
7. **Smoke test** — verifies that homepage, dogs, contacts and static respond 200

**Estimated time:** 5–10 minutes (depends on build speed and DNS)

---

## Updates

```bash
./deploy.sh update
```

Runs: `git pull` (`main`) → pull the pinned db/redis/nginx images → rebuild the
web image (refreshing the Python base image) → restart the stack → smoke test.
DB migrations are applied automatically on container startup (`entrypoint.sh`).

---

## Useful commands

```bash
# Live logs
docker compose logs -f web
docker compose logs -f nginx

# Django shell
docker compose exec web python manage.py shell

# Reset admin password
./setup_admin.sh

# Database backup
docker compose exec db pg_dump -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d).sql

# Database restore
docker compose exec -T db psql -U $DB_USER $DB_NAME < backup.sql

# Manual SSL renewal
docker compose --profile certbot run --rm certbot renew
docker compose exec nginx nginx -s reload

# Check Django configuration
docker compose exec web python manage.py check --deploy

# Recreate web only (after editing .env)
docker compose up -d web
```

---

## Troubleshooting

**nginx won't start / certificate error**
The certificate does not exist yet. Re-run `./deploy.sh first-deploy` — the script handles the HTTP→HTTPS bootstrap.

**502 Bad Gateway**
The web container is not ready or crashed.
```bash
docker compose logs --tail=50 web
docker compose up -d web   # restart
```

**Database connection refused**
```bash
docker compose ps db       # check it is healthy
docker compose up -d db    # restart if needed
```

**collectstatic fails (PermissionError)**
Volume permissions issue. Fix:
```bash
docker compose down
docker volume rm animal-shelter-webapp_staticfiles
docker compose up -d
```

**reCAPTCHA doesn't work**
Make sure `RECAPTCHA_PUBLIC_KEY` and `RECAPTCHA_PRIVATE_KEY` in `.env` are the real domain keys (not the test keys).

**Certbot fails (Challenge failed)**
DNS is not pointing to the VPS yet. Check with:
```bash
dig +short yourdomain.com    # should return the VPS IP
curl -s ifconfig.me          # VPS IP
```
Wait for DNS propagation and try again.
