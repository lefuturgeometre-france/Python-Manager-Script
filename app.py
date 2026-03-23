import os
import subprocess
import json
import uuid
from flask import Flask, render_template_string, request, redirect, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# Configuration
SCRIPT_DIR = "managed_scripts"
LOG_DIR = "logs"
CONFIG_FILE = "scripts_config.json"
os.makedirs(SCRIPT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Stockage des processus actifs et du scheduler
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

    log_path = os.path.join(LOG_DIR, f"{script_id}.log")
    with open(log_path, "a") as log_file:
        log_file.write(f"\n--- Démarrage le {datetime.now()} ---\n")
        
    # Lancement du processus
    proc = subprocess.Popen(
        ["python", os.path.join(SCRIPT_DIR, script['filename'])],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        text=True
    )
    processes[script_id] = proc

# --- ROUTES WEB ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Python Script Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="container mt-5">
    <h2>🚀 Manager de Scripts Python</h2>
    
    <div class="card p-4 mb-4">
        <h4>Ajouter un Script</h4>
        <form action="/add" method="post" enctype="multipart/form-data" class="row g-3">
            <div class="col-auto"><input type="file" name="file" class="form-control" required></div>
            <div class="col-auto"><input type="text" name="cron" class="form-control" placeholder="Cron (ex: */5 * * * *) ou vide"></div>
            <div class="col-auto"><button type="submit" class="btn btn-primary">Ajouter</button></div>
        </form>
    </div>

    <table class="table table-striped">
        <thead>
            <tr>
                <th>Nom</th>
                <th>Planification</th>
                <th>Actions</th>
                <th>Logs</th>
            </tr>
        </thead>
        <tbody>
            {% for id, s in scripts.items() %}
            <tr>
                <td>{{ s.filename }}</td>
                <td>{{ s.cron if s.cron else 'Manuel' }}</td>
                <td>
                    <a href="/start/{{ id }}" class="btn btn-success btn-sm">Lancer</a>
                    <a href="/stop/{{ id }}" class="btn btn-danger btn-sm">Arrêter</a>
                </td>
                <td><a href="/logs/{{ id }}" target="_blank">Voir logs</a></td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, scripts=load_config())

@app.route('/add', methods=['POST'])
def add_script():
    file = request.files['file']
    cron = request.form.get('cron')
    if file:
        script_id = str(uuid.uuid4())[:8]
        filename = file.filename
        file.save(os.path.join(SCRIPT_DIR, filename))
        
        config = load_config()
        config[script_id] = {'filename': filename, 'cron': cron}
        save_config(config)
        
        if cron:
            scheduler.add_job(run_script, 'cron', 
                              minute=cron.split()[0], 
                              hour=cron.split()[1], 
                              id=script_id, 
                              args=[script_id])
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
            return f"<pre>{f.read()}</pre>"
    return "Aucun log trouvé."

if __name__ == '__main__':
    app.run(debug=True, port=5000)