import time
from pywinauto import keyboard
from pywinauto.controls.common_controls import ToolbarWrapper
from pywinauto import mouse as pwa_mouse

# PROCESSAMENTO eh o botao[2] na toolbar principal
MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar):
    """
    Etapa 4: PROCESSAMENTO -> CONSISTIR PRODUCAO
    Clica em Consistir e aguarda o processamento.
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
    all_in_dialog = []
    for ctrl in consist_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        try:
            rect = ctrl.rectangle()
            all_in_dialog.append(f"'{txt}' ({cls}) rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
        except Exception:
            all_in_dialog.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"Descendentes do dialog: {'; '.join(all_in_dialog)}", level="DEBUG")

    # 3. Encontrar o botao "Consistir" (ou coordenada)
    consistir_btn, consistir_coords = _encontrar_botao_consistir(consist_dialog, app, api, processo_id)

    def click_consistir():
        if consistir_btn:
            consistir_btn.click_input()
        elif consistir_coords:
            pwa_mouse.click(coords=consistir_coords)
        else:
            from utils.window_utils import click_button_by_dialog_rect
            click_button_by_dialog_rect(consist_dialog, api, processo_id, position="left")

    # 4. Clicar em Consistir (1 clique inicia todo o processamento)
    api.log_progress(processo_id, "Clicando em Consistir...")
    click_consistir()

    # 5. Monitorar conclusao
    timeout = config["timeouts"].get("consistir", 3600)
    start_time = time.time()
    heartbeat_interval = 30
    last_heartbeat = start_time
    ja_clicou_segunda_vez = False

    api.log_progress(processo_id, f"Consistencia em andamento (timeout: {timeout}s)...")

    while time.time() - start_time < timeout:
        time.sleep(3)
        elapsed = int(time.time() - start_time)

        # Heartbeat
        if time.time() - last_heartbeat >= heartbeat_interval:
            proc_info = _ler_status_processamento(consist_dialog)
            api.log_progress(processo_id, f"Consistencia em andamento ({elapsed}s)... {proc_info}")
            last_heartbeat = time.time()

        # Verificar popup OK
        ok_found = False
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, f"Consistencia concluida em {elapsed}s!")
                    ctrl.click_input()
                    time.sleep(1)
                    _fechar_dialog(app, api, processo_id)
                    return True
            if ok_found:
                break

        # Verificar "Fim" no historico (indica que processamento terminou)
        for ctrl in consist_dialog.descendants():
            txt = ctrl.window_text()
            if not txt:
                continue
            # "Fim" no historico do processamento
            if 'Fim' in txt and ('Inicio' in txt or 'Total' in txt or 'Abrindo' in txt):
                api.log_progress(processo_id, f"Consistencia concluida em {elapsed}s! (detectado 'Fim' no historico)")
                _fechar_dialog(app, api, processo_id)
                return True

        # Verificar se apareceu "Preparado" ou "Selecione" — dados carregados mas nao processou
        # Isso pode acontecer se o 1o clique so carregou os dados. Nesse caso, clicar novamente.
        if not ja_clicou_segunda_vez and elapsed > 10:
            for ctrl in consist_dialog.descendants():
                txt = ctrl.window_text()
                if 'Preparado' in txt or 'Selecione' in txt:
                    api.log_progress(processo_id, "Dados carregados. Clicando novamente para processar...")
                    click_consistir()
                    ja_clicou_segunda_vez = True
                    break

    raise TimeoutError(f"Consistencia nao concluiu em {timeout} segundos.")


def _encontrar_botao_consistir(consist_dialog, app, api, processo_id):
    """Encontra o botao Consistir por varias estrategias. Retorna (btn, coords)."""
    consistir_btn = None

    # Estrategia 1: texto "Consistir" em qualquer controle
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            if 'Consistir' in txt:
                consistir_btn = ctrl
                api.log_progress(processo_id, f"Botao Consistir encontrado: '{txt}' ({ctrl.class_name()})")
                return consistir_btn, None

    # Estrategia 2: TToolBar com botoes
    for w in app.windows():
        for ctrl in w.descendants():
            if ctrl.class_name() == 'TToolBar':
                try:
                    tb = ToolbarWrapper(ctrl.handle)
                    count = tb.button_count()
                    api.log_progress(processo_id, f"TToolBar encontrada com {count} botoes", level="DEBUG")
                    for i in range(count):
                        try:
                            btn = tb.button(i)
                            btn_text = btn.text if hasattr(btn, 'text') else ''
                            api.log_progress(processo_id, f"  Toolbar btn[{i}]: '{btn_text}'", level="DEBUG")
                            if 'Consistir' in btn_text:
                                return btn, None
                        except Exception:
                            pass
                except Exception as e:
                    api.log_progress(processo_id, f"Erro ao ler TToolBar: {e}", level="DEBUG")

    # Estrategia 3: TBitBtn desconhecido (por eliminacao)
    known_texts = {'Selecionar', '&Selecionar', 'Fechar', '&Fechar',
                   'Imprimir', '&Imprimir', 'Gravar', '&Gravar', 'Todas', '&Todas'}
    for ctrl in consist_dialog.descendants():
        cls = ctrl.class_name()
        txt = ctrl.window_text().strip()
        if cls in ('TBitBtn', 'TSpeedButton', 'TToolButton') and txt not in known_texts:
            api.log_progress(processo_id, f"Candidato Consistir: '{txt}' ({cls})")
            return ctrl, None

    # Estrategia 4: Coordenada relativa ao Selecionar
    api.log_progress(processo_id,
        "Estrategia 4: Consistir nao tem HWND (provavel TSpeedButton). Calculando coordenada...", level="DEBUG")

    sel_btn = None
    for ctrl in consist_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        if 'Selecionar' in txt and 'Btn' in cls:
            sel_btn = ctrl
            break

    if sel_btn:
        sel_rect = sel_btn.rectangle()
        center_y = (sel_rect.top + sel_rect.bottom) // 2
        sel_width = sel_rect.right - sel_rect.left
        click_x = sel_rect.left - sel_width - 60

        for ctrl in consist_dialog.descendants():
            if ctrl.class_name() == 'TPanel':
                p_rect = ctrl.rectangle()
                if p_rect.top <= sel_rect.top and p_rect.bottom >= sel_rect.bottom:
                    if click_x < p_rect.left + 10:
                        click_x = p_rect.left + 65
                    break

        api.log_progress(processo_id,
            f"Ref: Selecionar rect=({sel_rect.left},{sel_rect.top},{sel_rect.right},{sel_rect.bottom}), "
            f"sel_width={sel_width}")
        api.log_progress(processo_id, f"Coordenada calculada para Consistir: ({click_x}, {center_y})")
        return None, (click_x, center_y)

    # Estrategia 5: dialog rect (fallback final)
    api.log_progress(processo_id, "Usando dialog rect como fallback...", level="DEBUG")
    return None, None


def _ler_status_processamento(dialog):
    """Le informacoes de status do dialog."""
    info_parts = []
    for ctrl in dialog.descendants():
        txt = ctrl.window_text()
        if any(kw in txt for kw in ['Processamento', 'Total', 'Preparado', 'Processando', 'Fim']):
            info_parts.append(txt.strip())
    return ' | '.join(info_parts) if info_parts else ''


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de Consistencia de forma robusta."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Consist', 'Produ'], 'Etapa 4')
