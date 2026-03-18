# Biogenie — Moniteur GTC

Surveille en temps réel le Répertoire des terrains contaminés du Québec (GTC - MELCCFP).
Dès qu'un nouveau terrain apparaît, Biogenie reçoit une **alerte email automatique**.

---

## Dashboard en ligne

```
https://antoinebeg05.github.io/AAA/dashboard.html
```

Accessible par toute l'équipe, sans rien installer. Fonctionne sur Mac, Windows et téléphone.

---

## Ce que fait ce logiciel

- 📡 **Surveille** le fichier GTC du gouvernement québécois 4x par jour
- 📧 **Envoie un email** automatique dès qu'un nouveau terrain est détecté
- 🗺️ **Carte interactive** avec code couleur par statut de réhabilitation
- 📋 **CRM intégré** : notes, pipeline, rappels, historique par terrain
- 📊 **Statistiques** : vue d'ensemble des terrains suivis
- 🔒 **Accès protégé** par mot de passe pour l'équipe

---

## Code couleur des terrains

| Couleur | Statut |
|---|---|
| 🔴 Rouge | Réhabilitation non débutée |
| 🟠 Orange | Réhabilitation en cours |
| 🟢 Vert | Réhabilitation terminée |
| ⚫ Gris | Statut inconnu |

---

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `dashboard.html` | Interface principale (carte, liste, CRM) |
| `monitor.py` | Script de surveillance GTC |
| `requirements.txt` | Dépendances Python |
| `supabase_setup.sql` | Configuration base de données (une seule fois) |
| `.github/workflows/monitor.yml` | Automatisation GitHub Actions |
| `env.example` | Modèle de configuration (sans mots de passe) |

---

## Configuration initiale

### 1. Fichier `.env` (ne jamais mettre sur GitHub)
```bash
cp env.example .env
# Remplir avec tes vraies valeurs
```

```
SMTP_USER=votre.email@gmail.com
SMTP_PASS=votre_app_password_gmail
ALERT_EMAIL=votre.email@gmail.com
```

> App Password Gmail → myaccount.google.com/apppasswords

### 2. Dépendances Python
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Test local
```bash
python3 monitor.py --once
```

---

## Secrets GitHub Actions

**Settings → Secrets and variables → Actions → New repository secret**

| Nom | Valeur |
|---|---|
| `SMTP_USER` | Adresse Gmail |
| `SMTP_PASS` | App Password Gmail |
| `ALERT_EMAIL` | Email destinataire des alertes |

---

## Activer le mot de passe du dashboard

1. Ouvrir le dashboard dans le navigateur
2. Ouvrir la console (F12 → onglet Console)
3. Taper : `genererHash('VotreMotDePasse')`
4. Copier le hash affiché
5. Le coller dans `dashboard.html` à la ligne `const PASS_HASH = '...'`
6. Commit + Push dans GitHub Desktop

---

## Moniteur automatique

Tourne via GitHub Actions **4x par jour** :

| Heure UTC | Heure Québec |
|---|---|
| 0h | 20h (veille) |
| 6h | 2h |
| 12h | 8h |
| 18h | 14h |

Déclenchement manuel possible : onglet **Actions** → **Biogenie — Veille GTC** → **Run workflow**

---

## Source des données

**Répertoire des terrains contaminés (GTC)** — MELCCFP, Gouvernement du Québec
Licence CC-BY 4.0 — https://www.donneesquebec.ca

---

*Biogenie — Consultation environnementale, Québec*
