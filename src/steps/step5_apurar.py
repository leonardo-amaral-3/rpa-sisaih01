import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse

MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar):
    """
    Etapa 5: PROCESSAMENTO -> APURAR PREVIA
    Apura as AIHs consistidas.
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

    # Debug: listar descendants
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

    # Estrategia 1: texto "Apurar" nos descendants
    for ctrl in apurar_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        if 'Apurar' in txt and ('Button' in cls or 'Btn' in cls or 'Speed' in cls):
            apurar_btn = ctrl
            api.log_progress(processo_id, f"Botao Apurar encontrado: '{txt}' ({cls})")
            break

    # Estrategia 2: TBitBtn desconhecido
    if not apurar_btn:
        known_texts = {'Fechar', '&Fechar', 'Imprimir', '&Imprimir'}
        for ctrl in apurar_dialog.descendants():
            cls = ctrl.class_name()
            txt = ctrl.window_text().strip()
            if cls in ('TBitBtn', 'TSpeedButton', 'TToolButton') and txt not in known_texts:
                apurar_btn = ctrl
                api.log_progress(processo_id, f"Candidato Apurar: '{txt}' ({cls})")
                break

    # Estrategia 3: dialog rect (fallback)
    if not apurar_btn:
        api.log_progress(processo_id,
            "Apurar nao tem HWND. Usando rect do dialog.", level="DEBUG")

    def click_apurar():
        if apurar_btn:
            apurar_btn.click_input()
        else:
            from utils.window_utils import click_button_by_dialog_rect
            click_button_by_dialog_rect(apurar_dialog, api, processo_id, position="left")

    # 4. Clicar em Apurar (1 clique inicia todo o processamento)
    api.log_progress(processo_id, "Clicando em Apurar...")
    click_apurar()

    # 5. Monitorar conclusao
    timeout = config["timeouts"].get("apurar", 3600)
    start_time = time.time()
    heartbeat_interval = 30
    last_heartbeat = start_time
    ja_clicou_segunda_vez = False

    api.log_progress(processo_id, f"Apuracao em andamento (timeout: {timeout}s)...")

    while time.time() - start_time < timeout:
        time.sleep(3)
        elapsed = int(time.time() - start_time)

        # Heartbeat
        if time.time() - last_heartbeat >= heartbeat_interval:
            proc_info = _ler_status(apurar_dialog)
            api.log_progress(processo_id, f"Apuracao em andamento ({elapsed}s)... {proc_info}")
            last_heartbeat = time.time()

        # Verificar popup OK
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, f"Apuracao concluida em {elapsed}s!")
                    ctrl.click_input()
                    time.sleep(1)
                    _fechar_dialog(app, api, processo_id)
                    return True

        # Verificar "Fim" no historico
        for ctrl in apurar_dialog.descendants():
            txt = ctrl.window_text()
            if not txt:
                continue
            if 'Fim' in txt and ('Inicio' in txt or 'Total' in txt or 'Abrindo' in txt):
                api.log_progress(processo_id, f"Apuracao concluida em {elapsed}s! (detectado 'Fim')")
                _fechar_dialog(app, api, processo_id)
                return True

        # Se "Preparado"/"Selecione" aparecer sem "Fim", dados carregaram mas nao processou
        if not ja_clicou_segunda_vez and elapsed > 10:
            for ctrl in apurar_dialog.descendants():
                txt = ctrl.window_text()
                if 'Preparado' in txt or 'Selecione' in txt:
                    api.log_progress(processo_id, "Dados carregados. Clicando novamente para processar...")
                    click_apurar()
                    ja_clicou_segunda_vez = True
                    break

    raise TimeoutError(f"Apuracao nao concluiu em {timeout} segundos.")


def _ler_status(dialog):
    """Le informacoes de status do dialog de apuracao."""
    info_parts = []
    for ctrl in dialog.descendants():
        txt = ctrl.window_text()
        if any(kw in txt for kw in ['Processamento', 'Total', 'Preparado', 'Processando', 'Fim']):
            info_parts.append(txt.strip())
    return ' | '.join(info_parts) if info_parts else ''


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de apuracao de forma robusta."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Apur', 'Pr'], 'Etapa 5')
