# Biogenie — Moniteur GTC

Surveille en temps réel le Répertoire des terrains contaminés du Québec (GTC).
Dès qu'un nouveau terrain apparaît, Biogenie envoie un **email** automatique.

---

## Déploiement gratuit (GitHub Actions + GitHub Pages)

C'est l'option recommandée : **zéro serveur, zéro coût**, le dashboard est accessible en ligne pour toute l'équipe.

### 1. Créer un repo GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/TON_USER/biogenie.git
git push -u origin main
```

### 2. Ajouter les secrets GitHub

Dans le repo → **Settings > Secrets and variables > Actions** → New repository secret :

| Nom | Valeur |
|-----|--------|
| `SMTP_USER` | ton adresse Gmail |
| `SMTP_PASS` | ton App Password Gmail |
| `ALERT_EMAIL` | email qui reçoit les alertes |

### 3. Activer GitHub Pages

Dans le repo → **Settings > Pages** → Source : `Deploy from a branch` → branche `main`, dossier `/ (root)`.

Le dashboard sera accessible sur : `https://TON_USER.github.io/biogenie/dashboard.html`

### 4. C'est tout !

Le moniteur tourne automatiquement **toutes les heures** via GitHub Actions.
Tu peux aussi le déclencher manuellement depuis l'onglet **Actions** du repo.

---

## Utilisation locale

### Pré-requis
- Python 3.10+
- Un compte Gmail avec App Password activé → myaccount.google.com/apppasswords

### Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Ouvre .env et remplis tes identifiants Gmail
```

### Lancer le moniteur en continu (vérifie toutes les 15 min)

```bash
python monitor.py
```

### Lancer une seule vérification

```bash
python monitor.py --once
```

### Lancer avec le dashboard web (port 8080)

```bash
python server.py
# Dashboard : http://localhost:8080/dashboard.html
```

---

## Ce que tu reçois quand un terrain est détecté

**Email (récapitulatif HTML) :**
Tableau avec tous les nouveaux terrains : adresse, municipalité, contaminants, statut, ID GTC.

---

## Sources de données

| Source | Fréquence màj | Champs disponibles |
|--------|--------------|-------------------|
| GTC MELCCFP (GPKG) | Périodique | Nom, adresse, contaminants, statut, superficie, coordonnées GPS |

**Fichier source :** Azure Blob Storage MELCCFP — `RepertoireTerrainsContamines.gpkg.zip`
**Licence :** Creative Commons 4.0 Attribution (CC-BY) — Québec

---

## Évolutions possibles

- [ ] Filtrer par région (Montréal, Laval, Rive-Sud...)
- [ ] Filtrer par type de contaminant (hydrocarbures, métaux lourds...)
- [ ] Intégration webhook Slack
- [ ] Alertes SMS via Twilio
- [ ] Scraping registre foncier (nouvelles inscriptions)
