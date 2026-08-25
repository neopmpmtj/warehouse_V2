# Deploying CentCompras to a DigitalOcean VPS

Step-by-step guide: develop on your local machine, push to GitHub, deploy to a
DigitalOcean droplet (same setup as www.utter-it.com).

**Architecture after this refactor:**

| Environment | Settings module | How chosen |
|-------------|-----------------|------------|
| Local dev | `config.settings.dev` | default in `manage.py` / `wsgi.py` / `asgi.py` |
| Tests | `config.settings.test` | `manage.py test` auto-selects |
| Production (VPS) | `config.settings.prod` | `DJANGO_SETTINGS_MODULE` env var in systemd |

All secrets live in `.env` (gitignored). The repo ships `.env.example` as the
template. `DATABASE_URL` is the primary database setting (dev and prod);
`POSTGRES_*` vars remain a fallback for local dev.

---

## 1. One-time local machine setup (already done here)

```bash
cp .env.example .env          # then edit values
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
./scripts/seed_dev_data.sh
python manage.py runserver    # uses config.settings.dev
```

`manage.py test` automatically uses `config.settings.test` (fast hasher, quiet
logging). No `DJANGO_SETTINGS_MODULE` needed locally.

---

## 2. Create the DigitalOcean droplet

1. Create a droplet (Ubuntu 24.04 LTS, e.g. 2 GB RAM / 1 vCPU to start).
2. Add your SSH key so you can log in as `root`.
3. Set a hostname, e.g. `centcompras-vps`.
4. Add a DNS **A record** in your domain registrar: `centcompras.yourdomain.com` → droplet IP.
5. Note the IP; you'll use it below.

---

## 3. Server packages (one-time)

```bash
ssh root@<DROPLET_IP>

# system packages
apt update && apt upgrade -y
apt install -y python3-venv python3-pip postgresql postgresql-contrib nginx git

# app user (no login shell)
adduser --disabled-password --gecos "" centcompras
usermod -aG sudo centcompras   # optional; only if you want sudo from this user
```

---

## 4. PostgreSQL database + user

```bash
sudo -u postgres psql

CREATE USER centcompras WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE centcompras_db OWNER centcompras;
\q
```

Test: `PGPASSWORD='STRONG_PASSWORD_HERE' psql -h localhost -U centcompras -d centcompras_db -c "SELECT 1"`

---

## 5. Clone the app + install

```bash
sudo mkdir -p /srv/centcompras /srv/centcompras/logs
sudo chown centcompras:centcompras /srv/centcompras /srv/centcompras/logs
sudo -u centcompras git clone git@github.com:neopmpmtj/warehouse_V2.git /srv/centcompras/warehouse_V2

cd /srv/centcompras/warehouse_V2
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

---

## 6. Environment file (secrets stay off GitHub)

```bash
sudo -u centcompras cp /srv/centcompras/warehouse_V2/.env.example /srv/centcompras/warehouse_V2/.env
sudo -u centcompras nano /srv/centcompras/warehouse_V2/.env
```

Set at least:

```ini
DJANGO_SETTINGS_MODULE=config.settings.prod
DJANGO_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=centcompras.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://centcompras.yourdomain.com
DATABASE_URL=postgresql://centcompras:STRONG_PASSWORD_HERE@localhost:5432/centcompras_db
```

---

## 7. First migrate + static files

```bash
cd /srv/centcompras/warehouse_V2
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
# optional: .venv/bin/python manage.py createsuperuser
```

---

## 8. systemd service (gunicorn)

Copy the provided unit file:

```bash
sudo cp /srv/centcompras/warehouse_V2/deploy/centcompras-gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable centcompras-gunicorn
sudo systemctl start centcompras-gunicorn
sudo systemctl status centcompras-gunicorn   # active (running)
```

The unit file points `WorkingDirectory` / `EnvironmentFile` at
`/srv/centcompras/warehouse_V2` and runs gunicorn on `127.0.0.1:8000` with
`DJANGO_SETTINGS_MODULE=config.settings.prod`. Logs go to
`/srv/centcompras/logs/gunicorn-*.log`.

---

## 9. nginx reverse proxy

```bash
sudo cp /srv/centcompras/warehouse_V2/deploy/centcompras-nginx.conf /etc/nginx/sites-available/centcompras
# edit server_name in the file to your real domain
sudo ln -s /etc/nginx/sites-available/centcompras /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 10. HTTPS (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d centcompras.yourdomain.com
```

certbot edits the nginx config to serve HTTPS and auto-renews. `prod.py`
enforces `SECURE_SSL_REDIRECT`, HSTS, and secure cookies — all handled once
certbot enables TLS.

Branch offline (Phase 6) uses a Service Worker at `/service-worker.js` and
IndexedDB in the browser. **Service Workers require HTTPS in production** (localhost
/ `127.0.0.1` are exempt for development). After deploy, branch staff should open
`https://centcompras.yourdomain.com/branch/catalog/` at least once while online so
the app shell and catalogue cache download before going offline.

---

## 11. Every deploy (after pushing to main)

```bash
cd /srv/centcompras/warehouse_V2
sudo -u centcompras git pull origin main
sudo -u centcompras .venv/bin/pip install -r requirements.txt   # only if deps changed
sudo -u centcompras .venv/bin/python manage.py migrate --noinput
sudo -u centcompras .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart centcompras-gunicorn
```

---

## Google OAuth login (after deploy)

Login-only Google Sign-In (openid/email/profile — no Calendar/Drive/Gmail).

1. In Google Cloud Console create an **OAuth client ID** for this app.
   - During dev: **Desktop app** type → loopback redirect (`http://localhost:8000/accounts/google/callback/`).
   - After deploy: **Web application** type → `https://centcompras.yourdomain.com/accounts/google/callback/`.
2. Put the credentials in `.env`:

   ```ini
   AUTH_MODE=both
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_OAUTH_REDIRECT_URI=https://centcompras.yourdomain.com/accounts/google/callback/
   ```

3. Google login is **existing-only**: the Google email must already exist as a user (no auto-create). Before flipping to `google_only`, every user must have linked Google once (they sign in with Google, then confirm their password once on the link-confirm page).
4. When ready for the extra security layer, set `AUTH_MODE=google_only` in `.env` — password login is then disabled and Google is the only method.
5. Restart: `sudo systemctl restart centcompras-gunicorn`.

---

## 12. Sanity checks

```bash
curl -sI https://centcompras.yourdomain.com/            # 200, login page
curl -sI https://centcompras.yourdomain.com/static/css/settings_menu.css   # 200 (static served by nginx)
sudo journalctl -u centcompras-gunicorn -n 50           # app logs
sudo tail -f /srv/centcompras/logs/gunicorn-error.log   # gunicorn errors
```

If the app runs but shows errors, the most common causes are:
- `.env` missing/typo'd `DATABASE_URL` or `DJANGO_SECRET_KEY`
- `ALLOWED_HOSTS` not including the domain
- static files 404 → `collectstatic` not run or nginx `alias` path wrong
