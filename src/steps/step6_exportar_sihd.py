import re
import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse

MENU_PROCESSAMENTO_INDEX = 2


def execute(config, api, processo_id, app, main_window, toolbar, hospital_data):
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
    #   [0] CONSISTIR PRODUCAO
    #   [1] APURAR PREVIA
    #   [2] EXPORTAR PRODUCAO PARA... (tem submenu ->)
    keyboard.send_keys("{DOWN}{DOWN}{DOWN}")  # 3x DOWN para chegar em EXPORTAR
    time.sleep(0.2)
    keyboard.send_keys("{RIGHT}")  # abre submenu
    time.sleep(0.3)
    # Submenu: SIHD (SECRETARIA) eh o 1o item
    keyboard.send_keys("{ENTER}")  # seleciona SIHD (SECRETARIA)
    time.sleep(2)

    api.log_progress(processo_id, "Menu PROCESSAMENTO > EXPORTAR > SIHD clicado.")

    # 2. Encontrar o dialog de exportacao
    export_dialog = None
    for w in app.windows():
        title = w.window_text()
        if 'Exporta' in title and 'Produ' in title:
            export_dialog = w
            break

    if not export_dialog:
        export_dialog = app.top_window()

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
    export_dir = config.get("export", {}).get("dir", r"C:\exports")
    cnes = hospital_data.get("cnes", "0000000")
    cnes_clean = re.sub(r'\D', '', cnes)  # "227023-4" -> "2270234"
    competencia = _ler_competencia(main_window)
    filename = f"{cnes_clean}_{competencia}.txt"
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

    arquivo_edit.click_input()
    time.sleep(0.2)
    arquivo_edit.set_edit_text(export_path)
    time.sleep(0.5)

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

    if not exportar_btn and not exportar_coords:
        raise Exception("Botao 'Exportar' nao encontrado e sem referencia para coordenada.")

    def click_exportar():
        if exportar_btn:
            exportar_btn.click_input()
        else:
            pwa_mouse.click(coords=exportar_coords)

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

        # Verificar popup OK
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, f"Exportacao concluida em {elapsed}s!")
                    ctrl.click_input()
                    time.sleep(1)
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


def _ler_competencia(main_window):
    """
    Le a competencia da status bar do SISAIH01.
    Formato esperado: "APRES.: 02 / 2026" -> "022026"
    """
    for ctrl in main_window.descendants():
        txt = ctrl.window_text()
        # Procurar padrao "APRES.: MM / AAAA" ou "MM / AAAA"
        match = re.search(r'(\d{2})\s*/\s*(\d{4})', txt)
        if match:
            mes = match.group(1)
            ano = match.group(2)
            return f"{mes}{ano}"

    # Fallback: procurar em todas as janelas
    try:
        app = main_window.app
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                match = re.search(r'(\d{2})\s*/\s*(\d{4})', txt)
                if match:
                    return f"{match.group(1)}{match.group(2)}"
    except Exception:
        pass

    # Se nao encontrou, retornar placeholder
    return "000000"


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de exportacao clicando em Fechar, por coordenada no TPanel, ou ESC."""
    api.log_progress(processo_id, "Fechando dialog de Exportacao...")
    time.sleep(1)

    # Tentar Fechar com HWND
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                ctrl.click_input()
                time.sleep(0.5)
                api.log_progress(processo_id, "Etapa 6 concluida: Exportacao para SIHD finalizada com sucesso.")
                return

    # Fechar tambem eh TSpeedButton — clicar na 3a zona do TPanel
    for w in app.windows():
        title = w.window_text()
        if 'Exporta' in title and 'Produ' in title:
            for ctrl in w.descendants():
                if ctrl.class_name() == 'TPanel':
                    try:
                        r = ctrl.rectangle()
                        height = r.bottom - r.top
                        if 30 <= height <= 60:
                            panel_width = r.right - r.left
                            btn_zone = panel_width // 3
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
                            api.log_progress(processo_id, "Etapa 6 concluida: Exportacao para SIHD finalizada com sucesso.")
                            return
                    except Exception:
                        pass

    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
    api.log_progress(processo_id, "Etapa 6 concluida: Exportacao para SIHD finalizada com sucesso.")
