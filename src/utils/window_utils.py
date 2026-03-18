import time
from pywinauto import keyboard
from pywinauto import mouse as pwa_mouse


def fechar_dialog_robusto(app, api, processo_id, dialog_keywords, step_label, max_retries=3):
    """
    Fecha um dialog Delphi de forma robusta, verificando se realmente fechou.

    dialog_keywords: lista de keywords para identificar o dialog pelo titulo
    step_label: label para log (ex: 'Etapa 4', 'Etapa 5')
    """
    api.log_progress(processo_id, f"Fechando dialog ({step_label})...")
    time.sleep(0.5)

    for attempt in range(max_retries):
        target_dialog = _find_dialog(app, dialog_keywords)
        if not target_dialog:
            api.log_progress(processo_id, f"{step_label} concluida com sucesso.")
            return True

        if attempt > 0:
            api.log_progress(processo_id,
                f"Dialog ainda aberto, tentativa {attempt + 1}/{max_retries}...", level="DEBUG")

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

        # Tentativa 2: Clicar no Fechar por coordenada usando o rect do DIALOG
        # Os botoes ficam no rodape do dialog. Fechar eh o mais à direita.
        if not fechar_clicked:
            fechar_clicked = _click_fechar_by_dialog_rect(target_dialog, api, processo_id)

        # Tentativa 3: WM_CLOSE via pywinauto .close()
        if not fechar_clicked:
            try:
                target_dialog.close()
                fechar_clicked = True
                api.log_progress(processo_id, "Dialog fechado via WM_CLOSE.", level="DEBUG")
            except Exception:
                pass

        # Tentativa 4: Alt+F4
        if not fechar_clicked:
            try:
                target_dialog.set_focus()
                time.sleep(0.2)
            except Exception:
                pass
            keyboard.send_keys("%{F4}")
            api.log_progress(processo_id, "Alt+F4 enviado.", level="DEBUG")

        time.sleep(1)

        if not _find_dialog(app, dialog_keywords):
            api.log_progress(processo_id, f"{step_label} concluida com sucesso.")
            return True

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


def _click_fechar_by_dialog_rect(dialog, api, processo_id):
    """
    Clica no botao Fechar usando o retangulo do dialog como referencia.
    Em dialogs Delphi, os botoes ficam no rodape. Fechar eh o mais a direita.
    Layout tipico: [Acao] [Imprimir] [Fechar] no rodape do dialog.
    """
    try:
        dlg_rect = dialog.rectangle()
        api.log_progress(processo_id,
            f"Dialog rect: ({dlg_rect.left},{dlg_rect.top},{dlg_rect.right},{dlg_rect.bottom})",
            level="DEBUG")

        # Fechar fica no canto inferior direito do dialog
        # ~35px acima da borda inferior, ~80px da borda direita
        cx = dlg_rect.right - 80
        cy = dlg_rect.bottom - 35

        api.log_progress(processo_id, f"Fechar por coordenada (dialog rect): ({cx}, {cy})", level="DEBUG")
        pwa_mouse.click(coords=(cx, cy))
        return True
    except Exception as e:
        api.log_progress(processo_id, f"Erro ao clicar Fechar por dialog rect: {e}", level="DEBUG")
        return False


def click_button_by_dialog_rect(dialog, api, processo_id, position="left"):
    """
    Clica em um botao no rodape do dialog usando o rect do dialog como referencia.

    position: "left" = primeiro botao (acao principal: Consistir, Apurar, Exportar)
              "right" = ultimo botao (Fechar)
    """
    try:
        dlg_rect = dialog.rectangle()
        dlg_width = dlg_rect.right - dlg_rect.left

        # Y: botoes ficam ~35px acima da borda inferior
        cy = dlg_rect.bottom - 35

        if position == "left":
            # Primeiro botao: ~60px da borda esquerda
            cx = dlg_rect.left + 60
        elif position == "center":
            # Botao do meio
            cx = (dlg_rect.left + dlg_rect.right) // 2
        else:  # "right"
            # Ultimo botao (Fechar): ~80px da borda direita
            cx = dlg_rect.right - 80

        api.log_progress(processo_id,
            f"Clique por dialog rect ({position}): ({cx}, {cy}) "
            f"[dialog=({dlg_rect.left},{dlg_rect.top},{dlg_rect.right},{dlg_rect.bottom})]",
            level="DEBUG")
        pwa_mouse.click(coords=(cx, cy))
        return True
    except Exception as e:
        api.log_progress(processo_id, f"Erro ao clicar botao por dialog rect: {e}", level="DEBUG")
        return False
