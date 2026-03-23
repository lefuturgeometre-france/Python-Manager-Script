# 🐍 Python Script Manager (Orchestrator)
Ton nouveau centre de contrôle pour scripts Python. Fini le lancement manuel dans dix terminaux différents. Cette application Flask te permet de centraliser, programmer et surveiller tous tes scripts via une interface web sécurisée et moderne.

## 🚀 Fonctionnalités Clés
Tableau de Bord Dynamique : Visualise en un coup d'œil le nombre de scripts totaux et ceux en cours d'exécution.

Ajout par Chemin (Path) : Pas besoin de déplacer tes fichiers. Indique le chemin absolu, le manager s'occupe du reste.

Programmation Intelligente :

Générateur Simple : Planifie des tâches en quelques clics (toutes les X minutes, tous les jours à 8h, etc.).

Mode Expert : Supporte les expressions Cron standard pour une précision totale.

Monitoring Temps Réel :

Point vert/rouge pour le statut en direct.

Logs avec auto-refresh toutes les 2 secondes (plus besoin de F5).

Historique d'exécution avec l'en-tête précis : --- [START] YYYY-MM-DD HH:MM:SS ---.

Sécurité Totale : Portail de connexion obligatoire. Rien n'est accessible sans authentification.

Robustesse Windows : Gestion automatique des encodages (UTF-8) pour éviter les crashs sur les accents ou les emojis.

## 📂 Structure du Projet
Plaintext
ManagerGemini/
├── app.py                 # Le cerveau (Flask + Scheduler)
├── .env                   # Configuration secrète (Identifiants, Ports)
├── scripts_config.json    # "Base de données" (Généré automatiquement)
├── logs/                  # Dossier de stockage des journaux
│   ├── manager_server.log # Logs du serveur lui-même
│   └── [id].log           # Logs spécifiques à chaque script
└── templates/             # Interface utilisateur
    ├── index.html         # Dashboard principal
    ├── login.html         # Page de connexion
    └── logs.html          # Visualiseur de logs auto-refresh
## 🛠 Installation Rapide
Installe les dépendances :

Bash
pip install flask apscheduler python-dotenv
Configure ton environnement :
Crée un fichier .env à la racine :

Extrait de code
FLASK_PORT=5000
AUTH_USER=admin
AUTH_PASSWORD=ton_pass
SECRET_KEY=genere_une_cle_au_pif_123
LOG_DIR=logs
CONFIG_FILE=scripts_config.json
SERVER_LOG_NAME=manager_server.log
Lance la bête :

Bash
python app.py
## 💡 Guide d'Utilisation
Connexion : Rends-toi sur http://127.0.0.1:5000 et connecte-toi avec tes identifiants du .env.

Ajout : Clique sur "+ Ajouter un nouveau script", donne-lui un nom sympa et colle le chemin vers ton fichier .py.

Logs : Clique sur le bouton "Logs" d'un script. La fenêtre restera ouverte et affichera le texte au fur et à mesure que ton script travaille.

Arrêt d'urgence : Si un script s'emballe, le bouton ⏹ (Stop) termine proprement le processus.

## ⚠️ Notes de Compatibilité
Encodage : Le manager force PYTHONIOENCODING="utf-8". Si tes scripts utilisent des caractères spéciaux, ils s'afficheront parfaitement sur le web.

Mode Debug : Le serveur est lancé avec use_reloader=False pour éviter que les tâches planifiées ne se déclenchent en double.

## Note
Fait avec IA Gemini Pro