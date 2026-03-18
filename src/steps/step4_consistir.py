import time
from pywinauto import keyboard
from pywinauto.controls.common_controls import ToolbarWrapper
from pywinauto import mouse as pwa_mouse

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
    # O botao pode ser TBitBtn, TSpeedButton, TToolButton, ou dentro de uma TToolBar.
    consistir_btn = None

    # Debug: listar TODOS os controles (inclusive sem texto) no dialog de consistencia
    all_in_dialog = []
    for ctrl in consist_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        try:
            rect = ctrl.rectangle()
            all_in_dialog.append(f"'{txt}' ({cls}) rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
        except Exception:
            all_in_dialog.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"TODOS descendentes do dialog (com rect): {'; '.join(all_in_dialog)}", level="DEBUG")

    # Debug: listar controles com texto em todas as janelas
    all_with_text = []
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if txt.strip():
                all_with_text.append(f"'{txt}' ({cls})")
            # Estrategia 1: qualquer controle com texto "Consistir" que seja clicavel
            if 'Consistir' in txt and not consistir_btn:
                consistir_btn = ctrl
    api.log_progress(processo_id, f"Controles com texto (todas janelas): {'; '.join(all_with_text)}", level="DEBUG")

    # Estrategia 2: procurar TToolBar e enumerar seus botoes
    if not consistir_btn:
        for w in app.windows():
            for ctrl in w.descendants():
                if ctrl.class_name() == 'TToolBar':
                    try:
                        tb = ToolbarWrapper(ctrl.handle)
                        count = tb.button_count()
                        api.log_progress(processo_id, f"TToolBar encontrada com {count} botoes", level="DEBUG")
                        for i in range(count):
                            btn = tb.button(i)
                            btn_text = btn.text if hasattr(btn, 'text') else ''
                            api.log_progress(processo_id, f"  Toolbar btn[{i}]: '{btn_text}'", level="DEBUG")
                            if 'Consistir' in btn_text:
                                consistir_btn = btn
                                api.log_progress(processo_id, f"Botao Consistir encontrado na TToolBar[{i}]")
                                break
                    except Exception as e:
                        api.log_progress(processo_id, f"Erro ao ler TToolBar: {e}", level="DEBUG")
                if consistir_btn:
                    break
            if consistir_btn:
                break

    # Estrategia 3: Encontrar por eliminacao na toolbar do dialog
    # O botao Consistir pode ter window_text() vazio (Delphi TBitBtn com glyph)
    if not consistir_btn:
        api.log_progress(processo_id, "Estrategia 3: buscando Consistir por eliminacao na toolbar...", level="DEBUG")
        known_btn_texts = {'Selecionar', '&Selecionar', 'Fechar', '&Fechar',
                           'Imprimir', '&Imprimir', 'Gravar', '&Gravar'}
        for ctrl in consist_dialog.descendants():
            cls = ctrl.class_name()
            txt = ctrl.window_text().strip()
            if cls in ('TBitBtn', 'TSpeedButton', 'TToolButton') and txt not in known_btn_texts:
                try:
                    rect = ctrl.rectangle()
                    api.log_progress(processo_id,
                        f"Candidato Consistir: texto='{txt}', classe={cls}, "
                        f"rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
                except Exception:
                    api.log_progress(processo_id,
                        f"Candidato Consistir: texto='{txt}', classe={cls}")
                # Aceitar se nao for um botao conhecido
                if txt not in known_btn_texts and 'Selecionar' not in txt:
                    consistir_btn = ctrl
                    break

    # Estrategia 4: Consistir eh provavelmente um TSpeedButton (TGraphicControl, sem HWND)
    # TSpeedButton nao aparece em descendants() do pywinauto pois nao tem window handle.
    # Solucao: clicar por coordenada relativa ao botao Selecionar (que eh TBitBtn com HWND).
    # Layout da barra: [Consistir] [Todas] [Selecionar] [Imprimir] [Fechar]
    consistir_coords = None
    if not consistir_btn:
        api.log_progress(processo_id,
            "Estrategia 4: Consistir nao tem HWND (provavel TSpeedButton). "
            "Calculando coordenada relativa ao botao Selecionar...", level="DEBUG")

        # Encontrar Selecionar como ponto de referencia
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
            sel_width = sel_rect.right - sel_rect.left  # ~120px

            # Consistir fica 2 posicoes à esquerda de Selecionar (Consistir | Todas | Selecionar)
            # Cada botao tem ~largura de Selecionar, checkbox Todas ~80px
            # Estimativa conservadora: centro do Consistir = ~1.5 larguras à esquerda
            click_x = sel_rect.left - sel_width - 60  # pula Todas (~80px) + metade de Consistir
            api.log_progress(processo_id,
                f"Ref: Selecionar rect=({sel_rect.left},{sel_rect.top},{sel_rect.right},{sel_rect.bottom}), "
                f"sel_width={sel_width}")

            # Encontrar o painel container para garantir que nao clicamos fora dele
            for ctrl in consist_dialog.descendants():
                if ctrl.class_name() == 'TPanel':
                    p_rect = ctrl.rectangle()
                    # O painel da barra de botoes contem o Selecionar
                    if p_rect.top <= sel_rect.top and p_rect.bottom >= sel_rect.bottom:
                        if click_x < p_rect.left + 10:
                            # Ajustar para nao clicar fora do painel
                            click_x = p_rect.left + 65  # ~centro do primeiro botao
                            api.log_progress(processo_id,
                                f"Ajustado para nao sair do painel: panel_left={p_rect.left}")
                        break

            consistir_coords = (click_x, center_y)
            api.log_progress(processo_id, f"Coordenada calculada para Consistir: ({click_x}, {center_y})")
        else:
            api.log_progress(processo_id, "Botao Selecionar nao encontrado como referencia!", level="ERROR")

    if not consistir_btn and not consistir_coords:
        raise Exception(f"Botao 'Consistir' nao encontrado e sem referencia para coordenada. Controles: {'; '.join(all_with_text)}")

    # Helper para clicar em Consistir (por controle ou por coordenada)
    def click_consistir():
        if consistir_btn:
            consistir_btn.click_input()
        else:
            pwa_mouse.click(coords=consistir_coords)

    # === FASE 1: Primeiro clique — Abre banco de dados e carrega AIHs ===
    api.log_progress(processo_id, "Fase 1: Clicando em Consistir para abrir banco e carregar AIHs...")
    click_consistir()

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
    click_consistir()

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
    """Fecha o dialog de Consistencia de forma robusta."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Consist', 'Produ'], 'Etapa 4')
