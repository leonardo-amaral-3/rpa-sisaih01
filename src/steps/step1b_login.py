import time
from pywinauto import keyboard


def _calcular_apresentacao(competencia):
    """
    Calcula a apresentacao (competencia + 1 mes).
    competencia vem como 'YYYYMM' (ex: '202602').
    Retorna apenas digitos 'MMYYYY' (ex: '032026') para o campo mascarado.
    """
    ano = int(competencia[:4])
    mes = int(competencia[4:6])
    mes += 1
    if mes > 12:
        mes = 1
        ano += 1
    return f"{mes:02d}{ano}"


def execute(config, api, processo_id, app, competencia):
    """
    Etapa 1b: Login no SISAIH01.
    Preenche usuario, senha e apresentacao na tela de autenticacao.
    Usa navegacao por teclado (TAB) e Ctrl+A para limpar campos.
    """
    api.log_progress(processo_id, "Iniciando Etapa 1b: Login no SISAIH01")

    apresentacao = _calcular_apresentacao(competencia)
    api.log_progress(processo_id, f"Competencia: {competencia} -> Apresentacao: {apresentacao}")

    # Encontrar a janela de autenticacao
    login_window = None
    for attempt in range(10):
        for w in app.windows():
            title = w.window_text()
            if 'Autentica' in title or 'Login' in title:
                login_window = w
                break
        if login_window:
            break
        time.sleep(1)

    if not login_window:
        api.log_progress(processo_id, "Tela de login nao encontrada, SISAIH01 pode ja estar logado.")
        return

    login_window.set_focus()
    time.sleep(0.5)

    # Clicar no campo Usuario (primeiro TEdit)
    try:
        edit_usuario = login_window.child_window(class_name="TEdit", found_index=0)
        edit_usuario.click_input()
    except Exception:
        pass
    time.sleep(0.3)

    # Limpar e preencher Usuario
    keyboard.send_keys("^a")
    time.sleep(0.1)
    keyboard.send_keys("MESTRE", with_spaces=True)
    time.sleep(0.3)

    # TAB para Senha
    keyboard.send_keys("{TAB}")
    time.sleep(0.3)

    # Limpar e preencher Senha
    keyboard.send_keys("^a")
    time.sleep(0.1)
    keyboard.send_keys("MESTRE", with_spaces=True)
    time.sleep(0.3)

    # TAB para Apresentacao
    keyboard.send_keys("{TAB}")
    time.sleep(0.3)

    # Limpar campo (Home pra ir pro inicio, Shift+End pra selecionar tudo)
    keyboard.send_keys("{HOME}")
    time.sleep(0.1)
    keyboard.send_keys("+{END}")
    time.sleep(0.1)

    # Digitar apenas os digitos (MMYYYY) - o campo mascarado insere a barra
    keyboard.send_keys(apresentacao, with_spaces=True)
    time.sleep(0.5)

    # Clicar em Entrar
    try:
        btn_entrar = login_window.child_window(title="Entrar", class_name="TBitBtn")
        btn_entrar.click_input()
    except Exception:
        try:
            btn_entrar = login_window.child_window(title_re=".*Entrar.*")
            btn_entrar.click_input()
        except Exception:
            keyboard.send_keys("{ENTER}")

    # Aguardar login processar e janela principal carregar
    time.sleep(3)

    # Verificar se login foi bem sucedido (janela de login sumiu)
    for attempt in range(10):
        login_still_open = False
        for w in app.windows():
            title = w.window_text()
            if 'Autentica' in title or 'Login' in title:
                login_still_open = True
                break
        if not login_still_open:
            break
        time.sleep(1)

    if login_still_open:
        raise Exception("Login falhou: janela de autenticacao ainda aberta.")

    api.log_progress(processo_id, "Etapa 1b concluida: Login realizado.")
