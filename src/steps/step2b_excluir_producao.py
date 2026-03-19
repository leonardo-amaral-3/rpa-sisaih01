import time
from pywinauto import keyboard

MENU_MANUTENCAO_INDEX = 5


def competencia_to_apresentacao(competencia):
    """
    Converte competencia (YYYYMM) para apresentacao (MM/YYYY),
    onde apresentacao = competencia + 1 mes.
    Ex: '202601' -> '02/2026'
    """
    year = int(competencia[:4])
    month = int(competencia[4:6])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f"{month:02d}/{year}"


def execute(config, api, processo_id, app, main_window, toolbar, competencia):
    """
    Etapa 2b: MANUTENCAO -> EXCLUIR PRODUCAO
    Limpa dados de producao anteriores antes de importar novo arquivo.
    """
    apresentacao = competencia_to_apresentacao(competencia)
    api.log_progress(processo_id, f"Iniciando Etapa 2b: Excluir Producao (apresentacao: {apresentacao})")

    # 1. Navegar: MANUTENCAO -> EXCLUIR PRODUCAO
    main_window.set_focus()
    time.sleep(0.3)

    btn = toolbar.button(MENU_MANUTENCAO_INDEX)
    btn.click()
    time.sleep(0.5)

    # EXCLUIR PRODUCAO eh o 2o item do dropdown (abaixo de IMPORTAR)
    keyboard.send_keys("{DOWN}")
    time.sleep(0.2)
    keyboard.send_keys("{ENTER}")
    time.sleep(1)

    # 2. Encontrar o dialog "Excluir Producao"
    excluir_dialog = None
    for w in app.windows():
        title = w.window_text()
        if 'Excluir' in title and 'Produ' in title:
            excluir_dialog = w
            break

    if not excluir_dialog:
        excluir_dialog = app.top_window()

    api.log_progress(processo_id, f"Dialog encontrado: '{excluir_dialog.window_text()}'")

    # 3. Preencher o campo "Apresentacao" (Edit no dialog)
    apresentacao_edit = None
    for ctrl in excluir_dialog.descendants():
        cls = ctrl.class_name()
        if 'Edit' in cls:
            apresentacao_edit = ctrl
            break

    if not apresentacao_edit:
        raise Exception("Campo 'Apresentacao' nao encontrado no dialog de exclusao.")

    apresentacao_edit.click_input()
    time.sleep(0.2)
    apresentacao_edit.set_edit_text(apresentacao)
    time.sleep(0.3)

    api.log_progress(processo_id, f"Apresentacao preenchida: {apresentacao}")

    # 4. Clicar no botao "Excluir"
    excluir_btn = None
    for ctrl in excluir_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        is_button = 'Button' in cls or 'Btn' in cls
        if 'Excluir' in txt and is_button:
            excluir_btn = ctrl
            break

    if not excluir_btn:
        raise Exception("Botao 'Excluir' nao encontrado no dialog.")

    api.log_progress(processo_id, "Clicando em Excluir...")
    excluir_btn.click_input()
    time.sleep(1)

    # 5. Dialog de confirmacao: "CONFIRMA EXCLUSAO?" -> Clicar "Yes"
    confirmed = False
    for attempt in range(10):
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt in ('Yes', '&Yes', 'Sim', '&Sim') and ('Button' in cls or 'Btn' in cls):
                    ctrl.click_input()
                    confirmed = True
                    api.log_progress(processo_id, "Confirmacao de exclusao: Yes clicado.")
                    break
            if confirmed:
                break
        if confirmed:
            break
        time.sleep(0.5)

    if not confirmed:
        api.log_progress(processo_id, "Dialog de confirmacao nao encontrado. Pode nao haver producao para excluir.", level="WARNING")
        # Fechar dialog e continuar — pode nao ter dados para excluir
        _fechar_dialog(app, api, processo_id)
        return True

    time.sleep(1)

    # 6. Dialog de sucesso: "EXCLUIDA COM SUCESSO!" -> Clicar "OK"
    ok_clicked = False
    for attempt in range(10):
        for w in app.windows():
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    ctrl.click_input()
                    ok_clicked = True
                    api.log_progress(processo_id, "Exclusao concluida: OK clicado.")
                    break
            if ok_clicked:
                break
        if ok_clicked:
            break
        time.sleep(0.5)

    time.sleep(0.5)

    # 7. Fechar o dialog de exclusao
    _fechar_dialog(app, api, processo_id)

    api.log_progress(processo_id, "Etapa 2b concluida: Producao anterior excluida.")
    return True


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de exclusao."""
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Excluir', 'Produ'], 'Etapa 2b')
