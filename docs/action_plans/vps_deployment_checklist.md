# Rex VPS Deployment Checklist

## Goal
Deploy Rex to the Contabo VPS so the iPhone app can use a stable public HTTPS backend for real street/pocket voice testing.

## Server Target
- Provider: Contabo
- VPS name: `rex`
- Public IPv4: `209.126.87.50`
- Region: US-central
- Resources: 48 GB RAM, 500 GB SSD
- Rex backend port: `127.0.0.1:8010`
- Public URL: `https://api.rexpilot.com`

## Architecture

```text
Internet / iPhone app
  -> HTTPS domain
  -> Caddy or Nginx on VPS ports 80/443
  -> Rex FastAPI on 127.0.0.1:8010
  -> Grok API + Deepgram + Google TTS + Supabase
```

EchoDesk can run on the same VPS behind a separate domain/subdomain and a different localhost port.

## Phase 1 - Prepare VPS

1. [ ] **Create deployment user and lock down basics**
   - What to do: SSH into the VPS as `root`, create a non-root user such as `rex`, add SSH key access, and disable password login if safe.
   - Commands:
     ```sh
     adduser rex
     usermod -aG sudo rex
     ```
   - Success criteria: You can SSH as the non-root deploy user.

2. [x] **Configure firewall**
   - What to do: Allow SSH, HTTP, and HTTPS only.
   - Commands:
     ```sh
     ufw allow OpenSSH
     ufw allow 80/tcp
     ufw allow 443/tcp
     ufw enable
     ufw status
     ```
   - Success criteria: Ports `22`, `80`, and `443` are allowed; FastAPI port `8000` is not publicly exposed.

3. [x] **Install system dependencies**
   - What to do: Install Python, venv, git, curl, and reverse proxy tooling.
   - Commands:
     ```sh
     sudo apt update
     sudo apt install -y python3 python3-venv python3-pip git curl
     ```
   - Success criteria: `python3`, `git`, and `curl` work on the VPS.

## Phase 2 - Upload Rex

4. [x] **Clone or pull the Rex repo**
   - What to do: Put Rex under `/opt/rex` or `/home/rex/rex`.
   - Commands:
     ```sh
     sudo mkdir -p /opt/rex
     sudo chown rex:rex /opt/rex
     cd /opt/rex
     git clone <REPO_URL> .
     ```
   - Success criteria: The VPS has the current Rex codebase.

5. [x] **Create Python virtualenv and install backend dependencies**
   - What to do: Install backend dependencies in an isolated venv.
   - Commands:
     ```sh
     cd /opt/rex
     python3 -m venv .venv
     . .venv/bin/activate
     pip install --upgrade pip
     pip install -r backend/requirements.txt
     ```
   - Success criteria: Dependencies install without errors.

6. [x] **Create production `.env`**
   - What to do: Create `/opt/rex/.env` with Grok, Supabase, Deepgram, and Google TTS values.
   - Required values:
     ```env
     APP_ENVIRONMENT=production
     CORS_ALLOWED_ORIGINS=
     GROK_API_KEY=
     GROK_MODEL=
     GROK_BASE_URL=https://api.x.ai/v1
     SUPABASE_URL=
     SUPABASE_SERVICE_ROLE_KEY=
     SUPABASE_ANON_KEY=
     DEEPGRAM_API_KEY=
     GOOGLE_TTS_PROJECT_ID=
     GOOGLE_APPLICATION_CREDENTIALS=
     ```
   - Success criteria: `.env` exists on the VPS and is not committed to git.

## Phase 3 - Configure Supabase

7. [ ] **Run Rex schema in Supabase**
   - What to do: Run `backend/supabase_schema.sql` in the Supabase SQL editor.
   - Tables required:
     - `conversations`
     - `messages`
     - `long_term_memory`
     - `voice_turns`
   - Success criteria: All required tables exist in Supabase.

8. [x] **Confirm backend Supabase credentials**
   - What to do: Make sure the VPS `.env` uses `SUPABASE_SERVICE_ROLE_KEY`, not only anon key.
   - Success criteria: Backend can read/write Supabase through service-role credentials.

## Phase 4 - Start Backend Manually

9. [x] **Run FastAPI manually on localhost**
   - What to do: Start Uvicorn bound to `127.0.0.1`.
   - Commands:
     ```sh
     cd /opt/rex
     . .venv/bin/activate
     set -a
     . ./.env
     set +a
     PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8010
     ```
   - Success criteria: Backend starts without crashing.

10. [x] **Verify readiness locally**
    - What to do: From another SSH session, call `/ready`.
    - Command:
      ```sh
      curl http://127.0.0.1:8010/ready
      ```
    - Success criteria: Response status is `ready`, with Grok, Supabase, Deepgram, and Google TTS configured.

## Phase 5 - Add systemd Service

11. [x] **Create `rex-backend.service`**
    - What to do: Create `/etc/systemd/system/rex-backend.service`.
    - Unit:
      ```ini
      [Unit]
      Description=Rex FastAPI Backend
      After=network.target

      [Service]
      Type=simple
      WorkingDirectory=/opt/rex
      EnvironmentFile=/opt/rex/.env
      Environment=PYTHONPATH=/opt/rex/backend
      ExecStart=/opt/rex/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
      Restart=always
      RestartSec=5

      [Install]
      WantedBy=multi-user.target
      ```
    - Success criteria: Unit file exists and points to the right repo/venv paths.

12. [x] **Enable and start service**
    - Commands:
      ```sh
      sudo systemctl daemon-reload
      sudo systemctl enable rex-backend
      sudo systemctl start rex-backend
      sudo systemctl status rex-backend
      ```
    - Success criteria: `rex-backend` is active and restarts automatically on reboot.

13. [x] **Check backend logs**
    - Command:
      ```sh
      sudo journalctl -u rex-backend -f
      ```
    - Success criteria: Logs show startup without repeated crashes.

## Phase 6 - Add HTTPS Reverse Proxy

14. [x] **Point DNS to VPS**
    - What to do: Create an A record for the Rex API domain.
    - Example:
      ```text
      api.rexpilot.com -> 209.126.87.50
      ```
    - Success criteria: `dig api.<your-domain>` resolves to `209.126.87.50`.

15. [x] **Install and configure Caddy or Nginx**
    - Recommended for simplicity: Caddy.
    - Example Caddyfile:
      ```caddy
      api.rexpilot.com -> 127.0.0.1:8010
      ```
    - Success criteria: HTTPS certificate is issued and proxy forwards to FastAPI.

16. [x] **Verify public HTTPS readiness**
    - Command:
      ```sh
      curl https://api.rexpilot.com/ready
      ```
    - Success criteria: Public `/ready` returns `ready`.

## Phase 7 - Point Flutter App to VPS

17. [x] **Run Flutter against VPS backend**
    - Command:
      ```sh
      flutter run \
        --dart-define=REX_BACKEND_URL=https://api.rexpilot.com \
        --dart-define=REX_CLOUD_VOICE_ENABLED=true
      ```
    - Success criteria: The app sends text chat to the VPS backend successfully.

18. [x] **Test cloud voice path**
    - What to test: Record audio, Deepgram transcript, Grok response, Google TTS playback.
    - Success criteria: One full voice turn works from the mobile app through the VPS.

## Phase 8 - Real Phone Street Test

19. [ ] **Run iPhone pocket/street test**
    - What to test: Wi-Fi and cellular, screen lock, app switch, AirPods/Bluetooth, noisy street, long monologue, interruption, second turn.
    - Success criteria: Rex works reliably enough for walking use.

20. [ ] **Document issues and fix follow-ups**
    - Files to update:
      - `docs/background_voice_constraints.md`
      - `docs/action_plans/voice_pipeline_checklist.md`
      - this checklist
    - Success criteria: Known limitations are written down, and critical failures become actionable fixes.

## Completion Criteria

- [ ] VPS is secured with firewall and non-root deploy user.
- [x] Rex backend runs under `systemd`.
- [x] Public HTTPS `/ready` returns `ready`.
- [x] Flutter app uses the VPS backend URL.
- [x] Text chat works from the macOS app through the VPS.
- [x] Cloud voice works from phone.
- [ ] Physical street/pocket test result is documented.

## Revision History

- 2026-05-16 - Initial VPS deployment checklist created for Contabo Rex server.
