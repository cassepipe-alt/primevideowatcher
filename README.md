# Prime Video US — Weekly New-Titles Watcher

Agente settimanale che rileva i **nuovi titoli** (film + serie) aggiunti al
catalogo **Amazon Prime Video negli Stati Uniti**, usando l'API ufficiale di
**TMDB**. Gira gratis su **GitHub Actions** (cron settimanale) e pubblica una
pagina HTML che si aggiorna da sola su **GitHub Pages**.

Nessun computer da tenere acceso. Nessun server. Zero costi.

---

## Come funziona

1. Ogni **lunedì alle 07:00 UTC** GitHub Actions esegue `watcher.py`.
2. Lo script interroga TMDB (`/discover/movie` e `/discover/tv`) filtrando per
   provider Prime Video + regione US.
3. Confronta il catalogo con quello della settimana prima (`state.json`) e
   isola **solo le vere novità**.
4. Genera `docs/index.html` e lo pubblica su GitHub Pages.

La **prima esecuzione** fotografa il catalogo senza segnalare novità (altrimenti
vedresti migliaia di "falsi nuovi"). Dalla **seconda settimana** in poi il diff
è pulito.

---

## Setup (10 minuti, una volta sola)

### 1. Ottieni una API key TMDB (gratuita)
- Registrati su https://www.themoviedb.org/signup
- Vai su **Settings → API** e richiedi una key (uso non commerciale).
- Copia l'**API Read Access Token** (quello lungo, inizia con `eyJ…`) **oppure**
  la **API Key (v3)**. Lo script accetta entrambi.

### 2. Crea il repository
- Crea un nuovo repo GitHub (può essere privato).
- Carica questi file mantenendo la struttura:
  ```
  watcher.py
  .github/workflows/watcher.yml
  README.md
  ```

### 3. Inserisci la key come Secret
- Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Nome: `TMDB_API_KEY`
- Valore: il token TMDB del punto 1.

### 4. Attiva GitHub Pages
- Repo → **Settings → Pages**
- Source: **GitHub Actions**.

### 5. Prima esecuzione manuale
- Repo → tab **Actions → Prime Video Watcher → Run workflow**.
- Finita la run, la pagina sarà su:
  `https://<tuo-utente>.github.io/<nome-repo>/`

Da qui in poi è automatico ogni lunedì. Aggiungi quel link ai preferiti.

---

## Personalizzazioni rapide

| Cosa | Dove | Come |
|------|------|------|
| Giorno/ora del check | `watcher.yml` → `cron` | Sintassi cron UTC. Es. `0 6 * * 3` = mercoledì 06:00 |
| Solo abbonamento (no ads) | `watcher.py` → `PROVIDERS` | Metti `"9"` invece di `"9\|2100"` |
| Altra regione | `watcher.py` → `REGION` | Es. `"IT"` per l'Italia |
| Lingua descrizioni | `watcher.py` → `LANG` | Es. `"it-IT"` |
| Più titoli per pagina | `watcher.py` → `MAX_PAGES` | Default 8 (~160 per tipo) |

---

## Note di affidabilità

- TMDB è alimentato dalla community: i dati di disponibilità per-provider sono
  ottimi ma non perfetti al 100%. Una variazione può occasionalmente riflettere
  un aggiornamento dei metadati più che un'aggiunta reale al catalogo.
- I diritti di attribuzione TMDB sono già inclusi nel footer della pagina
  generata, come richiesto dai loro termini d'uso.

---

## File inclusi
- `watcher.py` — script principale (diff + generazione HTML)
- `.github/workflows/watcher.yml` — cron settimanale + deploy Pages
- `README.md` — questa guida
