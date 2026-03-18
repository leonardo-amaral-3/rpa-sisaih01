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

    # 2. Encontrar o dialog de consistencia
    consist_dialog = None
    for w in app.windows():
        title = w.window_text()
        if 'Consist' in title and 'Produ' in title:
            consist_dialog = w
            break

    if not consist_dialog:
        consist_dialog = app.top_window()

    # Debug: listar controles do dialog
    all_controls = []
    for ctrl in consist_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        all_controls.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"Controles no dialog: {'; '.join(all_controls)}", level="DEBUG")

    # 3. Encontrar o botao "Consistir" com fallback progressivo
    consistir_btn = None

    # Estrategia 1: texto exato + classe de botao
    for ctrl in consist_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        if 'Consistir' in txt and ('Button' in cls or 'Btn' in cls):
            consistir_btn = ctrl
            break

    # Estrategia 2: TBitBtn no dialog (texto pode estar vazio)
    if not consistir_btn:
        for ctrl in consist_dialog.descendants():
            if ctrl.class_name() == 'TBitBtn':
                consistir_btn = ctrl
                api.log_progress(processo_id, f"Botao encontrado via classe TBitBtn (texto: '{ctrl.window_text()}')")
                break

    # Estrategia 3: qualquer controle com texto "Consistir"
    if not consistir_btn:
        for ctrl in consist_dialog.descendants():
            txt = ctrl.window_text()
            if 'Consistir' in txt and ctrl.class_name() not in ('TLabel', 'TStaticText'):
                consistir_btn = ctrl
                api.log_progress(processo_id, f"Botao encontrado por texto em {ctrl.class_name()}")
                break

    if not consistir_btn:
        raise Exception(f"Botao 'Consistir' nao encontrado. Controles: {'; '.join(all_controls)}")
    
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
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
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
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                ctrl.click_input()
                time.sleep(0.5)
                api.log_progress(processo_id, "Etapa 4 concluida: Consistencia finalizada com sucesso.")
                return
    
    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
    api.log_progress(processo_id, "Etapa 4 concluida: Consistencia finalizada com sucesso.")
