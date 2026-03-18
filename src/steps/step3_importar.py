import time
from pywinauto import keyboard
from pywinauto.application import Application


# Mapeamento de menus MANUTENÇÃO no submenu IMPORTAR:
#   IMPORTAR -> PRODUCAO
#   Teclado: click no botao MANUTENCAO, DOWN pra IMPORTAR, RIGHT pro submenu, ENTER em PRODUCAO
MENU_MANUTENCAO_INDEX = 5  # CADASTRO=0, PRODUCAO=1, PROCESSAMENTO=2, RELATORIOS=3, CONSULTA=4, MANUTENCAO=5


def navigate_to_importar_producao(main_window, toolbar):
    """
    Navega MANUTENCAO -> IMPORTAR -> PRODUCAO via teclado.
    O submenu IMPORTAR abre com seta RIGHT, e PRODUCAO eh o 1o item.
    """
    main_window.set_focus()
    time.sleep(0.3)

    # 1. Clicar no botao MANUTENCAO
    btn = toolbar.button(MENU_MANUTENCAO_INDEX)
    btn.click()
    time.sleep(0.5)

    # 2. O dropdown mostra: IMPORTAR, EXCLUIR PRODUCAO, etc.
    #    IMPORTAR eh o primeiro item -> nao precisa de DOWN
    #    Mas IMPORTAR tem um submenu (seta >) -> precisa RIGHT pra expandir
    keyboard.send_keys("{RIGHT}")  # Expande submenu de IMPORTAR
    time.sleep(0.3)

    # 3. Submenu abre: PRODUCAO, CEP, MODULO AUTORIZADOR, HABILITACAO
    #    PRODUCAO eh o primeiro -> ENTER direto
    keyboard.send_keys("{ENTER}")  # Seleciona PRODUCAO
    time.sleep(1)


def execute(config, api, processo_id, app, main_window, toolbar, file_path):
    """
    Etapa 3: MANUTENCAO -> IMPORTAR -> PRODUCAO
    Importa o arquivo SISA no SISAIH01.
    """
    api.log_progress(processo_id, "Iniciando Etapa 3: Importar Producao")
    
    # 1. Navegar no menu
    navigate_to_importar_producao(main_window, toolbar)
    api.log_progress(processo_id, "Dialog 'Importa Producao' aberto.")
    time.sleep(1)
    
    # 2. Encontrar o dialog "Importa Producao"
    import_dialog = None
    for w in app.windows():
        title = w.window_text()
        if 'Importa' in title and 'Produ' in title:
            import_dialog = w
            break
    
    if not import_dialog:
        # Fallback: tentar encontrar pelo campo Arquivo
        import_dialog = app.top_window()
    
    api.log_progress(processo_id, f"Dialog encontrado: '{import_dialog.window_text()}'")
    
    # 3. Preencher o campo "Arquivo" com o path completo do arquivo
    # O campo eh um Edit dentro do dialog. Vamos procurar o TEdit/Edit
    arquivo_edit = None
    for ctrl in import_dialog.descendants():
        cls = ctrl.class_name()
        if 'Edit' in cls:
            arquivo_edit = ctrl
            break
    
    if not arquivo_edit:
        # Se nao achou o Edit, procura em todas as janelas
        for w in app.windows():
            for ctrl in w.descendants():
                if 'Edit' in ctrl.class_name():
                    arquivo_edit = ctrl
                    break
            if arquivo_edit:
                break
    
    if not arquivo_edit:
        raise Exception("Campo 'Arquivo' nao encontrado no dialog de importacao.")
    
    # Limpar e digitar o caminho do arquivo
    arquivo_edit.click_input()
    time.sleep(0.2)
    arquivo_edit.set_edit_text(file_path)
    time.sleep(0.5)
    
    api.log_progress(processo_id, f"Arquivo selecionado: {file_path}")
    
    # 4. Clicar no botao "Importar"
    # SISAIH01 eh Delphi — botoes podem ser TButton, TBitBtn, TSpeedButton, etc.
    # Em TBitBtn com icone, window_text() pode retornar vazio.
    importar_btn = None

    # Debug: listar TODOS os controles do dialog para diagnostico
    all_controls = []
    for ctrl in import_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        all_controls.append(f"'{txt}' ({cls})")
    api.log_progress(processo_id, f"Controles no dialog: {'; '.join(all_controls)}", level="DEBUG")

    # Estrategia 1: buscar por texto "Importar" + classe de botao
    for ctrl in import_dialog.descendants():
        txt = ctrl.window_text()
        cls = ctrl.class_name()
        is_button = ('Button' in cls or 'Btn' in cls)
        if 'Importar' in txt and is_button:
            importar_btn = ctrl
            break

    # Estrategia 2: buscar TBitBtn no dialog (pode ter texto vazio mas ser o botao certo)
    if not importar_btn:
        for ctrl in import_dialog.descendants():
            if ctrl.class_name() == 'TBitBtn':
                importar_btn = ctrl
                api.log_progress(processo_id, f"Botao encontrado via classe TBitBtn (texto: '{ctrl.window_text()}')")
                break

    # Estrategia 3: buscar qualquer controle com texto "Importar" (pode ser TPanel, TLabel, etc)
    if not importar_btn:
        for ctrl in import_dialog.descendants():
            txt = ctrl.window_text()
            if 'Importar' in txt and ctrl.class_name() not in ('TLabel', 'TStaticText'):
                importar_btn = ctrl
                api.log_progress(processo_id, f"Botao encontrado por texto em {ctrl.class_name()}")
                break

    if not importar_btn:
        raise Exception(f"Botao 'Importar' nao encontrado. Controles: {'; '.join(all_controls)}")
    
    api.log_progress(processo_id, "Clicando em Importar... Aguardando processamento.")
    importar_btn.click_input()
    
    # 5. Aguardar a importacao concluir
    # A importacao mostra uma barra de progresso e depois um popup com OK
    timeout = config["timeouts"].get("import_file", 600)
    start_time = time.time()
    
    api.log_progress(processo_id, f"Aguardando importacao concluir (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        time.sleep(3)
        
        # Procurar popup de conclusao (geralmente um MessageBox com botao OK)
        for w in app.windows():
            title = w.window_text()
            # Procurar botoes OK em dialogs de mensagem
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if txt == 'OK' and ('Button' in cls or 'Btn' in cls):
                    api.log_progress(processo_id, "Importacao concluida! Clicando OK.")
                    ctrl.click_input()
                    time.sleep(1)
                    
                    # 6. Fechar o dialog de importacao
                    _fechar_dialog(app, api, processo_id)
                    
                    api.log_progress(processo_id, "Etapa 3 concluida: Arquivo importado com sucesso.")
                    return True
        
        # Heartbeat a cada 30s
        elapsed = int(time.time() - start_time)
        if elapsed > 0 and elapsed % 30 == 0:
            api.log_progress(processo_id, f"Importacao em andamento ({elapsed}s)...")
    
    raise TimeoutError(f"Importacao nao concluiu em {timeout} segundos.")


def _fechar_dialog(app, api, processo_id):
    """Fecha o dialog de importacao clicando em Fechar ou ESC."""
    api.log_progress(processo_id, "Fechando dialog de importacao...")
    time.sleep(0.5)
    
    for w in app.windows():
        for ctrl in w.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                ctrl.click_input()
                time.sleep(0.5)
                return
    
    # Fallback ESC
    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
