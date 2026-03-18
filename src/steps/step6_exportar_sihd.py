import os
import re
import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse

MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar, hospital_data, file_path=None):
    """
    Etapa 6: PROCESSAMENTO -> EXPORTAR PRODUCAO PARA... -> SIHD (SECRETARIA)
    Gera o arquivo de exportacao para envio ao SIHD.
    """
    api.log_progress(processo_id, "Iniciando Etapa 6: Exportar Producao para SIHD")

    # 1. Navegar no menu: PROCESSAMENTO -> EXPORTAR PRODUCAO PARA... -> SIHD (SECRETARIA)
    # Este item tem submenu, entao navegamos manualmente em vez de usar click_menu
    from steps.step1_check_open import click_menu
    click_menu(main_window, toolbar, MENU_PROCESSAMENTO_INDEX)  # so abre o menu

    # PROCESSAMENTO dropdown:
    #   [0] CONSISTIR PRODUCAO  (ja selecionado ao abrir)
    #   [1] APURAR PREVIA       (1x DOWN)
    #   [2] EXPORTAR PRODUCAO PARA... (2x DOWN, tem submenu ->)
    keyboard.send_keys("{DOWN}{DOWN}")  # 2x DOWN para chegar em EXPORTAR
    time.sleep(0.2)
    keyboard.send_keys("{RIGHT}")  # abre submenu
    time.sleep(0.3)
    # Submenu: SIHD (SECRETARIA) eh o 1o item
    keyboard.send_keys("{ENTER}")  # seleciona SIHD (SECRETARIA)
    time.sleep(2)

    api.log_progress(processo_id, "Menu PROCESSAMENTO > EXPORTAR > SIHD clicado.")

    # 2. Encontrar o dialog de exportacao (com retry, pode demorar a abrir)
    export_dialog = None
    for attempt in range(5):
        for w in app.windows():
            title = w.window_text()
            if 'Exporta' in title and 'Produ' in title:
                export_dialog = w
                break
        if export_dialog:
            break
        time.sleep(1)

    if not export_dialog:
        # Debug: listar todas as janelas para diagnostico
        all_wins = []
        for w in app.windows():
            all_wins.append(f"'{w.window_text()}' ({w.class_name()})")
        api.log_progress(processo_id, f"Janelas disponiveis: {'; '.join(all_wins)}", level="DEBUG")
        raise Exception("Dialog de exportacao nao encontrado. Verifique se o menu PROCESSAMENTO > EXPORTAR abriu corretamente.")

    api.log_progress(processo_id, f"Dialog encontrado: '{export_dialog.window_text()}'")

    # Debug: listar controles
    all_in_dialog = []
    for ctrl in export_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        try:
            rect = ctrl.rectangle()
            all_in_dialog.append(f"'{txt}' ({cls}) rect=({rect.left},{rect.top},{rect.right},{rect.bottom})")
        except Exception:
            all_in_dialog.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"Descendentes do dialog: {'; '.join(all_in_dialog)}", level="DEBUG")

    # 3. Gerar o caminho do arquivo de exportacao
    # Formato: {YYYYMM}AIH{CNES}.txt -> ex: 202602AIH2270234.txt
    export_dir = config.get("export", {}).get("dir", r"C:\exports")
    os.makedirs(export_dir, exist_ok=True)
    cnes = hospital_data.get("cnes", "0000000")
    cnes_clean = re.sub(r'\D', '', cnes)  # "227023-4" -> "2270234"
    competencia_yyyymm = _ler_competencia(app, api, processo_id, file_path)
    filename = f"{competencia_yyyymm}AIH{cnes_clean}.txt"
    export_path = f"{export_dir}\\{filename}"

    api.log_progress(processo_id, f"Arquivo de exportacao: {export_path}")

    # 4. Preencher o campo "Arquivo" (TEdit)
    arquivo_edit = None
    for ctrl in export_dialog.descendants():
        cls = ctrl.class_name()
        if 'Edit' in cls:
            arquivo_edit = ctrl
            break

    if not arquivo_edit:
        raise Exception("Campo 'Arquivo' nao encontrado no dialog de exportacao.")

    # Logar valor atual antes de preencher
    current_val = arquivo_edit.window_text()
    api.log_progress(processo_id, f"Valor atual do campo Arquivo: '{current_val}'", level="DEBUG")

    arquivo_edit.click_input()
    time.sleep(0.2)
    arquivo_edit.set_edit_text(export_path)
    time.sleep(0.3)

    # Verificar se o valor foi setado corretamente
    new_val = arquivo_edit.window_text()
    api.log_progress(processo_id, f"Valor apos set_edit_text: '{new_val}'", level="DEBUG")
    if export_path not in new_val and new_val != export_path:
        # Tentar via teclado: Ctrl+A, digitar
        api.log_progress(processo_id, "set_edit_text nao funcionou, tentando via teclado...", level="DEBUG")
        arquivo_edit.click_input()
        time.sleep(0.1)
        keyboard.send_keys("^a")  # Ctrl+A
        time.sleep(0.1)
        keyboard.send_keys(export_path.replace("\\", "{\\}"), with_spaces=True)
        time.sleep(0.3)
    time.sleep(0.2)

    api.log_progress(processo_id, f"Campo Arquivo preenchido: {export_path}")

    # 5. Encontrar o botao "Exportar"
    # Pode ser TSpeedButton (sem HWND) — mesma estrategia dos steps anteriores
    exportar_btn = None
    exportar_coords = None

    # Estrategia 1: buscar por texto "Exportar" nos descendants
    for ctrl in export_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        if 'Exportar' in txt and ('Button' in cls or 'Btn' in cls or 'Speed' in cls):
            exportar_btn = ctrl
            api.log_progress(processo_id, f"Botao Exportar encontrado: '{txt}' ({cls})")
            break

    # Estrategia 2: buscar TBitBtn desconhecido
    if not exportar_btn:
        known_texts = {'Fechar', '&Fechar', 'Imprimir', '&Imprimir'}
        for ctrl in export_dialog.descendants():
            cls = ctrl.class_name()
            txt = ctrl.window_text().strip()
            if cls in ('TBitBtn', 'TSpeedButton', 'TToolButton') and txt not in known_texts:
                exportar_btn = ctrl
                api.log_progress(processo_id, f"Candidato Exportar: '{txt}' ({cls})")
                break

    # Estrategia 3: coordenada relativa ao botao Fechar
    if not exportar_btn:
        api.log_progress(processo_id,
            "Exportar nao tem HWND (provavel TSpeedButton). Calculando coordenada...", level="DEBUG")

        fechar_btn = None
        for ctrl in export_dialog.descendants():
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

            for ctrl in export_dialog.descendants():
                if ctrl.class_name() == 'TPanel':
                    p_rect = ctrl.rectangle()
                    if p_rect.top <= fechar_rect.top and p_rect.bottom >= fechar_rect.bottom:
                        if click_x < p_rect.left + 10:
                            click_x = p_rect.left + btn_width // 2 + 5
                        break

            exportar_coords = (click_x, center_y)
            api.log_progress(processo_id,
                f"Ref: Fechar rect=({fechar_rect.left},{fechar_rect.top},{fechar_rect.right},{fechar_rect.bottom}), "
                f"Coordenada Exportar: ({click_x}, {center_y})")
        else:
            api.log_progress(processo_id, "Botao Fechar tambem nao tem HWND, usando TPanel...", level="DEBUG")

    # Estrategia 4: TODOS os botoes sao TSpeedButton sem HWND
    # Usar o TPanel (barra de botoes) como referencia.
    # Layout: [Exportar] [Imprimir] [Fechar] dentro do painel estreito
    if not exportar_btn and not exportar_coords:
        api.log_progress(processo_id, "Estrategia 4: usando TPanel como referencia...", level="DEBUG")

        button_panel = None
        progress_bar = None
        for ctrl in export_dialog.descendants():
            if ctrl.class_name() == 'TProgressBar':
                progress_bar = ctrl
            if ctrl.class_name() == 'TPanel':
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
            if progress_bar:
                pb_rect = progress_bar.rectangle()
                center_y = (p_rect.top + pb_rect.top) // 2
            else:
                center_y = (p_rect.top + p_rect.bottom) // 2

            btn_zone_width = panel_width // 3
            click_x = p_rect.left + btn_zone_width // 2

            exportar_coords = (click_x, center_y)
            api.log_progress(processo_id,
                f"Ref: TPanel rect=({p_rect.left},{p_rect.top},{p_rect.right},{p_rect.bottom}), "
                f"Coordenada Exportar: ({click_x}, {center_y})")

    # Estrategia 5: Usar dialog rect diretamente (igual step5)
    if not exportar_btn and not exportar_coords:
        api.log_progress(processo_id,
            "Nenhum botao encontrado, usando dialog rect como fallback...", level="DEBUG")

    def click_exportar():
        if exportar_btn:
            exportar_btn.click_input()
        elif exportar_coords:
            pwa_mouse.click(coords=exportar_coords)
        else:
            from utils.window_utils import click_button_by_dialog_rect
            click_button_by_dialog_rect(export_dialog, api, processo_id, position="left")

    # 6. Clicar em Exportar
    api.log_progress(processo_id, "Clicando em Exportar...")
    click_exportar()

    # 7. Aguardar conclusao
    timeout = config["timeouts"].get("exportar", 300)
    start_time = time.time()
    heartbeat_interval = 30
    last_heartbeat = start_time

    api.log_progress(processo_id, f"Exportacao em andamento (timeout: {timeout}s)...")

    while time.time() - start_time < timeout:
        time.sleep(3)
        elapsed = int(time.time() - start_time)

        # Heartbeat
        if time.time() - last_heartbeat >= heartbeat_interval:
            api.log_progress(processo_id, f"Exportacao em andamento ({elapsed}s)...")
            last_heartbeat = time.time()

        # Verificar popup OK (pode ser sucesso ou erro como I/O 103)
        for w in app.windows():
            win_text = w.window_text()
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    # Verificar se eh popup de erro
                    is_error = False
                    for c2 in w.descendants():
                        t2 = c2.window_text()
                        if t2 and ('erro' in t2.lower() or 'error' in t2.lower() or 'I/O' in t2):
                            is_error = True
                            api.log_progress(processo_id,
                                f"Popup de erro detectado: '{t2}'. Clicando OK...", level="WARNING")
                            break
                    ctrl.click_input()
                    time.sleep(1)
                    if is_error:
                        # Erro I/O 103 — arquivo pode ter sido criado mesmo assim
                        # Continuar monitorando ou tentar novamente
                        api.log_progress(processo_id,
                            "Erro durante exportacao, verificando se arquivo foi gerado...", level="WARNING")
                        continue
                    api.log_progress(processo_id, f"Exportacao concluida em {elapsed}s!")
                    _fechar_dialog(app, api, processo_id)
                    return export_path

        # Verificar se "Total de AIH Exportada" mudou (indica conclusao)
        for ctrl in export_dialog.descendants():
            txt = ctrl.window_text()
            if 'Total' in txt and 'AIH' in txt and 'Exportad' in txt:
                # Se tem numero > 0, exportacao concluiu
                numbers = re.findall(r'\d+', txt)
                if numbers and int(numbers[-1]) > 0:
                    api.log_progress(processo_id, f"Exportacao concluida: {txt}")
                    _fechar_dialog(app, api, processo_id)
                    return export_path

    raise TimeoutError(f"Exportacao nao concluiu em {timeout} segundos.")


def _ler_competencia(app, api, processo_id, file_path=None):
    """
    Le a competencia de APRESENTACAO (YYYYMM) para o nome do arquivo de exportacao.

    Estrategia:
    1. Extrair do nome/conteudo do arquivo de producao (competencia de producao + 1 mes = apresentacao)
    2. Buscar nas janelas do SISAIH01 (titulo ou controles com "MM / AAAA")
    3. Fallback: "000000"

    A competencia de APRESENTACAO eh sempre producao + 1 mes.
    Ex: producao 01/2026 -> apresentacao 02/2026 -> YYYYMM = "202602"
    """
    # Estrategia 1: Extrair do file_path (nome do arquivo de producao)
    # Ex: "producao_vargas_202601.txt" -> producao=202601 -> apresentacao=202602
    if file_path:
        basename = os.path.basename(file_path)
        # Procurar YYYYMM no nome do arquivo
        match = re.search(r'(\d{4})(0[1-9]|1[0-2])', basename)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            # Apresentacao = producao + 1 mes
            month += 1
            if month > 12:
                month = 1
                year += 1
            comp = f"{year}{month:02d}"
            api.log_progress(processo_id,
                f"Competencia extraida do arquivo: '{basename}' -> prod={match.group(0)} -> apres={comp}")
            return comp

    # Estrategia 2: Buscar nas janelas do SISAIH01
    # O titulo ou status bar pode mostrar "APRES.: 02 / 2026" ou "APRESENTAÇÃO: 02/2026"
    try:
        for w in app.windows():
            title = w.window_text()
            match = re.search(r'(\d{2})\s*/\s*(\d{4})', title)
            if match:
                mm, yyyy = match.group(1), match.group(2)
                comp = f"{yyyy}{mm}"
                api.log_progress(processo_id,
                    f"Competencia encontrada no titulo: '{title}' -> {comp}", level="DEBUG")
                return comp

            for ctrl in w.descendants():
                txt = ctrl.window_text()
                if not txt:
                    continue
                match = re.search(r'(\d{2})\s*/\s*(\d{4})', txt)
                if match:
                    mm, yyyy = match.group(1), match.group(2)
                    comp = f"{yyyy}{mm}"
                    api.log_progress(processo_id,
                        f"Competencia encontrada: '{txt}' -> {comp}", level="DEBUG")
                    return comp
    except Exception as e:
        api.log_progress(processo_id, f"Erro ao buscar competencia nas janelas: {e}", level="DEBUG")

    api.log_progress(processo_id, "Competencia nao encontrada!", level="WARNING")
    return "000000"


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de exportacao de forma robusta."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Exporta', 'Produ'], 'Etapa 6')
