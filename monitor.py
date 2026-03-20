"""
Biogenie — Moniteur GTC v4.2
Colonnes réelles GTC confirmées. Merge detailsFiches + point + surface (aire contaminée).
"""

import requests, json, os, logging, smtplib, zipfile, io, time, schedule
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("biogenie.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

GPKG_URL        = "https://stqc380donopppdtce01.blob.core.windows.net/donnees-ouvertes/Repertoire_terrains_contamines/RepertoireTerrainsContamines.gpkg.zip"
GPKG_DIR        = Path("/tmp/biogenie_gtc")
SNAPSHOT_FILE   = Path("gtc_snapshot.json")
DATA_FILE       = Path("gtc_data.json")
INTERVAL_MIN    = 15
GPKG_MAX_AGE_H  = 24  # re-télécharge le GPKG si plus vieux que 24h

SMTP_USER      = os.environ.get("SMTP_USER", "")
SMTP_PASS      = os.environ.get("SMTP_PASS", "")
ALERT_EMAIL    = os.environ.get("ALERT_EMAIL", "")
SUPABASE_URL   = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY   = os.environ.get("SUPABASE_KEY", "")

STATUS_CACHE_FILE = Path("gtc_status_cache.json")
CHANGES_FILE      = Path("gtc_changes.json")


# Colonnes réelles confirmées du GPKG GTC MELCCFP
# detailsFiches: NO_MEF_LIEU, NO_SEQ_DOSSIER, AUTR_ADR_AFF, CONTAM_EAU_EXTRA, CONTAM_SOL_EXTRA, QUAL_SOLS_AV, ETAT_REHAB, QUAL_SOLS, DATE_CRE_MAJ
# point:         NO_MEF_LIEU, LATITUDE, LONGITUDE, ADR_CIV_LIEU, CODE_POST_LIEU, LST_MRC_REG_ADM, DESC_MILIEU_RECEPT, NB_FICHES

def v(row, *keys):
    """Extrait la première valeur non-nulle parmi les clés données."""
    for k in keys:
        val = row.get(k,"")
        if val is not None and str(val).strip() not in ("","nan","None","NULL","null","<NA>","nan"):
            return str(val).strip()
    return ""

def build_terrain(uid, d_row, p_row):
    """Construit un terrain à partir des deux couches mergées."""
    contam_sol = v(d_row, "CONTAM_SOL_EXTRA")
    contam_eau = v(d_row, "CONTAM_EAU_EXTRA")
    if contam_sol and contam_eau and contam_sol != contam_eau:
        contaminants = f"Sol: {contam_sol} | Eau: {contam_eau}"
    else:
        contaminants = contam_sol or contam_eau

    return {
        "id":              uid,
        "nom":             v(p_row, "ADR_CIV_LIEU") or f"Terrain {uid}",
        "adresse":         v(p_row, "ADR_CIV_LIEU", "AUTR_ADR_AFF"),
        "code_postal":     v(p_row, "CODE_POST_LIEU"),
        "municipalite":    v(p_row, "LST_MRC_REG_ADM"),
        "contaminants":    contaminants,
        "contam_sol":      contam_sol,            # Contaminants sol (détail brut)
        "contam_eau":      contam_eau,            # Contaminants eau (détail brut)
        "qual_sols":       v(d_row, "QUAL_SOLS", "QUAL_SOLS_AV"),
        "qual_sols_avant": v(d_row, "QUAL_SOLS_AV"),   # Qualité sols AVANT réhabilitation
        "no_dossier":      v(d_row, "NO_SEQ_DOSSIER"), # N° dossier officiel MELCCFP
        "statut":          v(d_row, "ETAT_REHAB"),
        "activite":        v(p_row, "DESC_MILIEU_RECEPT"),
        "nb_fiches":       v(p_row, "NB_FICHES"),
        "latitude":        v(p_row, "LATITUDE"),
        "longitude":       v(p_row, "LONGITUDE"),
        "date_maj":        v(d_row, "DATE_CRE_MAJ"),
        # Champ enrichi depuis la couche surface du GPKG
        "aire_contaminee_m2": 0,
    }

def download_gpkg():
    try:
        GPKG_DIR.mkdir(parents=True, exist_ok=True)
        existing = list(GPKG_DIR.glob("*.gpkg"))
        if existing:
            age_h = (time.time() - existing[0].stat().st_mtime) / 3600
            if age_h < GPKG_MAX_AGE_H:
                log.info(f"GPKG en cache: {existing[0].name} ({age_h:.1f}h)")
                return existing[0]
            log.info(f"Cache expiré ({age_h:.1f}h > {GPKG_MAX_AGE_H}h) — re-téléchargement...")
            existing[0].unlink()
        log.info("Téléchargement GTC (~50 Mo) ...")
        r = requests.get(GPKG_URL, timeout=180)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = [n for n in z.namelist() if n.endswith(".gpkg")]
        if not names: return None
        z.extractall(GPKG_DIR)
        return GPKG_DIR / Path(names[0]).name
    except Exception as e:
        log.error(f"Téléchargement: {e}")
        return None

def load_terrains():
    try:
        import geopandas as gpd
    except ImportError:
        log.error("pip install geopandas")
        return []

    gpkg = download_gpkg()
    if not gpkg: return []

    try:
        gdf_d = gpd.read_file(str(gpkg), layer="detailsFiches")
        gdf_p = gpd.read_file(str(gpkg), layer="point")
        log.info(f"detailsFiches: {len(gdf_d)} | point: {len(gdf_p)}")

        # Index par NO_MEF_LIEU
        details = {}
        for _, r in gdf_d.iterrows():
            uid = str(r.get("NO_MEF_LIEU","")).strip()
            if uid: details[uid] = r.to_dict()

        points = {}
        for _, r in gdf_p.iterrows():
            uid = str(r.get("NO_MEF_LIEU","")).strip()
            if uid: points[uid] = r.to_dict()

        # Charger les superficies contaminées depuis la couche 'surface'
        surface_areas = load_surface_areas(gpkg)

        terrains = []
        # Tous les UIDs uniques
        all_uids = set(details.keys()) | set(points.keys())
        for uid in all_uids:
            d = details.get(uid, {})
            p = points.get(uid, {})
            t = build_terrain(uid, d, p)
            t["aire_contaminee_m2"] = int(surface_areas.get(uid, 0))
            terrains.append(t)

        log.info(f"{len(terrains)} terrains construits")
        return terrains

    except Exception as e:
        log.error(f"Chargement GPKG: {e}")
        return []

def load_snapshot():
    if not SNAPSHOT_FILE.exists(): return set()
    try: return set(json.load(open(SNAPSHOT_FILE)))
    except: return set()

def save_snapshot(ids):
    try: json.dump(list(ids), open(SNAPSHOT_FILE,"w"))
    except Exception as e: log.error(f"Snapshot: {e}")

def write_dashboard(terrains, new_ids, last_sync):
    payload = {
        "last_sync": last_sync,
        "total":     len(terrains),
        "nouveaux":  len(new_ids),
        "terrains":  terrains,
        "new_ids":   list(new_ids),
    }
    json.dump(payload, open(DATA_FILE,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    log.info(f"gtc_data.json mis à jour ({len(terrains)} terrains)")

def send_email(terrains):
    if not all([SMTP_USER, SMTP_PASS, ALERT_EMAIL]): return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Biogenie — {len(terrains)} nouveau(x) terrain(s) GTC"
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_EMAIL
        rows = "".join(f"""<tr>
          <td style="padding:12px;border-bottom:1px solid #222;color:#e8edf0">
            {t['adresse'] or t['id']}<br>
            <small style="color:#888">{t['municipalite']} {t['code_postal']}</small>
          </td>
          <td style="padding:12px;border-bottom:1px solid #222;color:#ffb830;font-size:12px">{t['contaminants'] or '—'}</td>
          <td style="padding:12px;border-bottom:1px solid #222;color:#888;font-size:12px">{t['statut'] or '—'}</td>
          <td style="padding:12px;border-bottom:1px solid #222;color:#555;font-family:monospace;font-size:11px">{t['id']}</td>
        </tr>""" for t in terrains)
        html = f"""<html><body style="background:#0a0d0f;color:#e8edf0;font-family:system-ui;padding:28px">
        <h2 style="color:#00e87a;margin-bottom:6px">Biogenie — {len(terrains)} nouveau(x) terrain(s)</h2>
        <p style="color:#555;font-family:monospace;font-size:12px;margin-bottom:20px">{datetime.now().strftime('%Y-%m-%d %H:%M')} · Source: GTC MELCCFP</p>
        <table style="width:100%;border-collapse:collapse;background:#111518;border-radius:8px;overflow:hidden">
          <tr style="background:#181d21">
            <th style="padding:10px 12px;text-align:left;color:#555;font-size:11px;text-transform:uppercase">Adresse</th>
            <th style="padding:10px 12px;text-align:left;color:#555;font-size:11px;text-transform:uppercase">Contaminants</th>
            <th style="padding:10px 12px;text-align:left;color:#555;font-size:11px;text-transform:uppercase">Statut</th>
            <th style="padding:10px 12px;text-align:left;color:#555;font-size:11px;text-transform:uppercase">ID</th>
          </tr>{rows}
        </table>
        </body></html>"""
        msg.attach(MIMEText(html,"html"))
        with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        log.info(f"Email envoyé → {ALERT_EMAIL}")
    except Exception as e:
        log.error(f"Email: {e}")

def load_surface_areas(gpkg_path):
    """Lit la couche 'surface' du GPKG et calcule l'aire contaminée (m²) par terrain."""
    try:
        import geopandas as gpd
        gdf = gpd.read_file(str(gpkg_path), layer="surface")
        # Reprojeter en EPSG:32198 (MTM Québec) pour avoir des mètres
        gdf_m = gdf.to_crs("EPSG:32198")
        gdf_m["aire_m2"] = gdf_m.geometry.area.round(0).astype(int)
        # Sommer par NO_MEF_LIEU (un terrain peut avoir plusieurs polygones)
        areas = gdf_m.groupby("NO_MEF_LIEU")["aire_m2"].sum().to_dict()
        log.info(f"Superficie contaminée calculée pour {len(areas)} terrains (couche 'surface')")
        return areas
    except Exception as e:
        log.error(f"Lecture couche surface: {e}")
        return {}

def detect_status_changes(terrains):
    """Détecte les changements de statut ETAT_REHAB depuis le dernier check."""
    cache = {}
    if STATUS_CACHE_FILE.exists():
        try: cache = json.load(open(STATUS_CACHE_FILE))
        except: pass
    new_cache, changes = {}, []
    for t in terrains:
        uid, new_s = t["id"], t.get("statut", "")
        new_cache[uid] = new_s
        old_s = cache.get(uid)
        if old_s is not None and old_s != new_s and old_s and new_s:
            changes.append({
                "terrain_id":    uid,
                "adresse":       t.get("adresse", ""),
                "municipalite":  t.get("municipalite", ""),
                "ancien_statut": old_s,
                "nouveau_statut": new_s,
            })
    try: json.dump(new_cache, open(STATUS_CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception as e: log.error(f"Status cache: {e}")
    return changes


def push_status_changes(changes):
    """Envoie les changements de statut à Supabase."""
    if not changes or not (SUPABASE_URL and SUPABASE_KEY): return
    import urllib.request
    headers = {
        "Content-Type":  "application/json",
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    for c in changes:
        try:
            data = json.dumps(c).encode("utf-8")
            req  = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/gtc_changes", data=data, headers=headers, method="POST")
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            log.error(f"Push change: {e}")
    log.info(f"{len(changes)} changement(s) de statut → Supabase")


def check_reminders():
    """Envoie les rappels de suivi dont la date est aujourd'hui."""
    if not all([SUPABASE_URL, SUPABASE_KEY, SMTP_USER, SMTP_PASS, ALERT_EMAIL]): return
    import urllib.request
    today   = datetime.now().strftime("%Y-%m-%d")
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    try:
        url  = f"{SUPABASE_URL}/rest/v1/crm?reminder_date=eq.{today}&reminder_sent=eq.false&select=terrain_id,contact_nom,note"
        req  = urllib.request.Request(url, headers=headers)
        rows = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if not rows: return
        log.info(f"{len(rows)} rappel(s) à envoyer...")
        patch_h = {**headers, "Content-Type": "application/json", "Prefer": "return=minimal"}
        for r in rows:
            _send_reminder(r["terrain_id"], r.get("contact_nom", ""), r.get("note", ""))
            patch = json.dumps({"reminder_sent": True}).encode("utf-8")
            preq  = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/crm?terrain_id=eq.{r['terrain_id']}",
                data=patch, headers=patch_h, method="PATCH"
            )
            urllib.request.urlopen(preq, timeout=10)
    except Exception as e:
        log.error(f"Rappels: {e}")


def _send_reminder(terrain_id, contact_nom, note):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Biogenie — Rappel de suivi : {terrain_id}"
        msg["From"], msg["To"] = SMTP_USER, ALERT_EMAIL
        rows = ""
        if contact_nom: rows += f'<tr><td style="padding:6px 0;color:#888;font-size:12px">Contact</td><td style="padding:6px 0">{contact_nom}</td></tr>'
        if note:        rows += f'<tr><td style="padding:6px 0;color:#888;font-size:12px;vertical-align:top">Note</td><td style="padding:6px 0">{note}</td></tr>'
        html = f"""<html><body style="background:#0a0d0f;color:#e8edf0;font-family:system-ui;padding:28px">
        <h2 style="color:#00e87a;margin-bottom:8px">⏰ Rappel de suivi — Biogenie</h2>
        <table><tr><td style="padding:6px 0;color:#888;font-size:12px">Dossier GTC</td><td style="padding:6px 0;font-weight:700">{terrain_id}</td></tr>{rows}</table>
        <p style="color:#555;font-family:monospace;font-size:11px;margin-top:16px">{datetime.now().strftime('%Y-%m-%d %H:%M')} · Biogenie Veille GTC</p>
        </body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        log.info(f"Rappel envoyé → {terrain_id}")
    except Exception as e:
        log.error(f"Rappel email: {e}")


def run_check():
    log.info("─"*50)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log.info(f"Vérification GTC — {now}")

    terrains = load_terrains()
    if not terrains:
        log.warning("Aucune donnée — réessai dans 15 min")
        return

    known   = load_snapshot()
    all_ids = {t["id"] for t in terrains}
    new_ids = all_ids - known

    if not known:
        log.info(f"Premier lancement — {len(all_ids)} terrains indexés, aucune alerte envoyée")
        write_dashboard(terrains, set(), now)
    elif not new_ids:
        log.info(f"Aucun nouveau terrain (connu: {len(known)})")
        write_dashboard(terrains, set(), now)
    else:
        nouveaux = [t for t in terrains if t["id"] in new_ids]
        log.info(f"🚨 {len(nouveaux)} NOUVEAU(X) TERRAIN(S) !")
        for t in nouveaux:
            log.info(f"  → [{t['id']}] {t['adresse']}, {t['municipalite']} | {t['contaminants']}")
        fname = f"alerte_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json.dump(nouveaux, open(fname,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
        write_dashboard(terrains, new_ids, now)
        send_email(nouveaux)

    # Changements de statut
    changes = detect_status_changes(terrains)
    if changes:
        log.info(f"🔄 {len(changes)} changement(s) de statut détecté(s)")
        for c in changes:
            log.info(f"  → [{c['terrain_id']}] {c['ancien_statut']} → {c['nouveau_statut']}")
        push_status_changes(changes)

    # Rappels de suivi
    check_reminders()

    save_snapshot(all_ids)
    log.info(f"Snapshot: {len(all_ids)} terrains connus")

def main():
    log.info("="*50)
    log.info("BIOGENIE — Moniteur GTC v4.1")
    log.info(f"Actualisation toutes les {INTERVAL_MIN} minutes")
    log.info("="*50)
    run_check()
    schedule.every(INTERVAL_MIN).minutes.do(run_check)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        # Mode GitHub Actions : une vérification et on quitte
        run_check()
    else:
        main()
