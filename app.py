import os
import subprocess
import json
import uuid
import sys
from flask import Flask, render_template_string, request, redirect, Response
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# Configuration
CONFIG_FILE = "scripts_config.json"
LOG_DIR = "logs"
SERVER_LOG = os.path.join(LOG_DIR, "manager_server.log")
os.makedirs(LOG_DIR, exist_ok=True)

import sys

# --- CONFIGURATION DES LOGS "DOUBLE SORTIE" ---
class Tee(object):
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush() # Force l'écriture immédiate
    def flush(self):
        for f in self.files:
            f.flush()

# On garde une copie de la console d'origine
original_stdout = sys.stdout

# On ouvre le fichier de log
log_file = open(SERVER_LOG, "a", encoding='utf-8', errors='replace')

# On redirige tout vers (Console + Fichier)
sys.stdout = Tee(original_stdout, log_file)
sys.stderr = sys.stdout

processes = {}
scheduler = BackgroundScheduler()
scheduler.start()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def is_proc_running(sid):
    """Vérifie si le processus est réellement en cours d'exécution"""
    proc = processes.get(sid)
    if proc:
        if proc.poll() is None: # poll() est None tant que le proc tourne
            return True
        else:
            del processes[sid] # Nettoyage si fini
    return False

def run_script(script_id):
    config = load_config()
    script = config.get(script_id)
    if not script or is_proc_running(script_id): return

    config[script_id]['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(config)

    log_path = os.path.join(LOG_DIR, f"{script_id}.log")
    working_dir = os.path.dirname(script['path'])

    with open(log_path, "a", encoding='utf-8') as log_file:
        log_file.write(f"\n--- [START] {datetime.now()} ---\n")
    
    proc = subprocess.Popen(
        ["python", os.path.basename(script['path'])],
        cwd=working_dir,
        stdout=open(log_path, "a", encoding='utf-8'),
        stderr=subprocess.STDOUT,
        text=True
    )
    processes[script_id] = proc

    # FORCER L'UTF-8 POUR LE SCRIPT ENFANT
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.Popen(
            ["python", os.path.basename(script['path'])],
            cwd=working_dir,
            stdout=open(log_path, "a", encoding='utf-8', errors='replace'),
            stderr=subprocess.STDOUT,
            text=True,
            env=env, # <-- On injecte l'environnement ici
            encoding='utf-8' # <-- On force l'encodage du flux
        )
        processes[script_id] = proc
    except Exception as e:
        pass

def build_cron_string(freq, val_min="0", val_hour="0", val_day="*"):
    """Génère une expression Cron à partir de paramètres simples"""
    if freq == "minutes":
        return f"*/{val_min} * * * *"
    elif freq == "hourly":
        return f"{val_min} * * * *"
    elif freq == "daily":
        return f"{val_min} {val_hour} * * *"
    elif freq == "weekly":
        return f"{val_min} {val_hour} * * {val_day}"
    return None


# --- TEMPLATE PRINCIPAL ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Python Orchestrator Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f4f7f6; font-family: 'Segoe UI', sans-serif; }
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .dot-running { background-color: #28a745; box-shadow: 0 0 8px #28a745; }
        .dot-stopped { background-color: #dc3545; }
    </style>
</head>
<body class="container py-5">
    <div class="d-flex justify-content-between align-items-center mb-4 text-white p-4 rounded shadow-sm" style="background: #2c3e50;">
        <div>
            <h2 class="m-0">🚀 Script Manager</h2>
            <small class="opacity-75">Contrôle et automatisation Python</small>
        </div>
        <div>
            <a href="/logs/manager" target="_blank" class="btn btn-outline-light btn-sm">Logs du Serveur</a>
        </div>
    </div>
    
    <div class="card border-0 shadow-sm p-4 mb-4">
    <form action="/add" method="post" id="addForm">
        <div class="row g-3">
            <div class="col-md-12">
                <label class="form-label fw-bold">Chemin du script .py</label>
                <input type="text" name="path" class="form-control" placeholder="C:/chemin/vers/script.py" required>
            </div>

            <div class="col-md-3">
                <label class="form-label fw-bold">Mode Programmation</label>
                <select name="cron_mode" id="cron_mode" class="form-select" onchange="toggleCronMode()">
                    <option value="simple">Générateur Simple</option>
                    <option value="manual">Manuel (Cron Expert)</option>
                </select>
            </div>

            <div id="simple_fields" class="col-md-7 row g-2">
                <div class="col-md-4">
                    <label class="form-label">Fréquence</label>
                    <select name="freq" class="form-select">
                        <option value="minutes">Toutes les X minutes</option>
                        <option value="hourly">Toutes les heures (à :min)</option>
                        <option value="daily">Tous les jours (à HH:mm)</option>
                        <option value="weekly">Toutes les semaines</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Minute</label>
                    <input type="number" name="s_min" class="form-control" value="0" min="0" max="59">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Heure</label>
                    <input type="number" name="s_hour" class="form-control" value="0" min="0" max="23">
                </div>
                <div class="col-md-4">
                    <label class="form-label">Jour (0=Lun, 6=Dim)</label>
                    <input type="text" name="s_day" class="form-control" value="*" placeholder="* ou 0-6">
                </div>
            </div>

            <div id="manual_fields" class="col-md-7" style="display:none;">
                <label class="form-label">Expression Cron</label>
                <input type="text" name="cron" class="form-control" placeholder="*/5 * * * *">
                <div class="form-text">Format: min heure jour mois jour_semaine</div>
            </div>

            <div class="col-md-2 d-flex align-items-end">
                <button type="submit" class="btn btn-primary w-100 py-2">Enregistrer</button>
            </div>
        </div>
    </form>
</div>

<script>
function toggleCronMode() {
    const mode = document.getElementById('cron_mode').value;
    document.getElementById('simple_fields').style.display = (mode === 'simple') ? 'flex' : 'none';
    document.getElementById('manual_fields').style.display = (mode === 'manual') ? 'block' : 'none';
}
</script>

    <div class="table-responsive bg-white rounded shadow-sm">
        <table class="table table-hover align-middle mb-0">
            <thead class="table-dark">
                <tr>
                    <th>Statut</th>
                    <th>Script</th>
                    <th>Planning / Prochain</th>
                    <th>Dernière exécution</th>
                    <th class="text-end">Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for id, s in scripts.items() %}
                <tr>
                    <td>
                        {% if running_status[id] %}
                        <span class="badge rounded-pill bg-success-subtle text-success border border-success">
                            <span class="status-dot dot-running"></span> Actif
                        </span>
                        {% else %}
                        <span class="badge rounded-pill bg-light text-muted border">
                            <span class="status-dot dot-stopped"></span> Off
                        </span>
                        {% endif %}
                    </td>
                    <td>
                        <div class="fw-bold">{{ s.path.split('/')[-1].split('\\\\')[-1] }}</div>
                        <div class="text-muted small">{{ s.path }}</div>
                    </td>
                    <td>
                        <span class="badge bg-info text-dark">{{ s.cron if s.cron else 'Manuel' }}</span>
                        <div class="small text-muted mt-1">Next: {{ next_runs[id] }}</div>
                    </td>
                    <td class="small text-muted">{{ s.last_run if s.last_run else '-' }}</td>
                    <td class="text-end">
                        <div class="btn-group btn-group-sm">
                            <a href="/start/{{ id }}" class="btn btn-success">▶</a>
                            <a href="/stop/{{ id }}" class="btn btn-warning">⏹</a>
                            <a href="/view_logs/{{ id }}" class="btn btn-info text-white">Logs</a>
                            <a href="/delete/{{ id }}" class="btn btn-danger" onclick="return confirm('Supprimer ?')">🗑</a>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# --- TEMPLATE LOGS AUTO-REFRESH ---
LOG_VIEW_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Logs - {{ name }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body style="background: #1e1e1e; color: #dcdcdc; font-family: 'Consolas', monospace; padding: 20px;">
    <div class="d-flex justify-content-between align-items-center border-bottom border-secondary pb-2 mb-3">
        <h4>Logs: {{ name }}</h4>
        <div>
            <span class="badge bg-success" id="status-indicator">Auto-refresh actif</span>
            <a href="/" class="btn btn-sm btn-outline-light ms-3">Retour</a>
        </div>
    </div>
    <pre id="log-content" style="white-space: pre-wrap; word-wrap: break-word;">Chargement...</pre>

    <script>
        function fetchLogs() {
            fetch('/raw_logs/{{ sid }}')
                .then(response => response.text())
                .then(data => {
                    const container = document.getElementById('log-content');
                    // On ne met à jour que si le contenu a changé pour économiser les ressources
                    if (container.innerText !== data) {
                        container.innerText = data;
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                });
        }
        setInterval(fetchLogs, 2000); // Rafraîchit toutes les 2 secondes
        fetchLogs();
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def index():
    config = load_config()
    next_runs = {}
    running_status = {}
    for sid in config:
        job = scheduler.get_job(sid)
        next_runs[sid] = job.next_run_time.strftime("%H:%M:%S") if (job and job.next_run_time) else "N/A"
        running_status[sid] = is_proc_running(sid)
    return render_template_string(HTML_TEMPLATE, scripts=config, next_runs=next_runs, running_status=running_status)

@app.route('/view_logs/<sid>')
def view_logs(sid):
    config = load_config()
    name = "Manager Server" if sid == "manager" else config.get(sid, {}).get('path', 'Inconnu')
    return render_template_string(LOG_VIEW_TEMPLATE, sid=sid, name=name)

@app.route('/raw_logs/<sid>')


def raw_logs(sid):
    log_path = SERVER_LOG if sid == "manager" else os.path.join(LOG_DIR, f"{sid}.log")
    
    if os.path.exists(log_path):
        with open(log_path, "r", encoding='utf-8', errors='replace') as f:
            return f.read()
    return "Aucun log."

@app.route('/logs/manager')
def server_logs():
    return redirect('/view_logs/manager')


@app.route('/add', methods=['POST'])
def add_script():
    path = request.form.get('path').strip().replace('"', '')
    mode = request.form.get('cron_mode') # 'manual' ou 'simple'
    cron = ""

    if mode == 'manual':
        cron = request.form.get('cron').strip()
    else:
        freq = request.form.get('freq')
        m = request.form.get('s_min', '0')
        h = request.form.get('s_hour', '0')
        d = request.form.get('s_day', '*')
        cron = build_cron_string(freq, m, h, d)

    if os.path.exists(path):
        sid = str(uuid.uuid4())[:8]
        config = load_config()
        config[sid] = {'path': path, 'cron': cron, 'last_run': None}
        save_config(config)
        
        if cron:
            try:
                p = cron.split()
                # On s'assure d'avoir 5 parties
                scheduler.add_job(run_script, 'cron', 
                                  minute=p[0], hour=p[1], day=p[2], 
                                  month=p[3], day_of_week=p[4], 
                                  id=sid, args=[sid])
            except Exception as e:
                print(f"Erreur Scheduler: {e}")
                
    return redirect('/')

@app.route('/start/<sid>')
def start(sid):
    run_script(sid)
    return redirect('/')

@app.route('/stop/<sid>')
def stop(sid):
    if sid in processes:
        processes[sid].terminate()
        del processes[sid]
    return redirect('/')

@app.route('/delete/<sid>')
def delete_script(sid):
    config = load_config()
    if sid in config:
        if scheduler.get_job(sid): scheduler.remove_job(sid)
        del config[sid]
        save_config(config)
    return redirect('/')

if __name__ == '__main__':
    # Recharger les jobs au lancement
    cfg = load_config()
    for sid, s in cfg.items():
        if s.get('cron'):
            try:
                p = s['cron'].split()
                scheduler.add_job(run_script, 'cron', minute=p[0], hour=p[1], id=sid, args=[sid])
            except: pass
    app.run(debug=True, port=5000, use_reloader=False) # use_reloader=False pour éviter les conflits de scheduler