# Deploying CentCompras to a Contabo VPS (staging, IP-only, no TLS)

Step-by-step runbook for the **staging phase**: plain `http://<server-ip>`, no
domain, no HTTPS, no Google OAuth — password login only, dummy data via the
seed command. This is what is running on `http://169.58.240.120` (2026-08-26).

> **When the customer approves** → migrate to the production path in
> [`DEPLOYMENT.md`](DEPLOYMENT.md) (DigitalOcean + backups + external DB +
> domain + HTTPS + Google OAuth).

**Credentials for the live staging box are NOT in this file** — they live in
the operator's private notes (see `memory/references/contabo-staging-deployment.md`
on the dev machine). Repo is public; keep it that way.

---

## 1. Order the VPS (Contabo)

- **Plan:** Cloud VPS 10 (4 vCPU / 8 GB RAM / 100 GB SSD) — more than enough for staging. VPS 20 if you want headroom.
- **OS:** Ubuntu 24.04 LTS (PostgreSQL 16 ships with it).
- **Location:** nearest EU DC to Portugal (Germany / London).
- After provisioning: Contabo emails login data; the IP + root password are in
  the Customer Control Panel (my.contabo.com) → VPS control.

## 2. First SSH + baseline

```bash
ssh root@<SERVER_IP>
# install your SSH key, then:
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
timedatectl set-timezone Europe/Lisbon
hostnamectl set-hostname centcompras-stage
```

## 3. Packages

```bash
apt-get install -y python3-venv python3-pip python3-dev \
  postgresql postgresql-contrib nginx git build-essential libpq-dev \
  fail2ban ufw
```

## 4. App user + PostgreSQL

```bash
mkdir -p /srv/centcompras/logs
useradd --system --home /srv/centcompras --shell /usr/sbin/nologin centcompras
chown -R centcompras:centcompras /srv/centcompras

sudo -u postgres psql <<'SQL'
CREATE USER centcompras WITH PASSWORD 'STRONG_PASSWORD';
CREATE DATABASE centcompras_db OWNER centcompras;
ALTER ROLE centcompras SET client_encoding TO 'utf8';
ALTER ROLE centcompras SET default_transaction_isolation TO 'read committed';
ALTER ROLE centcompras SET timezone TO 'UTC';
SQL
```

## 5. Clone + venv + deps

```bash
cd /srv/centcompras
git clone https://github.com/neopmpmtj/warehouse_V2.git
cd warehouse_V2
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
# VERIFY the install (do not trust pip's exit code through a pipe):
.venv/bin/python -c "import django, gunicorn, whitenoise, psycopg; print('imports OK')"
chown -R centcompras:centcompras /srv/centcompras   # AFTER clone (root-owned clone → logs/ PermissionError)
```

> ⚠️ **`requirements.txt` must contain `whitenoise`** — `base.py` loads
> `WhiteNoiseMiddleware` and gunicorn will crash at startup without it. If a
> docs/PDF PR ever rewrites requirements, re-check this line.

## 6. `.env` (staging, HTTP-only)

```bash
cat > .env <<'EOF'
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<generated: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=<SERVER_IP>,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://<SERVER_IP>
DATABASE_URL=postgresql://centcompras:STRONG_PASSWORD@localhost:5432/centcompras_db
SECURE_SSL_REDIRECT=False
SECURE_COOKIES=False
AUTH_MODE=both
EOF
chown centcompras:centcompras .env && chmod 600 .env
```

> **`SECURE_COOKIES=False` is required over plain HTTP** — with secure cookies
> the browser drops the session and login silently breaks. When HTTPS arrives,
> set `SECURE_SSL_REDIRECT=True` and remove/negate `SECURE_COOKIES`.
> `127.0.0.1,localhost` in ALLOWED_HOSTS is needed for on-box health checks.
> Leave `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` unset → password login only.

## 7. Migrate + static + seed + admin

```bash
cd /srv/centcompras/warehouse_V2
sudo -u centcompras .venv/bin/python manage.py migrate --noinput
sudo -u centcompras .venv/bin/python manage.py collectstatic --noinput
sudo -u centcompras .venv/bin/python manage.py seed_dev_data     # dummy users + ~50 items + branches
DJANGO_SUPERUSER_PASSWORD='<admin pw>' sudo -u centcompras .venv/bin/python manage.py createsuperuser --noinput --email admin@centcompras.dev
```

## 8. systemd + nginx + firewall

```bash
cp deploy/centcompras-gunicorn.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now centcompras-gunicorn

cp deploy/centcompras-nginx.conf /etc/nginx/sites-available/centcompras
sed -i 's/centcompras.example.com/<SERVER_IP>/' /etc/nginx/sites-available/centcompras
ln -sf /etc/nginx/sites-available/centcompras /etc/nginx/sites-enabled/centcompras
nginx -t && systemctl reload nginx

ufw allow OpenSSH && ufw allow 80/tcp && ufw --force enable
systemctl enable --now fail2ban
```

## 9. Verify (in order)

```bash
curl -sS http://127.0.0.1:8000/healthz          # {"status":"ok"}
curl -sS http://<SERVER_IP>/healthz             # via nginx
curl -sSI http://<SERVER_IP>/accounts/login/    # 200
# end-to-end login (field name is "username", email as value):
#   GET login page → extract csrfmiddlewaretoken → POST username=<email>&password=…
#   expect 302 → authed pages 200
```

## 10. Redeploy after pushing to main

```bash
cd /srv/centcompras/warehouse_V2
sudo -u centcompras git pull origin main
sudo -u centcompras .venv/bin/pip install -r requirements.txt   # only if deps changed
sudo -u centcompras .venv/bin/python manage.py migrate --noinput
sudo -u centcompras .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart centcompras-gunicorn
```

## Known staging limitations (by design)

- Browser shows "Not secure" — no TLS yet.
- **Branch offline / PWA (Phase 6) won't work over plain HTTP** — browsers
  require HTTPS for Service Workers. Everything online is fully functional.
- Google OAuth off — password login with dummy users only.

## Path to production (when customer approves)

See [`DEPLOYMENT.md`](DEPLOYMENT.md): DigitalOcean droplet, snapshots/backups,
external managed PostgreSQL, DNS A record, certbot HTTPS, Google OAuth Web
client (`AUTH_MODE=google_only` when ready). Flip `SECURE_SSL_REDIRECT=True`
(and let `SECURE_COOKIES` follow it) once 443 is live.
