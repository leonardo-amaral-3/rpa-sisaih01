import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse


def fechar_dialog_robusto(app, api, processo_id, dialog_keywords, step_label, max_retries=3):
    """
    Fecha um dialog Delphi de forma robusta, verificando se realmente fechou.

    dialog_keywords: lista de keywords para identificar o dialog pelo titulo (ex: ['Consist', 'Produ'])
    step_label: label para log (ex: 'Etapa 4', 'Etapa 5')
    """
    api.log_progress(processo_id, f"Fechando dialog ({step_label})...")
    time.sleep(0.5)

    for attempt in range(max_retries):
        # Encontrar o dialog alvo
        target_dialog = _find_dialog(app, dialog_keywords)
        if not target_dialog:
            api.log_progress(processo_id, f"{step_label} concluida com sucesso.")
            return True

        if attempt > 0:
            api.log_progress(processo_id,
                f"Dialog ainda aberto, tentativa {attempt + 1}/{max_retries}...", level="DEBUG")

        # Focar no dialog antes de tentar fechar
        try:
            target_dialog.set_focus()
            time.sleep(0.3)
        except Exception:
            pass

        # Tentativa 1: Botao Fechar com HWND
        fechar_clicked = False
        for ctrl in target_dialog.descendants():
            txt = ctrl.window_text()
            cls = ctrl.class_name()
            if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                try:
                    ctrl.click_input()
                    fechar_clicked = True
                    api.log_progress(processo_id, "Fechar clicado (HWND).", level="DEBUG")
                except Exception:
                    pass
                break

        if not fechar_clicked:
            # Tentativa 2: Coordenada no TPanel (3a zona = Fechar)
            fechar_clicked = _click_fechar_by_panel(target_dialog, api, processo_id)

        if not fechar_clicked:
            # Tentativa 3: WM_CLOSE via pywinauto .close()
            try:
                target_dialog.close()
                fechar_clicked = True
                api.log_progress(processo_id, "Dialog fechado via WM_CLOSE.", level="DEBUG")
            except Exception:
                pass

        if not fechar_clicked:
            # Tentativa 4: Alt+F4
            try:
                target_dialog.set_focus()
                time.sleep(0.2)
            except Exception:
                pass
            keyboard.send_keys("%{F4}")
            api.log_progress(processo_id, "Alt+F4 enviado.", level="DEBUG")

        time.sleep(1)

        # Verificar se fechou
        if not _find_dialog(app, dialog_keywords):
            api.log_progress(processo_id, f"{step_label} concluida com sucesso.")
            return True

        # Se ainda nao fechou, tentar ESC (pode ter popup de confirmacao)
        keyboard.send_keys("{ESC}")
        time.sleep(0.5)

    # Ultimo recurso: ESC multiplo
    for _ in range(3):
        keyboard.send_keys("{ESC}")
        time.sleep(0.3)

    api.log_progress(processo_id, f"{step_label} concluida (dialog pode ainda estar aberto).", level="WARNING")
    return False


def _find_dialog(app, keywords):
    """Encontra um dialog pelo titulo usando keywords."""
    for w in app.windows():
        title = w.window_text()
        if title and all(kw.lower() in title.lower() for kw in keywords):
            return w
    return None


def _click_fechar_by_panel(dialog, api, processo_id):
    """Clica no botao Fechar por coordenada usando TPanel como referencia."""
    button_panel = None
    progress_bar = None

    for ctrl in dialog.descendants():
        cls = ctrl.class_name()
        if cls == 'TProgressBar':
            progress_bar = ctrl
        if cls == 'TPanel':
            try:
                r = ctrl.rectangle()
                height = r.bottom - r.top
                if 30 <= height <= 60:
                    button_panel = ctrl
            except Exception:
                pass

    if not button_panel:
        return False

    p_rect = button_panel.rectangle()
    panel_width = p_rect.right - p_rect.left
    btn_zone = panel_width // 3

    if progress_bar:
        pb_rect = progress_bar.rectangle()
        cy = (p_rect.top + pb_rect.top) // 2
    else:
        cy = (p_rect.top + p_rect.bottom) // 2

    # Fechar eh o 3o botao (ultima zona)
    cx = p_rect.left + btn_zone * 2 + btn_zone // 2

    api.log_progress(processo_id, f"Fechar por coordenada: ({cx}, {cy})", level="DEBUG")
    pwa_mouse.click(coords=(cx, cy))
    return True
