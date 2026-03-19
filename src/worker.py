"""
SQS Worker — Entry point para consumir mensagens da fila e executar o RPA SISAIH01.

Uso:
  python worker.py          # Modo AWS: consome SQS, baixa/sobe S3
  python worker.py --local  # Modo local: le de local_messages.json, pula S3
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time

import boto3
import yaml

from sisaih_automation import run_automation, load_config
from utils.api_client import ApiClient
from utils.s3_handler import S3Handler
from utils.ec2_manager import EC2Manager


class VisibilityExtender(threading.Thread):
    """Thread daemon que estende o visibility timeout da mensagem SQS periodicamente."""

    def __init__(self, sqs_client, queue_url, receipt_handle, heartbeat, extension):
        super().__init__(daemon=True)
        self.sqs_client = sqs_client
        self.queue_url = queue_url
        self.receipt_handle = receipt_handle
        self.heartbeat = heartbeat
        self.extension = extension
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(self.heartbeat)
            if self._stop_event.is_set():
                break
            try:
                self.sqs_client.change_message_visibility(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=self.receipt_handle,
                    VisibilityTimeout=self.extension,
                )
                print(f"[VisibilityExtender] Visibility estendida em +{self.extension}s")
            except Exception as e:
                print(f"[VisibilityExtender] Erro ao estender visibility: {e}")
                break

    def stop(self):
        self._stop_event.set()


class SQSWorker:
    def __init__(self, config, is_local_mode=False):
        self.config = config
        self.is_local_mode = is_local_mode
        self._running = True
        self._processing = False

        aws_cfg = config.get('aws', {})
        worker_cfg = config.get('worker', {})

        self.queue_url = aws_cfg.get('sqs_queue_url', '')
        self.max_empty_polls = worker_cfg.get('max_empty_polls', 3)
        self.visibility_heartbeat = worker_cfg.get('visibility_heartbeat', 300)
        self.visibility_extension = worker_cfg.get('visibility_extension', 900)

        self.ec2 = EC2Manager(config)

        if not is_local_mode:
            sqs_kwargs = {'region_name': aws_cfg.get('region', 'sa-east-1')}
            sqs_endpoint = aws_cfg.get('sqs_endpoint_url')
            if sqs_endpoint:
                sqs_kwargs['endpoint_url'] = sqs_endpoint
                sqs_kwargs['aws_access_key_id'] = aws_cfg.get('access_key_id', 'test')
                sqs_kwargs['aws_secret_access_key'] = aws_cfg.get('secret_access_key', 'test')
            self.sqs = boto3.client('sqs', **sqs_kwargs)
            self.s3 = S3Handler(config)
        else:
            self.sqs = None
            self.s3 = None

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n[Worker] Sinal {sig_name} recebido. Aguardando mensagem atual terminar...")
        self._running = False

    def start(self):
        """Loop principal do worker."""
        print("[Worker] Iniciando SQS Worker...")
        if self.is_local_mode:
            self._run_local()
        else:
            self._run_sqs()
        print("[Worker] Worker encerrado.")

    def _run_local(self):
        """Modo local: le mensagens de local_messages.json."""
        messages_path = os.path.join(os.path.dirname(__file__), 'local_messages.json')
        if not os.path.exists(messages_path):
            print(f"[Worker] Arquivo nao encontrado: {messages_path}")
            return

        with open(messages_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        if not isinstance(messages, list):
            messages = [messages]

        for i, msg in enumerate(messages):
            if not self._running:
                break
            print(f"\n[Worker] Processando mensagem local {i + 1}/{len(messages)}")
            self._process_message_local(msg)

    def _run_sqs(self):
        """Modo AWS: long-polling SQS em loop."""
        empty_polls = 0
        print(f"[Worker] Consumindo fila: {self.queue_url}")

        while self._running:
            try:
                response = self.sqs.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    MessageAttributeNames=['All'],
                )
            except Exception as e:
                print(f"[Worker] Erro ao receber mensagem SQS: {e}")
                time.sleep(5)
                continue

            messages = response.get('Messages', [])

            if not messages:
                empty_polls += 1
                print(f"[Worker] Poll vazio ({empty_polls}/{self.max_empty_polls})")
                if empty_polls >= self.max_empty_polls:
                    print(f"[Worker] {self.max_empty_polls} polls vazios consecutivos. Agendando shutdown...")
                    self.ec2.schedule_shutdown()
                    self._running = False
                continue

            # Nova mensagem — resetar contador e cancelar shutdown se pendente
            empty_polls = 0
            if self.ec2.shutdown_pending:
                print("[Worker] Nova mensagem! Cancelando shutdown agendado.")
                self.ec2.cancel_shutdown()

            msg = messages[0]
            self._process_message_sqs(msg)

    def _process_message_sqs(self, sqs_message):
        """Processa uma mensagem SQS: download S3 -> RPA -> upload S3 -> callback -> delete."""
        receipt_handle = sqs_message['ReceiptHandle']
        self._processing = True
        extender = None

        try:
            body = json.loads(sqs_message['Body'])
            processo_id = body.get('processo_id', 'unknown')
            s3_input_key = body.get('s3_input_key', '')
            hospital_data = body.get('hospital_data', {})
            callback_url = body.get('callback_url')

            print(f"\n[Worker] === Processando processo {processo_id} ===")

            api = ApiClient(self.config, is_local_mode=False, callback_url=callback_url)
            api.log_progress(processo_id, "Mensagem SQS recebida. Iniciando processamento.")

            # Iniciar VisibilityExtender
            extender = VisibilityExtender(
                self.sqs, self.queue_url, receipt_handle,
                self.visibility_heartbeat, self.visibility_extension,
            )
            extender.start()

            # 1. Download do S3
            local_input_dir = self.config.get('paths', {}).get('local_input_dir', r'C:\SIHD_CONVERTER\input')
            filename = os.path.basename(s3_input_key)
            local_path = os.path.join(local_input_dir, filename)

            api.log_progress(processo_id, f"Baixando {s3_input_key} do S3...")
            self.s3.download_file(s3_input_key, local_path)
            api.log_progress(processo_id, f"Arquivo baixado: {local_path}")

            # 2. Executar automacao (step1 conecta ao SISAIH01 existente ou abre novo)
            result = run_automation(processo_id, local_path, hospital_data, is_local_mode=False, config=self.config)

            # 4. Upload resultado para S3
            export_path = result.get('export_path', '')
            s3_output_key = ''
            if export_path and os.path.exists(export_path):
                s3_output_key = f"output/{processo_id}/{os.path.basename(export_path)}"
                api.log_progress(processo_id, f"Enviando {export_path} para S3...")
                self.s3.upload_file(export_path, s3_output_key)
                api.log_progress(processo_id, f"Upload concluido: {s3_output_key}")

            # 5. Callback para a API
            api.notify_completion(processo_id, status="COMPLETED", s3_output_key=s3_output_key)

            # 6. Deletar mensagem SQS (sucesso)
            self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)
            print(f"[Worker] === Processo {processo_id} concluido com sucesso ===\n")

        except Exception as e:
            print(f"[Worker] ERRO ao processar mensagem: {e}")
            try:
                body = json.loads(sqs_message['Body'])
                processo_id = body.get('processo_id', 'unknown')
                callback_url = body.get('callback_url')
                api = ApiClient(self.config, is_local_mode=False, callback_url=callback_url)
                api.notify_completion(processo_id, status="FAILED", error_message=str(e))
            except Exception:
                pass
            # NAO deleta a mensagem — ela volta para a fila apos visibility timeout
            # e pode ser movida para DLQ pelo SQS

        finally:
            if extender:
                extender.stop()
            self._processing = False

    def _process_message_local(self, msg):
        """Processa uma mensagem no modo local (sem S3/SQS)."""
        processo_id = msg.get('processo_id', 'local_test')
        file_path = msg.get('file_path', '')
        hospital_data = msg.get('hospital_data', {})

        print(f"[Worker] Processo: {processo_id}, Arquivo: {file_path}")

        self._kill_sisaih()

        try:
            result = run_automation(processo_id, file_path, hospital_data, is_local_mode=True, config=self.config)
            status = result.get('status', 'UNKNOWN') if result else 'FAILED'
            print(f"[Worker] Resultado: {status}")
            if result and result.get('export_path'):
                print(f"[Worker] Export: {result['export_path']}")
        except Exception as e:
            print(f"[Worker] ERRO: {e}")

    def _kill_sisaih(self):
        """Mata o processo SISAIH01 se estiver rodando (garante estado limpo para retry)."""
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'SISAIH01.EXE'],
                    capture_output=True, check=False,
                )
            print("[Worker] SISAIH01 encerrado (ou nao estava rodando).")
        except Exception:
            pass
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="SQS Worker - SIHD Converter")
    parser.add_argument('--local', action='store_true', help='Modo local: le de local_messages.json')
    parser.add_argument('--config', default='config.yaml', help='Arquivo de config (default: config.yaml)')
    args = parser.parse_args()

    config = load_config(args.config)
    worker = SQSWorker(config, is_local_mode=args.local)
    worker.start()


if __name__ == '__main__':
    main()
