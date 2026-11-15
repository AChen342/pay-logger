# Pay Logger -- web app

The same Pay Logger, served over HTTP so it opens on your phone. It reuses
the desktop app's data and forecast code untouched (`logger`, `stats`,
`goals`, `formatting`, `calsync`); only the interface is new.

```
web/
    server.py              FastAPI: one cached Logger + the calendar, turned
                           into JSON endpoints. Background-refreshes every
                           10 min and after each write.
    static/                The phone UI (index.html, style.css, app.js).
                           Mobile-first, widens to two columns on a tablet
                           or desktop. Charts drawn in the browser as SVG.
    Containerfile          Slim image (no Qt/matplotlib).
    requirements-web.txt   Just the web deps.
    paylogger.container    Quadlet systemd unit for rootless Podman.
```

Nothing here computes anything: the numbers come from the top-level
`stats.py` / `logger.py`, the same as the desktop. So the web app and the
desktop app can run against the same Google Sheet at once.

## Run it on ac-server (rootless Podman + Quadlet)

From a clone of this repo on the server:

```bash
# 1. Put the service-account key and a data dir in place
mkdir -p ~/paylogger/data
cp /path/to/credentials.json ~/paylogger/credentials.json

# 2. Build the image (from the repo root, so the Containerfile sees the
#    top-level modules)
podman build -t paylogger -f web/Containerfile .

# 3. Install the Quadlet unit and start it (same pattern as the music stack)
cp web/paylogger.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start paylogger
systemctl --user status paylogger
```

`loginctl enable-linger achen` is already on from the music stack, so the
container survives logout and starts at boot.

## Reach it from your phone

- **On Wi-Fi at home:** `http://ac-server:8690` (or `http://192.168.1.253:8690`).
- **Anywhere, over Tailscale:** install Tailscale on the iPhone, then
  `http://<ac-server's Tailscale name>:8690`. This keeps your earnings off
  the public internet -- the app has no login of its own, so Tailscale is
  what gates access.

On the iPhone, open it in Safari and "Add to Home Screen" for an app-like
icon (the manifest/theme-color are set for that).

## Updating

From the laptop, double-click **`Deploy to Server.bat`** (repo root). It
commits + pushes, then SSHes to ac-server to pull, rebuild and restart.
Set `REPO` at the top of it to where the repo lives on the server.

Or by hand on the server:

```bash
git pull
podman build -t paylogger -f web/Containerfile .
systemctl --user restart paylogger
```

## Notes

- **Don't expose port 8690 to the internet** (no port-forward on the Fios
  gateway). There's no authentication; Tailscale is the access control.
- `credentials.json` is mounted read-only and never copied into the image.
- `goals.json` (your goals and usual days) lives in `~/paylogger/data/` so
  it survives rebuilds. It's separate from the desktop's `goals.json`, so
  set your goals once on each if you use both.
- The sheet is re-read every 10 minutes, so a shift you log on the desktop
  shows on your phone within 10 minutes (or tap the ↻ button).
