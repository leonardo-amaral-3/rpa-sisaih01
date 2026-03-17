import time

def wait_for_window(app, title_regex, timeout=30, raise_on_timeout=True):
    """Aguarda uma janela especifica aparecer e retorna a janela."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Tenta conectar e encontrar a janela
            win = app.window(title_re=title_regex)
            if win.exists() and win.is_visible():
                return win
        except Exception:
            pass
        time.sleep(1)
        
    if raise_on_timeout:
        raise TimeoutError(f"Janela '{title_regex}' não apareceu após {timeout} segundos.")
    return None

def wait_for_control_enabled(window, control_selector, timeout=60, raise_on_timeout=True):
    """Aguarda um botão/controle especifico ficar focado ou clicável (ex: aguardando importação carregar)."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            ctrl = window.child_window(**control_selector)
            if ctrl.exists() and ctrl.is_enabled():
                return ctrl
        except Exception:
            pass
        time.sleep(2)
        
    if raise_on_timeout:
        raise TimeoutError(f"Controle {control_selector} não ficou disponível após {timeout}s.")
    return None
