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


def _fechar_popups_pos_login(app, api, processo_id):
    """
    Fecha popups que aparecem apos o login (ex: copia de seguranca, avisos).
    """
    for attempt in range(5):
        found_popup = False
        for w in app.windows():
            title = w.window_text()
            cls = w.class_name()
            # Pular janelas principais
            if cls in ('TFrmPrincipal', 'TApplication', 'TFrmLogin'):
                continue
            if not title:
                continue
            # Detectar popups de confirmacao/aviso
            if any(kw in title.lower() for kw in ['copia', 'confirm', 'aviso', 'aten']):
                api.log_progress(processo_id, f"Popup pos-login detectado: '{title}'. Fechando...")
                found_popup = True
                # Tentar clicar em Nao/No/Cancelar
                clicked = False
                for ctrl in w.descendants():
                    txt = ctrl.window_text()
                    if any(kw in txt for kw in ['Não', 'Nao', 'No', 'Cancelar', 'Cancel']):
                        try:
                            ctrl.click_input()
                            clicked = True
                            break
                        except Exception:
                            pass
                if not clicked:
                    # Tentar fechar com ESC ou Enter (para "OK")
                    try:
                        w.set_focus()
                        time.sleep(0.2)
                        keyboard.send_keys("{ESCAPE}")
                    except Exception:
                        keyboard.send_keys("{ENTER}")
                time.sleep(1)
                break

            # Detectar dialogs genericos (#32770 = MessageBox do Windows)
            if cls == '#32770':
                api.log_progress(processo_id, f"MessageBox pos-login: '{title}'. Fechando...")
                found_popup = True
                try:
                    w.set_focus()
                    time.sleep(0.2)
                    # Clicar em Nao se existir, senao OK
                    clicked = False
                    for ctrl in w.descendants():
                        txt = ctrl.window_text()
                        if any(kw in txt for kw in ['&Não', '&Nao', '&No', 'Não', 'Nao']):
                            try:
                                ctrl.click_input()
                                clicked = True
                                break
                            except Exception:
                                pass
                    if not clicked:
                        keyboard.send_keys("{ESCAPE}")
                except Exception:
                    keyboard.send_keys("{ESCAPE}")
                time.sleep(1)
                break

        if not found_popup:
            break


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

    # Aguardar login processar
    time.sleep(3)

    # Fechar popups pos-login (ex: copia de seguranca)
    _fechar_popups_pos_login(app, api, processo_id)

    # Verificar se login foi bem sucedido (janela principal existe)
    main_found = False
    for attempt in range(10):
        for w in app.windows():
            if w.class_name() == 'TFrmPrincipal':
                main_found = True
                break
        if main_found:
            break
        time.sleep(1)

    if not main_found:
        raise Exception("Login falhou: janela principal (TFrmPrincipal) nao encontrada.")

    api.log_progress(processo_id, "Etapa 1b concluida: Login realizado.")
