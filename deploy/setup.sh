#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# GeniOS — One-Click DigitalOcean Droplet Setup
# Run: bash setup.sh
# ═══════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════"
echo "  GeniOS Full Stack Setup"
echo "  Backend + Frontend + Redis + Celery"
echo "═══════════════════════════════════════════"

# ── 1. System packages ──────────────────────────────────────────
echo ""
echo "[1/8] Installing system packages..."
sudo apt update -y
sudo apt install -y python3 python3-pip python3-venv redis-server nginx supervisor certbot python3-certbot-nginx git curl

# ── 2. Node.js 20 ───────────────────────────────────────────────
echo ""
echo "[2/8] Installing Node.js 20..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi
echo "Node: $(node -v), npm: $(npm -v)"

# ── 3. Clone repo ──────────────────────────────────────────────
echo ""
echo "[3/8] Setting up project..."
PROJECT_DIR="/home/genios"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Enter your GitHub repo URL (e.g., https://github.com/user/genios.git):"
    read -r REPO_URL
    sudo git clone "$REPO_URL" "$PROJECT_DIR"
    sudo chown -R $USER:$USER "$PROJECT_DIR"
else
    echo "Project already exists at $PROJECT_DIR, pulling latest..."
    cd "$PROJECT_DIR" && git pull
fi

# ── 4. Backend setup ───────────────────────────────────────────
echo ""
echo "[4/8] Setting up backend..."
cd "$PROJECT_DIR/genios-brain"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Check .env exists
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found in genios-brain/"
    echo "Create it now? (y/n)"
    read -r CREATE_ENV
    if [ "$CREATE_ENV" = "y" ]; then
        nano .env
    else
        echo "⚠️  Remember to create .env before starting services!"
    fi
fi

# ── 5. Frontend setup ──────────────────────────────────────────
echo ""
echo "[5/8] Setting up frontend..."
cd "$PROJECT_DIR/genios-dashboard"
npm install
npm run build

# ── 6. Redis config ────────────────────────────────────────────
echo ""
echo "[6/8] Configuring Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Set Redis to use limited memory (local cache only)
sudo bash -c 'cat >> /etc/redis/redis.conf << EOF

# GeniOS config
maxmemory 128mb
maxmemory-policy allkeys-lru
EOF'
sudo systemctl restart redis-server

# ── 7. Supervisor config ───────────────────────────────────────
echo ""
echo "[7/8] Configuring process manager..."
sudo mkdir -p /var/log/genios

sudo bash -c "cat > /etc/supervisor/conf.d/genios.conf << 'EOF'
[program:api]
command=/home/genios/genios-brain/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
directory=/home/genios/genios-brain
environment=PATH=\"/home/genios/genios-brain/venv/bin\"
autostart=true
autorestart=true
stderr_logfile=/var/log/genios/api.err.log
stdout_logfile=/var/log/genios/api.out.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB

[program:celery-worker]
# NOTE: must include the brain_router queue or task_brain_router (dispatched
# every minute by beat) piles up unconsumed in Redis. The --without-* flags
# disable Celery's gossip/mingle/heartbeat chatter (pointless for a single
# worker) which otherwise hammers Redis and burns the Upstash request quota.
command=/home/genios/genios-brain/venv/bin/celery -A app.celery_app worker --loglevel=info -Q high_priority,low_priority,brain_router --concurrency=2 --without-gossip --without-mingle --without-heartbeat
directory=/home/genios/genios-brain
environment=PATH=\"/home/genios/genios-brain/venv/bin\"
autostart=true
autorestart=true
stderr_logfile=/var/log/genios/celery.err.log
stdout_logfile=/var/log/genios/celery.out.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB

[program:celery-beat]
command=/home/genios/genios-brain/venv/bin/celery -A app.celery_app beat --loglevel=info
directory=/home/genios/genios-brain
environment=PATH=\"/home/genios/genios-brain/venv/bin\"
autostart=true
autorestart=true
stderr_logfile=/var/log/genios/beat.err.log
stdout_logfile=/var/log/genios/beat.out.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB

[program:frontend]
command=/usr/bin/npx next start -p 3000
directory=/home/genios/genios-dashboard
environment=NODE_ENV="production"
autostart=true
autorestart=true
stderr_logfile=/var/log/genios/frontend.err.log
stdout_logfile=/var/log/genios/frontend.out.log
stdout_logfile_maxbytes=10MB
stderr_logfile_maxbytes=10MB

[group:genios]
programs=api,celery-worker,celery-beat,frontend
EOF"

sudo supervisorctl reread
sudo supervisorctl update

# ── 8. Nginx config ────────────────────────────────────────────
echo ""
echo "[8/8] Configuring Nginx..."

echo "Enter your domain (e.g., genios.ai) or press Enter to skip:"
read -r DOMAIN

if [ -n "$DOMAIN" ]; then
    sudo bash -c "cat > /etc/nginx/sites-available/genios << 'NGINX_EOF'
# Frontend
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}

# Backend API
server {
    listen 80;
    server_name api.$DOMAIN;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
NGINX_EOF"

    sudo ln -sf /etc/nginx/sites-available/genios /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t && sudo systemctl reload nginx

    echo ""
    echo "Add these DNS records (A records) pointing to this server's IP:"
    echo "  $DOMAIN       → $(curl -s ifconfig.me)"
    echo "  api.$DOMAIN   → $(curl -s ifconfig.me)"
    echo ""
    echo "After DNS propagates, run this for free SSL:"
    echo "  sudo certbot --nginx -d $DOMAIN -d api.$DOMAIN"
else
    echo "Skipping Nginx domain setup. Access via IP:"
    echo "  Frontend: http://$(curl -s ifconfig.me):3000"
    echo "  API:      http://$(curl -s ifconfig.me):8000"
fi

# ── Start everything ───────────────────────────────────────────
echo ""
echo "Starting all services..."
sudo supervisorctl start genios:*

# ── Done ───────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  ✓ GeniOS Setup Complete!"
echo "═══════════════════════════════════════════"
echo ""
echo "Services:"
echo "  API:      http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Redis:    localhost:6379"
echo ""
echo "Commands:"
echo "  Check status:    sudo supervisorctl status"
echo "  View API logs:   tail -f /var/log/genios/api.out.log"
echo "  View errors:     tail -f /var/log/genios/api.err.log"
echo "  Restart all:     sudo supervisorctl restart genios:*"
echo "  Deploy update:   bash /home/genios/deploy/update.sh"
echo ""
