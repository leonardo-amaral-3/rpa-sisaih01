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

    # 3. Encontrar o botao "Consistir"
    # No SISAIH01 o botao pode estar FORA do dialog interno (em um painel pai),
    # entao buscamos em TODAS as janelas do app.
    consistir_btn = None
    all_bitbtns = []

    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if cls == 'TBitBtn':
                all_bitbtns.append(f"'{txt}' ({cls}) pos={ctrl.rectangle()}")
            if 'Consistir' in txt and ('Button' in cls or 'Btn' in cls):
                consistir_btn = ctrl
                break
        if consistir_btn:
            break

    api.log_progress(processo_id, f"TBitBtns encontrados: {'; '.join(all_bitbtns)}", level="DEBUG")

    if not consistir_btn:
        raise Exception(f"Botao 'Consistir' nao encontrado. TBitBtns: {'; '.join(all_bitbtns)}")

    # === FASE 1: Primeiro clique — Abre banco de dados e carrega AIHs ===
    api.log_progress(processo_id, "Fase 1: Clicando em Consistir para abrir banco e carregar AIHs...")
    consistir_btn.click_input()

    # Aguardar o banco abrir e as AIHs carregarem (status "Preparado")
    # Detectamos pelo texto "Preparado" em algum controle, ou pela lista de AIHs populada
    prep_timeout = config["timeouts"].get("consistir_preparar", 120)  # 2min pra carregar
    start_prep = time.time()

    api.log_progress(processo_id, f"Aguardando banco de dados carregar (timeout: {prep_timeout}s)...")

    preparado = False
    while time.time() - start_prep < prep_timeout:
        time.sleep(2)
        for ctrl in consist_dialog.descendants():
            txt = ctrl.window_text()
            # "Preparado" aparece no status bar quando as AIHs foram carregadas
            if 'Preparado' in txt:
                preparado = True
                break
            # Tambem verificar se o historico mostra "Selecione AIH"
            if 'Selecione AIH' in txt:
                preparado = True
                break
        if preparado:
            break

    if not preparado:
        api.log_progress(processo_id, "Status 'Preparado' nao detectado, tentando continuar mesmo assim...", level="WARNING")

    api.log_progress(processo_id, "Banco carregado. AIHs prontas para processamento.")
    time.sleep(1)

    # === FASE 2: Segundo clique — Inicia processamento das AIHs ===
    api.log_progress(processo_id, "Fase 2: Clicando em Consistir novamente para iniciar processamento das AIHs...")
    consistir_btn.click_input()

    # 4. Aguardar o processamento concluir (pode levar 40min+)
    timeout = config["timeouts"].get("consistir", 7200)  # 2h default
    start_time = time.time()
    heartbeat_interval = 60  # Log a cada 1 minuto
    last_heartbeat = start_time
    processamento_iniciou = False

    api.log_progress(processo_id, f"Consistencia em andamento (timeout: {timeout}s = {timeout//3600}h)...")

    # Dar tempo inicial pro processamento comecar
    time.sleep(10)

    while time.time() - start_time < timeout:
        time.sleep(5)
        elapsed = int(time.time() - start_time)

        # Heartbeat periodico
        if time.time() - last_heartbeat >= heartbeat_interval:
            minutes = elapsed // 60
            # Tentar ler o tempo de processamento do dialog
            proc_info = _ler_status_processamento(consist_dialog)
            api.log_progress(processo_id, f"Consistencia em andamento ({minutes}min)... {proc_info}")
            last_heartbeat = time.time()

        # Detectar que o processamento iniciou (tempo > 0:00:00)
        if not processamento_iniciou:
            for ctrl in consist_dialog.descendants():
                txt = ctrl.window_text()
                if 'Processamento' in txt and '0:00:00' not in txt:
                    processamento_iniciou = True
                    api.log_progress(processo_id, "Processamento de AIHs iniciado.")
                    break

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

        # Verificar se o status voltou a "Preparado" (indica que terminou)
        if processamento_iniciou:
            for ctrl in consist_dialog.descendants():
                txt = ctrl.window_text()
                if 'Preparado' in txt:
                    api.log_progress(processo_id, f"Consistencia concluida em {elapsed}s (~{elapsed//60}min)!")
                    _fechar_dialog(app, api, processo_id)
                    return True

    raise TimeoutError(f"Consistencia nao concluiu em {timeout} segundos ({timeout//3600}h).")


def _ler_status_processamento(dialog):
    """Le informacoes de status do dialog (tempo de processamento, total, etc)."""
    info_parts = []
    for ctrl in dialog.descendants():
        txt = ctrl.window_text()
        if any(kw in txt for kw in ['Processamento', 'Total', 'Preparado', 'Processando']):
            info_parts.append(txt.strip())
    return ' | '.join(info_parts) if info_parts else ''


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
