import os
import subprocess
import json
import uuid
import sys
from flask import Flask, render_template, request, redirect
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

app = Flask(__name__)

# Configuration via .env
CONFIG_FILE = os.getenv("CONFIG_FILE", "scripts_config.json")
LOG_DIR = os.getenv("LOG_DIR", "logs")
SERVER_LOG = os.path.join(LOG_DIR, os.getenv("SERVER_LOG_NAME", "manager_server.log"))
PORT = int(os.getenv("FLASK_PORT", 5000))

os.makedirs(LOG_DIR, exist_ok=True)

# --- LOGS DOUBLE SORTIE (Console + Fichier) ---
class Tee(object):
    def __init__(self, *files): self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files: f.flush()

if not hasattr(sys.stdout, 'files'):
    log_file = open(SERVER_LOG, "a", encoding='utf-8', errors='replace')
    sys.stdout = Tee(sys.stdout, log_file)
    sys.stderr = sys.stdout

processes = {}
scheduler = BackgroundScheduler()
scheduler.start()

# --- FONCTIONS LOGIQUE ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config, f, indent=4)

def is_proc_running(sid):
    proc = processes.get(sid)
    if proc:
        if proc.poll() is None: return True
        else: del processes[sid]
    return False

def build_cron_string(freq, val_min="0", val_hour="0", val_day="*"):
    if freq == "minutes": return f"*/{val_min} * * * *"
    if freq == "hourly": return f"{val_min} * * * *"
    if freq == "daily": return f"{val_min} {val_hour} * * *"
    if freq == "weekly": return f"{val_min} {val_hour} * * {val_day}"
    return None

def run_script(script_id):
    config = load_config()
    script = config.get(script_id)
    if not script or is_proc_running(script_id): return

    # Mise à jour de la date dans l'interface
    config[script_id]['last_run'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(config)

    log_path = os.path.join(LOG_DIR, f"{script_id}.log")
    
    # --- RESTAURATION DE L'EN-TÊTE DE LOG DEMANDÉ ---
    with open(log_path, "a", encoding='utf-8', errors='replace') as log_file:
        log_file.write(f"\n--- [START] {datetime.now()} ---\n")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    try:
        proc = subprocess.Popen(
            ["python", os.path.basename(script['path'])],
            cwd=os.path.dirname(script['path']),
            stdout=open(log_path, "a", encoding='utf-8', errors='replace'),
            stderr=subprocess.STDOUT, 
            text=True, 
            env=env
        )
        processes[script_id] = proc
    except Exception as e: 
        print(f"Erreur lancement {script_id}: {e}")

# --- ROUTES ---

@app.route('/')
def index():
    config = load_config()
    next_runs, running_status = {}, {}
    running_count = 0
    for sid in config:
        job = scheduler.get_job(sid)
        next_runs[sid] = job.next_run_time.strftime("%H:%M:%S") if (job and job.next_run_time) else "N/A"
        is_running = is_proc_running(sid)
        running_status[sid] = is_running
        if is_running: running_count += 1
    
    return render_template('index.html', 
                           scripts=config, 
                           next_runs=next_runs, 
                           running_status=running_status,
                           total_count=len(config),
                           running_count=running_count)

@app.route('/add', methods=['POST'])
def add_script():
    name = request.form.get('name', '').strip()
    path = request.form.get('path', '').strip().replace('"', '')
    mode = request.form.get('cron_mode')
    
    if mode == 'manual':
        cron = request.form.get('cron', '').strip()
    else:
        cron = build_cron_string(
            request.form.get('freq'), 
            request.form.get('s_min', '0'), 
            request.form.get('s_hour', '0'), 
            request.form.get('s_day', '*')
        )

    if os.path.exists(path):
        sid = str(uuid.uuid4())[:8]
        config = load_config()
        config[sid] = {'name': name, 'path': path, 'cron': cron, 'last_run': None}
        save_config(config)
        if cron:
            try:
                p = cron.split()
                scheduler.add_job(run_script, 'cron', minute=p[0], hour=p[1], day=p[2], month=p[3], day_of_week=p[4], id=sid, args=[sid])
            except: pass
    return redirect('/')

@app.route('/view_logs/<sid>')
def view_logs(sid):
    config = load_config()
    name = "Manager Server" if sid == "manager" else config.get(sid, {}).get('name', 'Inconnu')
    return render_template('logs.html', sid=sid, name=name)

@app.route('/raw_logs/<sid>')
def raw_logs(sid):
    log_path = SERVER_LOG if sid == "manager" else os.path.join(LOG_DIR, f"{sid}.log")
    if os.path.exists(log_path):
        with open(log_path, "r", encoding='utf-8', errors='replace') as f: return f.read()
    return "Aucun log disponible."

@app.route('/logs/manager')
def server_logs(): return redirect('/view_logs/manager')

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
    # Rechargement des jobs existants au démarrage
    cfg = load_config()
    for sid, s in cfg.items():
        if s.get('cron'):
            try:
                p = s['cron'].split()
                scheduler.add_job(run_script, 'cron', minute=p[0], hour=p[1], day=p[2], month=p[3], day_of_week=p[4], id=sid, args=[sid])
            except: pass
    app.run(debug=True, port=PORT, use_reloader=False)