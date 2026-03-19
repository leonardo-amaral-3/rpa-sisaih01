import time
from pywinauto import keyboard


def _calcular_apresentacao(competencia):
    """
    Calcula a apresentacao (competencia + 1 mes).
    competencia vem como 'YYYYMM' (ex: '202602').
    Retorna no formato 'MM/YYYY' (ex: '03/2026').
    """
    ano = int(competencia[:4])
    mes = int(competencia[4:6])
    mes += 1
    if mes > 12:
        mes = 1
        ano += 1
    return f"{mes:02d}/{ano}"


def execute(config, api, processo_id, app, competencia):
    """
    Etapa 1b: Login no SISAIH01.
    Preenche usuario, senha e apresentacao na tela de autenticacao.
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

    # Preencher Usuario
    try:
        edit_usuario = login_window.child_window(class_name="TEdit", found_index=0)
        edit_usuario.set_focus()
        edit_usuario.set_edit_text("MESTRE")
    except Exception:
        keyboard.send_keys("{TAB}")
        time.sleep(0.2)
        keyboard.send_keys("MESTRE")

    time.sleep(0.3)

    # Preencher Senha
    try:
        edit_senha = login_window.child_window(class_name="TEdit", found_index=1)
        edit_senha.set_focus()
        edit_senha.set_edit_text("MESTRE")
    except Exception:
        keyboard.send_keys("{TAB}")
        time.sleep(0.2)
        keyboard.send_keys("MESTRE")

    time.sleep(0.3)

    # Preencher Apresentacao
    try:
        edit_apresentacao = login_window.child_window(class_name="TMaskEdit", found_index=0)
        edit_apresentacao.set_focus()
        edit_apresentacao.set_edit_text(apresentacao)
    except Exception:
        try:
            edit_apresentacao = login_window.child_window(class_name="TEdit", found_index=2)
            edit_apresentacao.set_focus()
            edit_apresentacao.set_edit_text(apresentacao)
        except Exception:
            keyboard.send_keys("{TAB}")
            time.sleep(0.2)
            keyboard.send_keys(apresentacao)

    time.sleep(0.3)

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

    time.sleep(2)
    api.log_progress(processo_id, "Etapa 1b concluida: Login realizado.")
