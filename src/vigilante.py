import threading
import time

class Vigilante(threading.Thread):
    """
    Thread que roda em background (Daemon) a cada 5 segundos buscando
    janelas de erro ou popups de confirmação surpresa que a aplicacao
    SISAIH01 possa disparar, atrapalhando a execucao principal.
    """
    def __init__(self, app, api, processo_id, interval=5):
        super().__init__(daemon=True) # Termina silenciosamente qdo a Main Thread acaba
        self.app = app
        self.api = api
        self.processo_id = processo_id
        self.interval = interval
        self.running = False
        self.error_detected = None

    def start_watch(self):
        self.running = True
        self.start()

    def stop_watch(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                # Procura por todas as janelas que o 'app' é dono
                # Filtra por titulos como 'Atenção', 'Erro', 'Aviso'
                windows = self.app.windows()
                for w in windows:
                    title = w.window_text()
                    if title and title in ["Atenção", "Erro", "Aviso", "Mensagem do Sistema"]:
                        # Tenta pegar o texto descritivo do popup
                        try:
                            # A maioria dos Message Boxes padrao do windows usam Static pra label de erro
                            msg_ctrl = w.child_window(class_name="Static")
                            msg = msg_ctrl.window_text()
                        except Exception:
                            msg = "<Texto de erro não encontrado>"
                        
                        full_err = f"Pop-up interceptado pelo Vigilante! Título: '{title}', Mensagem: '{msg}'"
                        self.error_detected = full_err
                        
                        self.api.log_progress(self.processo_id, full_err, level="ERROR")
                        # Em producao podemos printar tela, ou clicar em OK pra descartar e falhar graciosamente
                        
                        self.running = False # Encerra o vigilante pq ja pegou
                        break
            except Exception:
                pass # Ignorar excecoes do watcher pra nao crashar a Main Thread
            
            time.sleep(self.interval)
