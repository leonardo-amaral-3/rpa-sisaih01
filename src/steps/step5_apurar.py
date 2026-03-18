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

    # Debug: listar controles do dialog
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
    # Layout esperado: [Apurar] [Imprimir] [Fechar]
    # Apurar pode ser TSpeedButton (sem HWND) — mesma estrategia do step4
    apurar_btn = None
    apurar_coords = None

    # Estrategia 1: buscar por texto "Apurar" nos descendants
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

    # Estrategia 3: coordenada relativa ao botao Fechar (TBitBtn com HWND)
    # Layout: [Apurar] [Imprimir] [Fechar] — Apurar fica à esquerda
    if not apurar_btn:
        api.log_progress(processo_id,
            "Apurar nao tem HWND (provavel TSpeedButton). Calculando coordenada...", level="DEBUG")

        fechar_btn = None
        for ctrl in apurar_dialog.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                fechar_btn = ctrl
                break

        if fechar_btn:
            fechar_rect = fechar_btn.rectangle()
            center_y = (fechar_rect.top + fechar_rect.bottom) // 2
            btn_width = fechar_rect.right - fechar_rect.left

            click_x = fechar_rect.left - btn_width * 2 - 10 + btn_width // 2

            for ctrl in apurar_dialog.descendants():
                if ctrl.class_name() == 'TPanel':
                    p_rect = ctrl.rectangle()
                    if p_rect.top <= fechar_rect.top and p_rect.bottom >= fechar_rect.bottom:
                        if click_x < p_rect.left + 10:
                            click_x = p_rect.left + btn_width // 2 + 5
                        break

            apurar_coords = (click_x, center_y)
            api.log_progress(processo_id,
                f"Ref: Fechar rect=({fechar_rect.left},{fechar_rect.top},{fechar_rect.right},{fechar_rect.bottom}), "
                f"Coordenada Apurar: ({click_x}, {center_y})")
        else:
            api.log_progress(processo_id, "Botao Fechar tambem nao tem HWND, usando TPanel como referencia...", level="DEBUG")

    # Estrategia 4: TODOS os botoes sao TSpeedButton sem HWND (Apurar, Imprimir, Fechar)
    # Usar o TPanel (barra de botoes) como referencia de coordenada.
    # Identificamos a barra de botoes como o TPanel mais estreito (altura ~40-50px)
    # que contem o TProgressBar.
    # Layout: [Apurar] [Imprimir] [Fechar] dentro do painel
    if not apurar_btn and not apurar_coords:
        api.log_progress(processo_id, "Estrategia 4: usando TPanel como referencia...", level="DEBUG")

        # Encontrar o TPanel da barra de botoes (o mais estreito, altura < 60px)
        button_panel = None
        progress_bar = None
        for ctrl in apurar_dialog.descendants():
            if ctrl.class_name() == 'TProgressBar':
                progress_bar = ctrl
            cls = ctrl.class_name()
            if cls == 'TPanel':
                try:
                    r = ctrl.rectangle()
                    height = r.bottom - r.top
                    if 30 <= height <= 60:
                        button_panel = ctrl
                except Exception:
                    pass

        if button_panel:
            p_rect = button_panel.rectangle()
            panel_width = p_rect.right - p_rect.left
            # Centro Y do painel, mas acima da progress bar se ela existir
            if progress_bar:
                pb_rect = progress_bar.rectangle()
                center_y = (p_rect.top + pb_rect.top) // 2
            else:
                center_y = (p_rect.top + p_rect.bottom) // 2

            # Apurar eh o 1o de 3 botoes. Dividir o painel em 3 partes iguais.
            btn_zone_width = panel_width // 3
            click_x = p_rect.left + btn_zone_width // 2  # centro da 1a zona

            apurar_coords = (click_x, center_y)
            api.log_progress(processo_id,
                f"Ref: TPanel rect=({p_rect.left},{p_rect.top},{p_rect.right},{p_rect.bottom}), "
                f"Coordenada Apurar: ({click_x}, {center_y})")
        else:
            api.log_progress(processo_id, "TPanel barra de botoes nao encontrado!", level="ERROR")

    if not apurar_btn and not apurar_coords:
        raise Exception("Botao 'Apurar' nao encontrado e sem referencia para coordenada.")

    def click_apurar():
        if apurar_btn:
            apurar_btn.click_input()
        else:
            pwa_mouse.click(coords=apurar_coords)

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

        # Heartbeat periodico
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
    """Fecha o dialog de apuracao clicando em Fechar, por coordenada no TPanel, ou ESC."""
    api.log_progress(processo_id, "Fechando dialog de Apuracao...")
    time.sleep(1)

    # Tentar encontrar Fechar com HWND
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                ctrl.click_input()
                time.sleep(0.5)
                api.log_progress(processo_id, "Etapa 5 concluida: Apuracao finalizada com sucesso.")
                return

    # Fechar tambem eh TSpeedButton sem HWND — clicar na 3a zona do TPanel
    for w in app.windows():
        title = w.window_text()
        if 'Apur' in title and 'Pr' in title:
            for ctrl in w.descendants():
                if ctrl.class_name() == 'TPanel':
                    try:
                        r = ctrl.rectangle()
                        height = r.bottom - r.top
                        if 30 <= height <= 60:
                            panel_width = r.right - r.left
                            btn_zone = panel_width // 3
                            # Fechar eh o 3o botao (ultima zona)
                            progress_bar = None
                            for c2 in w.descendants():
                                if c2.class_name() == 'TProgressBar':
                                    progress_bar = c2
                                    break
                            if progress_bar:
                                pb_rect = progress_bar.rectangle()
                                cy = (r.top + pb_rect.top) // 2
                            else:
                                cy = (r.top + r.bottom) // 2
                            cx = r.left + btn_zone * 2 + btn_zone // 2
                            api.log_progress(processo_id,
                                f"Fechar por coordenada no TPanel: ({cx}, {cy})")
                            pwa_mouse.click(coords=(cx, cy))
                            time.sleep(0.5)
                            api.log_progress(processo_id, "Etapa 5 concluida: Apuracao finalizada com sucesso.")
                            return
                    except Exception:
                        pass

    # Ultimo fallback: ESC
    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
    api.log_progress(processo_id, "Etapa 5 concluida: Apuracao finalizada com sucesso.")
