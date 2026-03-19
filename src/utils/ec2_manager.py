import os
import subprocess
import platform


class EC2Manager:
    def __init__(self, config):
        worker_cfg = config.get('worker', {})
        self.default_delay = worker_cfg.get('shutdown_delay', 120)
        self.shutdown_pending = False
        self._is_windows = platform.system() == 'Windows'

    def schedule_shutdown(self, delay=None):
        """Agenda shutdown da maquina. Windows: shutdown /s /t N. Linux: mock/log."""
        if self.shutdown_pending:
            return
        delay = delay or self.default_delay
        if self._is_windows:
            subprocess.run(['shutdown', '/s', '/t', str(delay)], check=False)
        else:
            print(f"[EC2Manager] Mock shutdown agendado em {delay}s (ambiente Linux/dev)")
        self.shutdown_pending = True

    def cancel_shutdown(self):
        """Cancela shutdown agendado. Idempotente — seguro chamar mesmo sem shutdown pendente."""
        if self._is_windows:
            subprocess.run(['shutdown', '/a'], check=False)
        else:
            print("[EC2Manager] Mock shutdown cancelado (ambiente Linux/dev)")
        self.shutdown_pending = False
