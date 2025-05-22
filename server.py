import subprocess
import time
import json
import os
import threading
import sys

# Configuration
CONFIG_FILE = 'config.json'
CHECK_INTERVAL = 30  # Intervalle de vérification en secondes

chemin_absolu = os.path.abspath(__file__)
os.chdir("/".join(chemin_absolu.split(os.path.sep)[:-1]))

latest_commit_sha = None
restart = False

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def get_user_input(prompt, default=None):
    value = input(prompt)
    return value if value else default

def clone_or_pull_repo(repo_url, local_repo_path, github_token):
    if not os.path.exists(local_repo_path):
        subprocess.run(['git', 'clone', f'https://{github_token}@{repo_url.split("://")[1]}', local_repo_path])
    else:
        subprocess.run(['git', '-C', local_repo_path, 'pull'])

def get_latest_commit_sha(local_repo_path):
    if latest_commit_sha is None:
        result = subprocess.run(['git', 'log', '--pretty=format:\'%H\'', '-1'], capture_output=True, text=True)
        return result.stdout.strip().replace("'", "")
    else:
        return latest_commit_sha

def get_remote_latest_commit_sha(repo_url, github_token):
    result = subprocess.run(['git', 'ls-remote', f'https://{github_token}@{repo_url.split("://")[1]}', 'HEAD'], capture_output=True, text=True)
    return result.stdout.split()[0]

def run_commands(commands, local_repo_path, stop_event):
    os.chdir(local_repo_path)
    processes = []
    try:
        retry = 0
        while not stop_event.is_set() and retry < 10:
            for command in commands:
                print(f"Exécution de la commande : {command}")
                process = subprocess.Popen(command.split())
                processes.append(process)
                while process.poll() is None:  # Vérifier si le processus est toujours en cours
                    if stop_event.is_set():
                        process.terminate()  # Terminer le processus si l'événement est déclenché
                        process.wait()  # Attendre que le processus se termine
                        return
                    time.sleep(1)  # Attendre un peu avant de vérifier à nouveau
                process.wait()  # Attendre que le processus se termine

            retry += 1
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:  # Vérifier si le processus est toujours en cours
                process.terminate()  # Terminer le processus
            process.wait()  # Attendre que le processus se termine

def check_for_updates(repo_url, local_repo_path, github_token, stop_event):
    global latest_commit_sha
    last_commit_sha = get_latest_commit_sha(local_repo_path)
    while not stop_event.is_set():
        time.sleep(CHECK_INTERVAL)
        print('Checkup mise à jour . . .')
        current_commit_sha = get_remote_latest_commit_sha(repo_url, github_token)
        print(current_commit_sha, last_commit_sha)
        if current_commit_sha != last_commit_sha:
            print("Modification détectée, mise à jour en cours...")
            stop_event.set()  # Arrêter les commandes en cours
            break

def restart_script():
    """Redémarre le script en fonction du système d'exploitation et de l'environnement."""
    os.chdir("./..")
    python = sys.executable
    script = os.path.abspath(__file__)
    if os.name == 'nt':  # Windows
        os.execl(python, python, script)
    else:  # Unix (Linux, macOS)
        os.execl(python, python, script)

def main():
    config = load_config()

    if not config:
        config['github_token'] = get_user_input("Entrez votre token GitHub : ")
        config['repo_url'] = get_user_input("Entrez l'URL de votre dépôt GitHub (ex: https://github.com/propriétaire/nom_du_dépôt) : ")
        config['local_repo_path'] = get_user_input("Entrez le chemin local de votre dépôt : ")
        config['commands_to_run'] = get_user_input("Entrez les commandes à exécuter, séparées par des virgules : ").split(',')
        save_config(config)
    else:
        print("Configuration chargée depuis le fichier.")

    clone_or_pull_repo(config['repo_url'], config['local_repo_path'], config['github_token'])

    stop_event = threading.Event()

    # Démarrer les threads pour exécuter les commandes et vérifier les mises à jour
    commands_thread = threading.Thread(target=run_commands, args=(config['commands_to_run'], config['local_repo_path'], stop_event))
    update_thread = threading.Thread(target=check_for_updates, args=(config['repo_url'], config['local_repo_path'], config['github_token'], stop_event))

    commands_thread.start()
    update_thread.start()

    # Attendre que le thread de vérification des mises à jour se termine
    update_thread.join()

    if stop_event.is_set():
        commands_thread.join()  # Attendre que le thread des commandes se termine
        stop_event.clear()  # Réinitialiser l'événement pour la prochaine itération
        restart_script()  # Redémarrer le script

if __name__ == '__main__':
    main()
