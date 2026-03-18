import time
from pywinauto import keyboard

# PROCESSAMENTO eh o botao[2] na toolbar principal
MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar):
    """
    Etapa 4: PROCESSAMENTO -> CONSISTIR PRODUCAO
    Clica em Consistir e aguarda o processamento (pode levar 40min+).
    """
    api.log_progress(processo_id, "Iniciando Etapa 4: Consistir Producao")
    
    # 1. Navegar no menu: PROCESSAMENTO -> CONSISTIR PRODUCAO
    from steps.step1_check_open import click_menu
    click_menu(main_window, toolbar, MENU_PROCESSAMENTO_INDEX, "CONSISTIR PRODUCAO")
    
    api.log_progress(processo_id, "Dialog 'Consistencia da Producao' aberto.")
    time.sleep(2)
    
    # 2. Encontrar e clicar o botao "Consistir" no dialog
    consistir_btn = None
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if txt == 'Consistir' and 'Button' in cls:
                consistir_btn = ctrl
                break
        if consistir_btn:
            break
    
    if not consistir_btn:
        # Tentar achar por texto parcial
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if 'Consistir' in txt and 'Button' in cls:
                    consistir_btn = ctrl
                    break
            if consistir_btn:
                break
    
    if not consistir_btn:
        raise Exception("Botao 'Consistir' nao encontrado no dialog.")
    
    api.log_progress(processo_id, "Clicando em Consistir... Aguardando processamento (pode levar 40min+).")
    consistir_btn.click_input()
    
    # 3. Aguardar o processamento concluir
    # O dialog mostra "Historico do processamento" enquanto roda.
    # Quando termina, o botao Consistir volta a ficar habilitado,
    # ou aparece um dialog de conclusao.
    timeout = config["timeouts"].get("consistir", 7200)  # 2h default
    start_time = time.time()
    heartbeat_interval = 60  # Log a cada 1 minuto
    last_heartbeat = start_time
    
    api.log_progress(processo_id, f"Consistencia em andamento (timeout: {timeout}s = {timeout//3600}h)...")
    
    # Dar um tempo inicial pro processamento comecar
    time.sleep(10)
    
    while time.time() - start_time < timeout:
        time.sleep(5)
        elapsed = int(time.time() - start_time)
        
        # Heartbeat periodico
        if time.time() - last_heartbeat >= heartbeat_interval:
            minutes = elapsed // 60
            api.log_progress(processo_id, f"Consistencia em andamento ({minutes}min)...")
            last_heartbeat = time.time()
        
        # Verificar se apareceu um popup/dialog com OK
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and 'Button' in cls:
                    api.log_progress(processo_id, f"Consistencia concluida em {elapsed}s (~{elapsed//60}min)!")
                    ctrl.click_input()
                    time.sleep(1)
                    _fechar_dialog(app, api, processo_id)
                    return True
        
        # Verificar se o botao Consistir voltou a ficar habilitado
        # (indica que terminou sem popup de OK)
        try:
            if consistir_btn.is_enabled():
                # Checar se tem texto no historico
                api.log_progress(processo_id, f"Consistencia parece ter concluido em {elapsed}s (~{elapsed//60}min).")
                _fechar_dialog(app, api, processo_id)
                return True
        except Exception:
            pass
    
    raise TimeoutError(f"Consistencia nao concluiu em {timeout} segundos ({timeout//3600}h).")


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de Consistencia clicando em Fechar ou ESC."""
    api.log_progress(processo_id, "Fechando dialog de Consistencia...")
    time.sleep(1)
    
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and 'Button' in cls:
                ctrl.click_input()
                time.sleep(0.5)
                api.log_progress(processo_id, "Etapa 4 concluida: Consistencia finalizada com sucesso.")
                return
    
    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
    api.log_progress(processo_id, "Etapa 4 concluida: Consistencia finalizada com sucesso.")
