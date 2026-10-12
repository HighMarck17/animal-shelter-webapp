#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
STEP=0
DOMAIN=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

step()    { STEP=$((STEP+1)); echo -e "\n${CYAN}${BOLD}[${STEP}] $1${NC}"; }
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}" >&2; exit 1; }
confirm() { read -rp "$(echo -e "${YELLOW}${1:-Continue?} [y/N] ${NC}")" ans; [[ "${ans,,}" == "y" ]]; }

# ==============================================================
check_prerequisites() {
    step "Checking prerequisites"

    command -v docker >/dev/null 2>&1 || error "Docker not found. Install Docker before proceeding."
    docker compose version >/dev/null 2>&1 || error "Docker Compose plugin not found."
    success "Docker and Docker Compose available"

    if [ ! -f "${SCRIPT_DIR}/.env" ]; then
        cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
        warn ".env not found — created from .env.example"
        echo -e "${YELLOW}Configure .env with the real values, then run the script again.${NC}"
        exit 0
    fi
    success ".env found"

    local missing=()
    for var in SECRET_KEY DB_PASSWORD DJANGO_SUPERUSER_PASSWORD ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS; do
        local val
        val=$(grep -E "^${var}=" "${SCRIPT_DIR}/.env" | cut -d'=' -f2- | xargs 2>/dev/null || true)
        [[ -z "$val" ]] && missing+=("$var")
    done
    [[ ${#missing[@]} -gt 0 ]] && error "Missing or empty variables in .env: ${missing[*]}"
    success "Critical .env variables configured"
}

# ==============================================================
get_domain() {
    local hosts
    hosts=$(grep -E "^ALLOWED_HOSTS=" "${SCRIPT_DIR}/.env" | cut -d'=' -f2- | xargs 2>/dev/null || true)
    for h in $(echo "$hosts" | tr ',' ' '); do
        if [[ "$h" != "localhost" && "$h" != "127.0.0.1" && "$h" != "::1" && "$h" != "*" ]]; then
            echo "$h"; return
        fi
    done
}

# ==============================================================
configure_domain() {
    step "Domain configuration"

    local detected; detected=$(get_domain)
    if [[ -n "$detected" ]]; then
        echo -e "Domain detected from ALLOWED_HOSTS: ${BOLD}${detected}${NC}"
        if confirm "Use this domain for SSL and nginx?"; then
            DOMAIN="$detected"
        fi
    fi

    if [[ -z "$DOMAIN" ]]; then
        read -rp "$(echo -e "${CYAN}Production domain (e.g. yourdomain.com): ${NC}")" DOMAIN
    fi
    [[ -z "$DOMAIN" ]] && error "Domain not specified."

    local nginx_conf="${SCRIPT_DIR}/nginx/conf.d/default.conf"
    if grep -q "tuodominio\.it" "$nginx_conf"; then
        sed -i "s/tuodominio\.it/${DOMAIN}/g" "$nginx_conf"
        success "Domain updated in nginx/conf.d/default.conf"
    else
        success "Domain already configured in nginx/conf.d/default.conf"
    fi
}

# ==============================================================
build_and_deploy() {
    step "Building production image"
    docker compose build web

    step "Starting db, redis and web"
    docker compose up -d db redis web

    echo -n "Waiting for Gunicorn to start"
    local i=0
    until docker compose exec -T web python3 -c "
import urllib.request, sys
try:
    urllib.request.urlopen('http://127.0.0.1:8000/')
    sys.exit(0)
except:
    sys.exit(1)" 2>/dev/null; do
        echo -n "."; sleep 5; i=$((i+1))
        if [[ $i -ge 12 ]]; then
            echo ""
            docker compose logs --tail=30 web >&2
            error "Web not responding after 60s. Check the logs above."
        fi
    done
    echo ""; success "Gunicorn running"
}

# ==============================================================
setup_ssl() {
    step "SSL configuration (Let's Encrypt)"

    local nginx_conf="${SCRIPT_DIR}/nginx/conf.d/default.conf"
    local nginx_bak="${nginx_conf}.bak"
    local cert="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

    # Restore from a possible previous interruption
    if [[ -f "$nginx_bak" ]]; then
        warn "Found .bak from an interrupted run — restoring SSL config"
        cp "$nginx_bak" "$nginx_conf"; rm "$nginx_bak"
    fi

    if [[ -f "$cert" ]]; then
        success "Certificate already present — starting nginx with SSL"
        docker compose up -d nginx
        return 0
    fi

    warn "Certificate not found — starting temporary nginx (HTTP) for the ACME challenge"
    cp "$nginx_conf" "$nginx_bak"
    cat > "$nginx_conf" <<'HTTPEOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}
HTTPEOF

    docker compose up -d nginx
    sleep 3

    local admin_email
    admin_email=$(grep -E "^ADMIN_EMAIL=" "${SCRIPT_DIR}/.env" | cut -d'=' -f2- | xargs 2>/dev/null || echo "admin@example.com")

    echo -e "\n${CYAN}Running certbot for ${DOMAIN}...${NC}"
    docker compose --profile certbot run --rm certbot certonly \
        --webroot -w /var/www/certbot \
        --non-interactive --agree-tos \
        -m "${admin_email}" \
        -d "${DOMAIN}" -d "www.${DOMAIN}" \
    || {
        cp "$nginx_bak" "$nginx_conf"; rm "$nginx_bak"
        error "Certbot failed. Make sure the DNS for ${DOMAIN} points to this server (IP: $(curl -s ifconfig.me 2>/dev/null || echo '?'))."
    }

    cp "$nginx_bak" "$nginx_conf"; rm "$nginx_bak"
    docker compose exec nginx nginx -s reload
    success "SSL active — certificate obtained for ${DOMAIN}"
}

# ==============================================================
setup_cron() {
    step "Automatic certificate renewal"

    local cron_cmd="0 3 * * * cd ${SCRIPT_DIR} && docker compose --profile certbot run --rm certbot renew --quiet && docker compose exec nginx nginx -s reload"
    echo -e "Cron entry to add:\n  ${BOLD}${cron_cmd}${NC}\n"

    if confirm "Add it to the crontab automatically?"; then
        ( crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$cron_cmd" ) | crontab -
        success "Cron added (every day at 03:00)"
    else
        warn "Add the cron command above manually."
    fi
}

# ==============================================================
setup_admin() {
    step "Admin superuser configuration"
    bash "${SCRIPT_DIR}/setup_admin.sh"
    success "Admin configured"
}

# ==============================================================
smoke_test() {
    step "Smoke test"

    local base="https://${DOMAIN}"
    local admin_url; admin_url=$(grep -E "^ADMIN_URL=" "${SCRIPT_DIR}/.env" | cut -d'=' -f2- | xargs 2>/dev/null || echo "admin/")
    admin_url="${admin_url:-admin/}"
    local failed=0

    for path in "/" "/dogs/" "/contacts/" "/static/css/variables.css"; do
        if curl -sf --max-time 10 "${base}${path}" >/dev/null 2>&1; then
            success "${path} → 200"
        else
            warn "${path} → unreachable"
            failed=$((failed+1))
        fi
    done

    echo ""
    if [[ $failed -eq 0 ]]; then
        echo -e "${GREEN}${BOLD}✓ Deploy completed successfully!${NC}"
    else
        warn "${failed} endpoints unreachable. Check: docker compose logs web nginx"
    fi
    echo -e "  Site:  ${BOLD}${base}/${NC}"
    echo -e "  Admin: ${BOLD}${base}/${admin_url}${NC}"
}

# ==============================================================
update() {
    check_prerequisites
    DOMAIN=$(get_domain || true)

    step "Pulling latest code (main)"
    git pull --ff-only origin main

    # Pull pinned service images and refresh the Python base image, so tag
    # bumps in docker-compose.yml / Dockerfile and rebuilt patch images apply
    step "Pull images, rebuild and restart"
    docker compose pull db redis nginx
    docker compose build --pull web
    docker compose up -d db redis web nginx

    echo -n "Waiting for web to restart"
    local i=0
    until docker compose exec -T web python3 -c "
import urllib.request, sys
try:
    urllib.request.urlopen('http://127.0.0.1:8000/')
    sys.exit(0)
except:
    sys.exit(1)" 2>/dev/null; do
        echo -n "."; sleep 5; i=$((i+1))
        if [[ $i -ge 12 ]]; then
            echo ""
            docker compose logs --tail=20 web >&2
            error "Web not responding after 60s."
        fi
    done
    echo ""

    if [[ -n "$DOMAIN" ]]; then
        smoke_test
    else
        success "Web updated and running"
    fi
}

# ==============================================================
usage() {
    echo -e "${BOLD}deploy.sh${NC} — Guided deploy script for the Animal Shelter WebApp\n"
    echo "  ./deploy.sh first-deploy   Full first-time setup on the VPS (build, SSL, admin, cron)"
    echo "  ./deploy.sh update         Pull + rebuild + restart"
    echo "  ./deploy.sh --help         Show this message"
    echo -e "\nFull documentation: ${BOLD}DEPLOY.md${NC}"
}

# ==============================================================
cd "${SCRIPT_DIR}"
case "${1:-}" in
    first-deploy)
        echo -e "\n${BOLD}=== FIRST DEPLOY — Animal Shelter WebApp ===${NC}"
        check_prerequisites
        configure_domain
        build_and_deploy
        setup_ssl
        setup_cron
        setup_admin
        smoke_test
        ;;
    update)
        echo -e "\n${BOLD}=== UPDATE — Animal Shelter WebApp ===${NC}"
        update
        ;;
    --help|-h|help)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
