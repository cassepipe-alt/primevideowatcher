#!/usr/bin/env python3
"""
Prime Video US — Weekly New-Titles Watcher
Interroga l'API ufficiale di TMDB per i titoli (film + serie) disponibili su
Amazon Prime Video negli Stati Uniti, rileva le NOVITA' rispetto alla settimana
precedente e genera una pagina HTML statica (docs/index.html) pubblicabile su
GitHub Pages.

Richiede la variabile d'ambiente TMDB_API_KEY (API Read Access Token v4 o key v3).
"""

import os
import sys
import json
import time
import html
import datetime as dt
from urllib import request, parse, error

# --- Config ----------------------------------------------------------------
TMDB_KEY   = os.environ.get("TMDB_API_KEY", "").strip()
REGION     = "US"
# Provider ID di Amazon Prime Video su TMDB:
#   9   = Amazon Prime Video (abbonamento)
#   10  = Amazon Video (noleggio/acquisto) -> escluso
#   2100 = Amazon Prime Video with Ads
PROVIDERS  = "9|2100"
LANG       = "en-US"
BASE       = "https://api.themoviedb.org/3"
IMG_BASE   = "https://image.tmdb.org/t/p/w200"
STATE_FILE = "state.json"          # storico titoli già visti
OUT_HTML   = "docs/index.html"
MAX_PAGES  = 8                      # ~160 titoli per tipo: ampio margine

if not TMDB_KEY:
    print("ERRORE: TMDB_API_KEY non impostata.", file=sys.stderr)
    sys.exit(1)

# TMDB accetta sia v3 key (?api_key=) sia v4 bearer token. Rileviamo:
USE_BEARER = TMDB_KEY.startswith("eyJ") or len(TMDB_KEY) > 60


def api_get(path, params):
    params = dict(params)
    headers = {"Accept": "application/json", "User-Agent": "prime-watcher/1.0"}
    if USE_BEARER:
        headers["Authorization"] = f"Bearer {TMDB_KEY}"
    else:
        params["api_key"] = TMDB_KEY
    url = f"{BASE}{path}?{parse.urlencode(params)}"
    req = request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except error.HTTPError as e:
            if e.code == 429:           # rate limit
                time.sleep(2 + attempt * 2)
                continue
            raise
        except error.URLError:
            time.sleep(2)
    raise RuntimeError(f"Richiesta fallita: {url}")


def discover(media_type):
    """Restituisce la lista di titoli del media_type ('movie'|'tv') disponibili
    su Prime Video US, ordinati per data di aggiunta più recente."""
    results = []
    sort = "primary_release_date.desc" if media_type == "movie" else "first_air_date.desc"
    today = dt.date.today().isoformat()
    for page in range(1, MAX_PAGES + 1):
        params = {
            "language": LANG,
            "watch_region": REGION,
            "with_watch_providers": PROVIDERS,
            "with_watch_monetization_types": "flatrate|ads",
            "sort_by": sort,
            "page": page,
        }
        # Non includere uscite ancora nel futuro lontano
        if media_type == "movie":
            params["primary_release_date.lte"] = today
        else:
            params["first_air_date.lte"] = today
        data = api_get(f"/discover/{media_type}", params)
        for it in data.get("results", []):
            title = it.get("title") or it.get("name") or "—"
            date  = it.get("release_date") or it.get("first_air_date") or ""
            results.append({
                "id": f"{media_type}:{it['id']}",
                "title": title,
                "type": media_type,
                "date": date,
                "year": (date[:4] if date else ""),
                "overview": (it.get("overview") or "")[:240],
                "poster": (IMG_BASE + it["poster_path"]) if it.get("poster_path") else "",
                "rating": round(it.get("vote_average") or 0, 1),
                "tmdb": f"https://www.themoviedb.org/{media_type}/{it['id']}",
            })
        if page >= data.get("total_pages", 1):
            break
    return results


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"seen": {}, "history": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    print("Interrogo TMDB…")
    movies = discover("movie")
    tv     = discover("tv")
    catalog = movies + tv
    print(f"  film: {len(movies)}  serie: {len(tv)}")

    state = load_state()
    seen  = state.get("seen", {})
    first_run = len(seen) == 0

    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    new_items = []
    for it in catalog:
        if it["id"] not in seen:
            if not first_run:
                it["detected"] = now
                new_items.append(it)
            seen[it["id"]] = {"title": it["title"], "first_seen": now}

    # alla primissima esecuzione popoliamo lo storico senza segnare "novità",
    # così la settimana dopo il diff è pulito.
    if first_run:
        print("Prima esecuzione: storico inizializzato, nessuna novità segnalata.")

    state["seen"] = seen
    run_record = {
        "date": now,
        "new_count": len(new_items),
        "total_catalog": len(catalog),
    }
    state.setdefault("history", []).append(run_record)
    state["history"] = state["history"][-20:]   # tieni ultime 20 run
    save_state(state)

    render_html(new_items, catalog, now, first_run, state["history"])
    print(f"Fatto. Novità rilevate: {len(new_items)}")


# --- Generazione HTML -------------------------------------------------------
def card(it, highlight=False):
    poster = (f'<img src="{html.escape(it["poster"])}" alt="" loading="lazy">'
              if it["poster"] else '<div class="noposter">🎬</div>')
    badge = "SERIE" if it["type"] == "tv" else "FILM"
    rating = f'<span class="rate">★ {it["rating"]}</span>' if it["rating"] else ""
    return f'''
    <a class="card {it['type']} {'hl' if highlight else ''}" href="{html.escape(it['tmdb'])}" target="_blank" rel="noopener">
      <div class="poster">{poster}<span class="type">{badge}</span></div>
      <div class="body">
        <div class="title">{html.escape(it['title'])}</div>
        <div class="meta">{html.escape(it['year'])} {rating}</div>
        <div class="ov">{html.escape(it['overview'])}</div>
      </div>
    </a>'''


def render_html(new_items, catalog, now, first_run, history):
    new_items.sort(key=lambda x: x["date"], reverse=True)
    movies = [x for x in new_items if x["type"] == "movie"]
    tv     = [x for x in new_items if x["type"] == "tv"]
    asof   = dt.datetime.fromisoformat(now.replace("Z", "")).strftime("%d/%m/%Y %H:%M UTC")

    if first_run:
        banner = ('<div class="banner first">📦 Prima esecuzione: ho fotografato il '
                  'catalogo attuale. Le <b>novità reali</b> appariranno dalla prossima '
                  'run settimanale.</div>')
        new_section = ""
    elif new_items:
        banner = f'<div class="banner ok">✨ <b>{len(new_items)}</b> nuovi titoli rilevati dall\'ultima run.</div>'
        new_section = ""
    else:
        banner = '<div class="banner empty">Nessun nuovo titolo dall\'ultima run settimanale.</div>'
        new_section = ""

    cards_new = "".join(card(x, highlight=True) for x in new_items) or \
                '<div class="none">— Nessuna novità —</div>'

    runs = "".join(
        f'<tr><td>{dt.datetime.fromisoformat(h["date"].replace("Z","")).strftime("%d/%m %H:%M")}</td>'
        f'<td>{h["new_count"]}</td><td>{h["total_catalog"]}</td></tr>'
        for h in reversed(history)
    )

    doc = f'''<!DOCTYPE html>
<html lang="it"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prime Video US — Nuovi Titoli</title>
<style>
:root{{--bg:#0a0e17;--panel:#111826;--line:#1e2a3d;--txt:#e8eef7;--mut:#8a98ac;
--accent:#00a8e1;--movie:#ffb454;--tv:#7ee787}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--txt);line-height:1.5;
background-image:radial-gradient(circle at 20% -10%,rgba(0,168,225,.08),transparent 40%)}}
.wrap{{max-width:1180px;margin:0 auto;padding:26px 18px 80px}}
header{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;
flex-wrap:wrap;padding-bottom:18px;border-bottom:1px solid var(--line);margin-bottom:20px}}
h1{{font-size:1.5rem;letter-spacing:-.02em;display:flex;align-items:center;gap:10px}}
.logo{{width:34px;height:34px;border-radius:8px;display:inline-flex;align-items:center;
justify-content:center;font-weight:800;font-size:.85rem;color:#fff;
background:linear-gradient(135deg,var(--accent),#0066b3)}}
.sub{{color:var(--mut);font-size:.85rem;margin-top:4px}}
.asof{{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:10px 14px;font-size:.78rem;color:var(--mut);text-align:right}}
.asof b{{color:var(--txt);display:block}}
.banner{{border-radius:10px;padding:12px 16px;font-size:.85rem;margin-bottom:22px;
border:1px solid var(--line)}}
.banner.ok{{background:linear-gradient(90deg,rgba(0,168,225,.14),transparent);
border-left:3px solid var(--accent);color:#bfe9ff}}
.banner.first{{background:rgba(255,180,84,.1);border-left:3px solid var(--movie);color:#ffe1b8}}
.banner.empty{{color:var(--mut)}}
h2{{font-size:1.05rem;margin:24px 0 12px;display:flex;align-items:center;gap:10px}}
h2 .rule{{flex:1;height:1px;background:var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;
overflow:hidden;text-decoration:none;color:inherit;transition:.15s;display:flex;flex-direction:column}}
.card:hover{{border-color:var(--accent);transform:translateY(-3px)}}
.card.hl{{box-shadow:0 0 0 1px var(--accent),0 8px 28px rgba(0,168,225,.18)}}
.poster{{position:relative;aspect-ratio:2/3;background:#0d1420}}
.poster img{{width:100%;height:100%;object-fit:cover;display:block}}
.noposter{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
font-size:2rem;opacity:.3}}
.type{{position:absolute;top:8px;left:8px;font-size:.62rem;font-weight:800;
padding:3px 8px;border-radius:6px;letter-spacing:.05em;backdrop-filter:blur(4px)}}
.card.movie .type{{background:rgba(255,180,84,.85);color:#1a1206}}
.card.tv .type{{background:rgba(126,231,135,.85);color:#06210b}}
.body{{padding:11px 13px}}
.title{{font-weight:700;font-size:.9rem;line-height:1.25}}
.meta{{font-size:.74rem;color:var(--mut);margin-top:4px}}
.rate{{color:var(--movie)}}
.ov{{font-size:.74rem;color:var(--mut);margin-top:7px;display:-webkit-box;
-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.none{{color:var(--mut);padding:30px;text-align:center}}
table{{width:100%;border-collapse:collapse;font-size:.8rem;margin-top:10px;max-width:420px}}
td,th{{padding:7px 12px;border-bottom:1px solid var(--line);text-align:left;color:var(--mut)}}
th{{color:var(--txt);font-weight:600}}
footer{{margin-top:46px;padding-top:18px;border-top:1px solid var(--line);
font-size:.74rem;color:var(--mut);line-height:1.7}}
footer a{{color:var(--accent);text-decoration:none}}
</style></head><body><div class="wrap">
<header>
  <div><h1><span class="logo">PV</span> Prime Video US — Nuovi Titoli</h1>
  <div class="sub">Diff settimanale automatico via TMDB · regione US · provider Prime Video</div></div>
  <div class="asof">Ultimo aggiornamento<b>{asof}</b></div>
</header>
{banner}
<h2>✨ Novità di questa settimana <span class="rule"></span>
<span style="font-size:.8rem;color:var(--mut)">{len(movies)} film · {len(tv)} serie</span></h2>
<div class="grid">{cards_new}</div>

<h2>📊 Storico run <span class="rule"></span></h2>
<table><tr><th>Data run</th><th>Novità</th><th>Catalogo</th></tr>{runs}</table>

<footer>
Generato automaticamente da GitHub Actions. Dati: <a href="https://www.themoviedb.org/" target="_blank">The Movie Database (TMDB)</a> —
"This product uses the TMDB API but is not endorsed or certified by TMDB."<br>
Il confronto rileva i titoli comparsi nel catalogo Prime Video US dall'ultima esecuzione. Il catalogo cambia di continuo; alcune variazioni possono riflettere aggiornamenti dei metadati TMDB più che aggiunte effettive.
</footer>
</div></body></html>'''

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()
