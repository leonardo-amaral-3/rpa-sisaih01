import os
import requests
import json
from datetime import datetime

class ApiClient:
    def __init__(self, config, is_local_mode=False):
        self.base_url = config.get('api', {}).get('base_url', 'http://localhost:3333')
        self.is_local_mode = is_local_mode

    def log_progress(self, processo_id, message, level="INFO"):
        """Envia ou simula o envio de um log de progresso."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] Processo {processo_id} - {message}"
        print(log_entry)

        if not self.is_local_mode and processo_id:
            try:
                url = f"{self.base_url}/processo/{processo_id}/rpa-logs"
                payload = {
                    "level": level,
                    "message": message,
                    "timestamp": timestamp
                }
                # Comentar/descomentar na fase 2
                # requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"[ERROR] Falha ao enviar log para a API: {e}")

    def notify_completion(self, processo_id, status, error_message=None):
        """Notifica o webhook final dizendo que o RPA terminou (sucesso ou falha)."""
        print(f"=== Processo {processo_id} Finalizado com Status: {status} ===")
        if error_message:
            print(f"Erro: {error_message}")

        if not self.is_local_mode and processo_id:
            try:
                url = f"{self.base_url}/processo/{processo_id}/conversion-callback"
                payload = {
                    "status": status,
                    "message": error_message
                }
                # Comentar/descomentar na fase 2
                # requests.post(url, json=payload, timeout=10)
            except Exception as e:
                print(f"[ERROR] Falha ao notificar callback da API: {e}")
