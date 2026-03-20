import platform
import subprocess
import threading

import boto3
import requests


class EC2Manager:
    def __init__(self, config):
        worker_cfg = config.get('worker', {})
        aws_cfg = config.get('aws', {})
        self.default_delay = worker_cfg.get('shutdown_delay', 120)
        self.shutdown_pending = False
        self._is_windows = platform.system() == 'Windows'
        self._timer = None
        self._region = aws_cfg.get('region', 'us-east-1')

    def schedule_shutdown(self, delay=None):
        """Agenda terminate da instância EC2 após delay segundos.

        Usa threading.Timer para manter o grace period: se chegar mensagem nova
        antes do timer disparar, cancel_shutdown() cancela o terminate.
        """
        if self.shutdown_pending:
            return
        delay = delay or self.default_delay
        self._timer = threading.Timer(delay, self._do_terminate)
        # Em dev (Linux), daemon=True permite que Ctrl+C encerre o processo imediatamente.
        # Em prod (Windows), daemon=False mantém o processo vivo até o terminate disparar.
        self._timer.daemon = not self._is_windows
        self._timer.start()
        self.shutdown_pending = True
        print(f"[EC2Manager] Terminate agendado em {delay}s")

    def cancel_shutdown(self):
        """Cancela terminate agendado. Idempotente — seguro chamar mesmo sem terminate pendente."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.shutdown_pending = False
        print("[EC2Manager] Terminate cancelado")

    def _get_instance_id(self):
        """Obtém o Instance ID via EC2 Instance Metadata Service (IMDSv2)."""
        try:
            token_resp = requests.put(
                'http://169.254.169.254/latest/api/token',
                headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
                timeout=2,
            )
            token = token_resp.text
            resp = requests.get(
                'http://169.254.169.254/latest/meta-data/instance-id',
                headers={'X-aws-ec2-metadata-token': token},
                timeout=2,
            )
            return resp.text
        except Exception as e:
            print(f"[EC2Manager] Erro ao obter instance ID: {e}")
            return None

    def _do_terminate(self):
        """Termina a própria instância EC2. Em Linux/dev, apenas loga."""
        if not self._is_windows:
            print("[EC2Manager] Mock terminate (ambiente Linux/dev)")
            return

        instance_id = self._get_instance_id()
        if not instance_id:
            print("[EC2Manager] Não conseguiu instance ID. Fallback: shutdown /s /t 0")
            subprocess.run(['shutdown', '/s', '/t', '0'], check=False)
            return

        print(f"[EC2Manager] Terminando instância {instance_id}...")
        try:
            ec2 = boto3.client('ec2', region_name=self._region)
            ec2.terminate_instances(InstanceIds=[instance_id])
            print(f"[EC2Manager] Instância {instance_id} terminada")
        except Exception as e:
            print(f"[EC2Manager] Erro ao terminar: {e}. Fallback: shutdown /s /t 0")
            subprocess.run(['shutdown', '/s', '/t', '0'], check=False)
