import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse

MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar):
    """
    Etapa 5: PROCESSAMENTO -> APURAR PREVIA
    Apura as AIHs consistidas. Pode levar bastante tempo.
    """
    api.log_progress(processo_id, "Iniciando Etapa 5: Apurar Previa")

    # 1. Navegar no menu: PROCESSAMENTO -> APURAR PREVIA (2o item, downs=1)
    from steps.step1_check_open import click_menu
    click_menu(main_window, toolbar, MENU_PROCESSAMENTO_INDEX, "APURAR PREVIA", downs=1)

    api.log_progress(processo_id, "Menu PROCESSAMENTO > APURAR PREVIA clicado.")
    time.sleep(2)

    # 2. Encontrar o dialog de apuracao
    apurar_dialog = None
    for w in app.windows():
        title = w.window_text()
        if 'Apur' in title and 'Pr' in title:
            apurar_dialog = w
            break

    if not apurar_dialog:
        apurar_dialog = app.top_window()

    api.log_progress(processo_id, f"Dialog encontrado: '{apurar_dialog.window_text()}'")

    # Debug: logar rect do dialog e descendants
    try:
        dlg_rect = apurar_dialog.rectangle()
        api.log_progress(processo_id,
            f"Dialog rect: ({dlg_rect.left},{dlg_rect.top},{dlg_rect.right},{dlg_rect.bottom})",
            level="DEBUG")
    except Exception:
        pass

    all_in_dialog = []
    for ctrl in apurar_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        try:
            rect = ctrl.rectangle()
            all_in_dialog.append(f"'{txt}' ({cls}) rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
        except Exception:
            all_in_dialog.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"Descendentes do dialog: {'; '.join(all_in_dialog)}", level="DEBUG")

    # 3. Encontrar o botao "Apurar"
    apurar_btn = None
    use_dialog_rect = False

    # Estrategia 1: buscar por texto "Apurar" nos descendants (com HWND)
    for ctrl in apurar_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        if 'Apurar' in txt and ('Button' in cls or 'Btn' in cls or 'Speed' in cls):
            apurar_btn = ctrl
            api.log_progress(processo_id, f"Botao Apurar encontrado: '{txt}' ({cls})")
            break

    # Estrategia 2: buscar TBitBtn desconhecido (excluindo Fechar/Imprimir)
    if not apurar_btn:
        known_texts = {'Fechar', '&Fechar', 'Imprimir', '&Imprimir'}
        for ctrl in apurar_dialog.descendants():
            cls = ctrl.class_name()
            txt = ctrl.window_text().strip()
            if cls in ('TBitBtn', 'TSpeedButton', 'TToolButton') and txt not in known_texts:
                apurar_btn = ctrl
                api.log_progress(processo_id, f"Candidato Apurar: '{txt}' ({cls})")
                break

    # Estrategia 3: Apurar eh TSpeedButton sem HWND.
    # Usar o RECT DO DIALOG — botoes ficam no rodape, Apurar eh o mais à esquerda.
    if not apurar_btn:
        use_dialog_rect = True
        api.log_progress(processo_id,
            "Apurar nao tem HWND. Usando rect do dialog para clicar no rodape.", level="DEBUG")

    def click_apurar():
        if apurar_btn:
            apurar_btn.click_input()
        else:
            from utils.window_utils import click_button_by_dialog_rect
            click_button_by_dialog_rect(apurar_dialog, api, processo_id, position="left")

    # === FASE 1: Primeiro clique — carrega dados ===
    api.log_progress(processo_id, "Fase 1: Clicando em Apurar para carregar dados...")
    click_apurar()

    # Aguardar carregamento (status "Preparado" ou lista populada)
    prep_timeout = config["timeouts"].get("apurar_preparar", 120)
    start_prep = time.time()
    preparado = False

    api.log_progress(processo_id, f"Aguardando carregamento (timeout: {prep_timeout}s)...")

    while time.time() - start_prep < prep_timeout:
        time.sleep(2)

        # Verificar popup OK (pode concluir direto sem fase 2)
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, "Apuracao concluida (popup OK na fase 1)!")
                    ctrl.click_input()
                    time.sleep(1)
                    _fechar_dialog(app, api, processo_id)
                    return True

        for ctrl in apurar_dialog.descendants():
            txt = ctrl.window_text()
            if 'Preparado' in txt or 'Selecione' in txt:
                preparado = True
                break
        if preparado:
            break

    if not preparado:
        api.log_progress(processo_id, "Status 'Preparado' nao detectado, tentando continuar...", level="WARNING")

    api.log_progress(processo_id, "Dados carregados.")
    time.sleep(1)

    # === FASE 2: Segundo clique — inicia apuracao ===
    api.log_progress(processo_id, "Fase 2: Clicando em Apurar para iniciar processamento...")
    click_apurar()

    # Aguardar conclusao
    timeout = config["timeouts"].get("apurar", 3600)
    start_time = time.time()
    heartbeat_interval = 60
    last_heartbeat = start_time
    processamento_iniciou = False

    api.log_progress(processo_id, f"Apuracao em andamento (timeout: {timeout}s = {timeout//60}min)...")
    time.sleep(10)

    while time.time() - start_time < timeout:
        time.sleep(5)
        elapsed = int(time.time() - start_time)

        if time.time() - last_heartbeat >= heartbeat_interval:
            minutes = elapsed // 60
            proc_info = _ler_status(apurar_dialog)
            api.log_progress(processo_id, f"Apuracao em andamento ({minutes}min)... {proc_info}")
            last_heartbeat = time.time()

        if not processamento_iniciou:
            for ctrl in apurar_dialog.descendants():
                txt = ctrl.window_text()
                if 'Processamento' in txt and '0:00:00' not in txt:
                    processamento_iniciou = True
                    api.log_progress(processo_id, "Processamento de apuracao iniciado.")
                    break

        # Verificar popup OK
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, f"Apuracao concluida em {elapsed}s (~{elapsed//60}min)!")
                    ctrl.click_input()
                    time.sleep(1)
                    _fechar_dialog(app, api, processo_id)
                    return True

        # Verificar se voltou a "Preparado"
        if processamento_iniciou:
            for ctrl in apurar_dialog.descendants():
                txt = ctrl.window_text()
                if 'Preparado' in txt:
                    api.log_progress(processo_id, f"Apuracao concluida em {elapsed}s (~{elapsed//60}min)!")
                    _fechar_dialog(app, api, processo_id)
                    return True

    raise TimeoutError(f"Apuracao nao concluiu em {timeout} segundos ({timeout//60}min).")


def _ler_status(dialog):
    """Le informacoes de status do dialog de apuracao."""
    info_parts = []
    for ctrl in dialog.descendants():
        txt = ctrl.window_text()
        if any(kw in txt for kw in ['Processamento', 'Total', 'Preparado', 'Processando']):
            info_parts.append(txt.strip())
    return ' | '.join(info_parts) if info_parts else ''


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de apuracao de forma robusta."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Apur', 'Pr'], 'Etapa 5')
