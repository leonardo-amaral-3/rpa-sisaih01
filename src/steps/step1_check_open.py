import os
import time
from pywinauto.application import Application
from pywinauto.controls.common_controls import ToolbarWrapper
from pywinauto import keyboard
import warnings
warnings.filterwarnings("ignore")


def find_main_toolbar(win):
    """Encontra a toolbar principal (a com 7 botoes = menu CADASTRO/PRODUCAO/etc)."""
    for ctrl in win.descendants():
        if ctrl.class_name() == 'TToolBar':
            try:
                tb = ToolbarWrapper(ctrl.handle)
                if tb.button_count() == 7:
                    return tb
            except Exception:
                continue
    raise Exception("Toolbar principal (menu) nao encontrada na janela do SISAIH01.")


def click_menu(win, toolbar, button_index, menu_item_text=None):
    """
    Clica em um botao da toolbar (menu principal) e opcionalmente
    seleciona um item do popup menu via teclado.
    
    button_index: indice do botao na toolbar (0=CADASTRO, 1=PRODUCAO, 2=PROCESSAMENTO...)
    menu_item_text: texto do item no popup menu (ex: 'HOSPITAL')
    """
    win.set_focus()
    time.sleep(0.3)
    
    # Clicar no botao do menu principal
    btn = toolbar.button(button_index)
    btn.click()
    time.sleep(0.5)
    
    if menu_item_text:
        # Usar teclado pra navegar no popup menu aberto
        # O item desejado esta no submenu. Usamos as setas + Enter.
        # Mapeamento dos itens do submenu CADASTRO:
        #   HOSPITAL = 1o item (0 vezes DOWN + ENTER)
        #   PROFISSIONAIS = 2o item (1x DOWN + ENTER)
        #   TERCEIROS = 3o item (2x DOWN + ENTER)
        #   OPERADORES = 4o item (3x DOWN + ENTER)
        
        menu_items_map = {
            "HOSPITAL": 0,
            "PROFISSIONAIS": 1,
            "TERCEIROS": 2,
            "OPERADORES": 3,
        }
        
        downs = menu_items_map.get(menu_item_text.upper(), 0)
        
        for _ in range(downs):
            keyboard.send_keys("{DOWN}")
            time.sleep(0.1)
        
        keyboard.send_keys("{ENTER}")
        time.sleep(1)


def execute(config, api, processo_id):
    """
    Etapa 1: Verificar se o SISAIH01 esta rodando, se nao, abri-lo.
    Retorna a instancia do Application, a Janela Principal e a Toolbar Principal.
    """
    api.log_progress(processo_id, "Iniciando Etapa 1: Verificar/Abrir SISAIH01")
    
    exec_path = config["sisaih"]["executable_path"]
    app = Application(backend="win32")
    
    # 1. Tentar conectar a uma instancia existente
    try:
        app.connect(path=exec_path, timeout=5)
        api.log_progress(processo_id, "SISAIH01 ja estava rodando, conectando...")
    except Exception:
        api.log_progress(processo_id, f"Iniciando nova instancia: {exec_path}")
        if not os.path.exists(exec_path):
            raise FileNotFoundError(f"Executavel nao encontrado: {exec_path}")
        app.start(exec_path)
        time.sleep(5)

    # 2. Encontrar a janela PRINCIPAL pela class TFrmPrincipal (nao top_window pq
    #    pode ter formularios abertos na frente como 'Cadastro de Hospital')
    main_window = None
    for w in app.windows():
        if w.class_name() == 'TFrmPrincipal':
            main_window = w
            break
    
    if not main_window:
        # Fallback: usar top_window
        main_window = app.top_window()
    
    api.log_progress(processo_id, f"Janela principal: '{main_window.window_text()}' (Class: {main_window.class_name()})")
    
    # 3. Fechar qualquer formulario que esteja aberto na frente
    # Lista abrangente de keywords para pegar qualquer dialog residual do SISAIH01
    residual_keywords = [
        'Cadastro', 'Importa', 'Consist', 'Hospital', 'Produc',
        'Manutenc', 'Processamento', 'Seleciona',
    ]
    for w in app.windows():
        title = w.window_text()
        cls = w.class_name()
        if cls not in ('TFrmPrincipal', 'TApplication') and title and \
           any(kw.lower() in title.lower() for kw in residual_keywords):
            api.log_progress(processo_id, f"Fechando formulario residual: '{title}' ({cls})")
            try:
                w.close()
                time.sleep(0.5)
            except Exception:
                keyboard.send_keys("{ESC}")
                time.sleep(0.5)
    
    # 4. Encontrar a toolbar principal (menu)
    toolbar = find_main_toolbar(main_window)
    api.log_progress(processo_id, f"Toolbar principal encontrada com {toolbar.button_count()} botoes.")
    
    try:
        main_window.set_focus()
    except Exception:
        pass

    api.log_progress(processo_id, "Etapa 1 concluida: SISAIH01 aberto e pronto.")
    return app, main_window, toolbar
