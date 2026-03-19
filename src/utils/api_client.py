import time
import requests
from datetime import datetime


class ApiClient:
    def __init__(self, config, is_local_mode=False, callback_url=None):
        api_cfg = config.get('api', {})
        self.base_url = api_cfg.get('base_url', 'http://localhost:3333')
        self.timeout = api_cfg.get('timeout', 15)
        self.max_retries = api_cfg.get('max_retries', 3)
        self.api_key = api_cfg.get('api_key', '')
        self.is_local_mode = is_local_mode
        self.callback_url = callback_url

    def _post_with_retry(self, url, payload):
        """POST com backoff exponencial (1s, 2s, 4s...)."""
        headers = {}
        if self.api_key:
            headers['X-API-Key'] = self.api_key

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    print(f"[RETRY] Tentativa {attempt + 1} falhou: {e}. Aguardando {wait}s...")
                    time.sleep(wait)
        print(f"[ERROR] Todas as {self.max_retries} tentativas falharam: {last_error}")
        return None

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
                self._post_with_retry(url, payload)
            except Exception as e:
                print(f"[ERROR] Falha ao enviar log para a API: {e}")

    def notify_completion(self, processo_id, status, error_message=None, s3_output_key=None):
        """Notifica o webhook final dizendo que o RPA terminou (sucesso ou falha)."""
        print(f"=== Processo {processo_id} Finalizado com Status: {status} ===")
        if error_message:
            print(f"Erro: {error_message}")

        if not self.is_local_mode and processo_id:
            try:
                url = self.callback_url or f"{self.base_url}/processo/{processo_id}/conversion-callback"
                payload = {
                    "status": status,
                    "message": error_message
                }
                if s3_output_key:
                    payload["s3_output_key"] = s3_output_key
                self._post_with_retry(url, payload)
            except Exception as e:
                print(f"[ERROR] Falha ao notificar callback da API: {e}")
