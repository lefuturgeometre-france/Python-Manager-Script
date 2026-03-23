import os
import subprocess
import json
import uuid
from flask import Flask, render_template_string, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# Configuration
CONFIG_FILE = "scripts_config.json"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Stockage des processus et scheduler
processes = {}
scheduler = BackgroundScheduler()
scheduler.start()

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def run_script(script_id):
    config = load_config()
    script = config.get(script_id)
    if not script: return

    # Mise à jour de la dernière exécution
    config[script_id]['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(config)

    log_path = os.path.join(LOG_DIR, f"{script_id}.log")
    
    # Lancement du processus à l'emplacement du fichier
    script_path = script['path']
    working_dir = os.path.dirname(script_path)

    with open(log_path, "a") as log_file:
        log_file.write(f"\n--- Lancé le {datetime.now()} ---\n")
    
    proc = subprocess.Popen(
        ["python", os.path.basename(script_path)],
        cwd=working_dir, # Exécution dans son propre dossier
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        text=True
    )
    processes[script_id] = proc

# --- INTERFACE HTML ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Python Orchestrator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style> .time-text { font-size: 0.85rem; color: #666; } </style>
</head>
<body class="container mt-5">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>🚀 Manager de Scripts</h2>
        <span class="badge bg-info text-dark">Total: {{ scripts|length }}</span>
    </div>
    
    <div class="card p-4 mb-4 shadow-sm">
        <h5>Ajouter un script existant</h5>
        <form action="/add" method="post" class="row g-3">
            <div class="col-md-6">
                <input type="text" name="path" class="form-control" placeholder="Chemin absolu (ex: C:/projets/script.py)" required>
            </div>
            <div class="col-md-4">
                <input type="text" name="cron" class="form-control" placeholder="Cron (ex: */30 * * * *)">
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary w-100">Enregistrer</button>
            </div>
        </form>
    </div>

    <table class="table table-hover border">
        <thead class="table-light">
            <tr>
                <th>Nom & Chemin</th>
                <th>Planification / Prochain</th>
                <th>Dernière exécution</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for id, s in scripts.items() %}
            <tr>
                <td>
                    <strong>{{ s.path.split('/')[-1].split('\\\\')[-1] }}</strong><br>
                    <small class="text-muted">{{ s.path }}</small>
                </td>
                <td>
                    <span class="badge bg-secondary">{{ s.cron if s.cron else 'Manuel' }}</span><br>
                    <span class="time-text">Prochain: {{ next_runs[id] }}</span>
                </td>
                <td class="time-text">{{ s.last_run if s.last_run else 'Jamais' }}</td>
                <td>
                    <div class="btn-group">
                        <a href="/start/{{ id }}" class="btn btn-outline-success btn-sm">▶</a>
                        <a href="/stop/{{ id }}" class="btn btn-outline-warning btn-sm">⏹</a>
                        <a href="/logs/{{ id }}" target="_blank" class="btn btn-outline-info btn-sm">Log</a>
                        <a href="/delete/{{ id }}" class="btn btn-outline-danger btn-sm" onclick="return confirm('Supprimer ce script du manager ?')">🗑</a>
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    config = load_config()
    next_runs = {}
    for script_id in config:
        job = scheduler.get_job(script_id)
        next_runs[script_id] = job.next_run_time.strftime("%H:%M:%S") if job and job.next_run_time else "N/A"
    
    return render_template_string(HTML_TEMPLATE, scripts=config, next_runs=next_runs)

@app.route('/add', methods=['POST'])
def add_script():
    path = request.form.get('path').strip()
    cron = request.form.get('cron').strip()
    
    if os.path.exists(path):
        script_id = str(uuid.uuid4())[:8]
        config = load_config()
        config[script_id] = {'path': path, 'cron': cron, 'last_run': None}
        save_config(config)
        
        if cron:
            try:
                # Format cron simple: min hour day month day_of_week
                parts = cron.split()
                scheduler.add_job(run_script, 'cron', 
                                  minute=parts[0], hour=parts[1], 
                                  id=script_id, args=[script_id])
            except: pass
    return redirect('/')

@app.route('/delete/<script_id>')
def delete_script(script_id):
    config = load_config()
    if script_id in config:
        # Arrêter le job s'il existe
        if scheduler.get_job(script_id):
            scheduler.remove_job(script_id)
        # Supprimer de la config (le fichier sur disque reste intact)
        del config[script_id]
        save_config(config)
    return redirect('/')

@app.route('/start/<script_id>')
def start(script_id):
    run_script(script_id)
    return redirect('/')

@app.route('/stop/<script_id>')
def stop(script_id):
    proc = processes.get(script_id)
    if proc:
        proc.terminate()
        del processes[script_id]
    return redirect('/')

@app.route('/logs/<script_id>')
def get_logs(script_id):
    log_path = os.path.join(LOG_DIR, f"{script_id}.log")
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f"<pre style='background:#222; color:#eee; padding:20px;'>{f.read()}</pre>"
    return "Aucun log trouvé."

if __name__ == '__main__':
    # Initialisation des jobs au démarrage
    initial_config = load_config()
    for sid, s in initial_config.items():
        if s.get('cron'):
            try:
                p = s['cron'].split()
                scheduler.add_job(run_script, 'cron', minute=p[0], hour=p[1], id=sid, args=[sid])
            except: pass

    app.run(debug=True, port=5000)