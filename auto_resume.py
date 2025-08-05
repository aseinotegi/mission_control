import os
import yaml
import requests
import time
from datetime import datetime
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

# --- LÓGICA DE CONFIGURACIÓN Y AUTENTICACIÓN ---
def load_config(config_path='resume_config.yaml'):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️  Cargando configuración...")
    try:
        with open(config_path, 'r', encoding='utf-8') as f: config = yaml.safe_load(f)
        print("✅ Configuración cargada.")
        return config
    except Exception as e:
        print(f"❌ ERROR CRÍTICO al cargar configuración: {e}"); return None

def get_token(email, api_key, login_url):
    print("🔑 Obteniendo token de autenticación...")
    try:
        response = requests.post(login_url, auth=(email, api_key))
        response.raise_for_status()
        print("✅ Token obtenido.")
        return response.json()["access_token"]
    except Exception as e:
        print(f"❌ Error al obtener el token: {e}"); return None

# <<<<<<< INICIO DEL CAMBIO >>>>>>>
# --- FUNCIÓN DE AYUDA PARA ESPERAR ESTADOS (AHORA CON RENOVACIÓN DE TOKEN) ---
def wait_for_awake_status(client, query, params, target_status, config, timeout=60, poll_interval=5):
    """
    Espera hasta que el robot alcance un 'target_status' específico.
    Si el token expira durante la espera, intenta renovarlo.
    """
    print(f"  -> ⏱️  Esperando a que el estado sea '{target_status}' (máx. {timeout} segundos)...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            result = client.execute(query, variable_values=params)
            current_status = result['currentRobotStatus']['awakeStatus']
            print(f"    -> Estado actual: {current_status}")
            if current_status == target_status:
                return True # ¡Éxito!
            time.sleep(poll_interval)
        except Exception as e:
            print(f"    -> Error durante la espera: {e}")
            # Si el error es de tipo '401 Unauthorized', renovamos el token aquí mismo
            if "401" in str(e):
                print("    -> Token expirado durante la espera. Intentando renovar...")
                new_token = get_token(config['credentials']['user'], config['credentials']['key'], config['api_endpoints']['login_url'])
                if new_token:
                    client.transport.headers["Authorization"] = f"Bearer {new_token}"
                    print("    -> Token renovado. Continuando la espera...")
                else:
                    print("    -> Fallo al renovar token. Abortando secuencia.")
                    return False # Abortamos si no podemos renovar el token
            
            time.sleep(poll_interval)
    
    print(f"    -> ❌ TIEMPO DE ESPERA AGOTADO. El estado no cambió a '{target_status}' a tiempo.")
    return False # Timeout alcanzado
# <<<<<<< FIN DEL CAMBIO >>>>>>>

# --- FUNCIÓN PRINCIPAL ---
def main():
    config = load_config()
    if not config: return

    # Cargar las queries y mutaciones
    try:
        with open("queries/get_mission_status.graphql", 'r', encoding='utf-8') as f: query_mission_status = gql(f.read())
        with open("queries/get_awake_status.graphql", 'r', encoding='utf-8') as f: query_awake_status = gql(f.read())
        with open("queries/awake_command.graphql", 'r', encoding='utf-8') as f: mutation_awake = gql(f.read())
        with open("queries/resume_mission.graphql", 'r', encoding='utf-8') as f: mutation_resume = gql(f.read())
    except FileNotFoundError as e:
        print(f"❌ ERROR CRÍTICO: No se encontró el archivo de query '{e.filename}'."); return

    # Obtener token y crear cliente
    token = get_token(config['credentials']['user'], config['credentials']['key'], config['api_endpoints']['login_url'])
    if not token: return
        
    transport = RequestsHTTPTransport(
        url=config['api_endpoints']['graphql_url'],
        headers={"Authorization": f"Bearer {token}"},
        verify=True,
        retries=3
    )
    client = Client(transport=transport)
    params = {"robotId": config['robot_info']['id']}
    
    recovery_sequence_active = False

    print("\n" + "="*50)
    print("🚀 INICIANDO SCRIPT DE REANUDACIÓN AUTOMÁTICA")
    print("="*50 + "\n")

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔎 Comprobando estado del robot...")
            
            result = client.execute(query_mission_status, variable_values=params)
            
            is_running = result.get('isMissionRunning')
            mission_exec = result.get('currentMissionExecution')
            status = mission_exec.get('status') if mission_exec else None

            if is_running and status == 'PAUSED' and not recovery_sequence_active:
                print(f"\n⚠️  ¡MISIÓN PAUSADA DETECTADA! Iniciando secuencia de recuperación robusta...")
                recovery_sequence_active = True

                print("\n--- PASO 1: Poner en reposo ---")
                client.execute(mutation_awake, variable_values={'robotId': params['robotId'], 'state': 'ASLEEP'})
                print("  -> Comando ASLEEP enviado.")
                
                # <<<<<<< INICIO DEL CAMBIO >>>>>>>
                # Pasamos el objeto 'config' a la función de espera
                if wait_for_awake_status(client, query_awake_status, params, "ASLEEP", config):
                    print("✅ Robot confirmado en estado ASLEEP.")

                    print("\n--- PASO 2: Despertar robot ---")
                    client.execute(mutation_awake, variable_values={'robotId': params['robotId'], 'state': 'AWAKE'})
                    print("  -> Comando AWAKE enviado.")
                    
                    if wait_for_awake_status(client, query_awake_status, params, "AWAKE", config):
                        print("✅ Robot confirmado en estado AWAKE.")

                        print("\n--- PASO 3: Reanudar misión ---")
                        print("  -> Enviando comando RESUME MISSION...")
                        resume_result = client.execute(mutation_resume, variable_values=params)
                        new_status = resume_result.get('resumeMissionExecution', {}).get('status')
                        print(f"✅ Secuencia completada. Nuevo estado esperado: {new_status}")
                    else:
                        print("❌ ERROR DE SECUENCIA: El robot no confirmó el estado AWAKE a tiempo.")
                else:
                    print("❌ ERROR DE SECUENCIA: El robot no confirmó el estado ASLEEP a tiempo.")
                # <<<<<<< FIN DEL CAMBIO >>>>>>>

                print("-" * 50)
            
            elif is_running and status == 'IN_PROGRESS' and recovery_sequence_active:
                print("✅ Misión reanudada con éxito. El sistema de recuperación vuelve a estar activo.")
                recovery_sequence_active = False

            elif not is_running and recovery_sequence_active:
                print("ℹ️ La misión ha finalizado. Reseteando el estado de recuperación.")
                recovery_sequence_active = False

            else:
                recovery_status = "en recuperación" if recovery_sequence_active else "normal"
                print(f"  -> Estado: {'Corriendo' if is_running else 'Parado'}, Status: {status}, Modo: {recovery_status}. No se requiere acción.")

        except Exception as e:
            print(f"  -> ❌ ERROR durante la comprobación: {e}")
            if "401" in str(e):
                print("  -> Error de autorización. Renovando token...")
                token = get_token(config['credentials']['user'], config['credentials']['key'], config['api_endpoints']['login_url'])
                if token:
                    client.transport.headers["Authorization"] = f"Bearer {token}"
        
        print(f" -> Próxima comprobación en {config['settings']['check_interval_seconds']} segundos...")
        time.sleep(config['settings']['check_interval_seconds'])

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Script detenido por el usuario.")