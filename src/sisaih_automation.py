import argparse
import json
import os
import re
import time
import yaml
import traceback

from pywinauto import keyboard

from utils.api_client import ApiClient
from steps import step1_check_open, step2_cadastro, step3_importar, step4_consistir, step5_apurar, step6_exportar_sihd
from vigilante import Vigilante

def load_config(config_path="config.yaml"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, config_path)
    with open(full_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _fechar_dialogs_residuais(app, api, processo_id, main_window):
    """
    Fecha todos os dialogs/janelas abertas que nao sao a janela principal do SISAIH01.
    Funciona como rede de seguranca entre steps.
    """
    main_handle = main_window.handle
    fechados = 0

    for attempt in range(3):
        found_extra = False
        for w in app.windows():
            # Pular janela principal (por handle, nao por titulo)
            if w.handle == main_handle:
                continue

            title = w.window_text()
            if not title:
                continue

            # Pular janelas do sistema / fantasma
            if 'GDI+' in title or 'Default IME' in title:
                continue

            # Pular janelas com rect invalido (0,0,0,0) — fantasmas
            try:
                r = w.rectangle()
                if r.right - r.left <= 1 or r.bottom - r.top <= 1:
                    continue
            except Exception:
                continue

            # Pular se o titulo contem SISAIH e parece ser a janela principal
            if 'SISAIH01' in title and 'Programa' in title:
                continue

            found_extra = True
            api.log_progress(processo_id,
                f"Dialog residual: '{title}'. Fechando...", level="DEBUG")

            # Tentar clicar Fechar (HWND)
            clicked = False
            for ctrl in w.descendants():
                txt = ctrl.window_text()
                cls = ctrl.class_name()
                if 'Fechar' in txt and ('Button' in cls or 'Btn' in cls):
                    try:
                        ctrl.click_input()
                        clicked = True
                    except Exception:
                        pass
                    break

            # Fallback: coordenada no canto inferior direito
            if not clicked:
                from utils.window_utils import _click_fechar_by_dialog_rect
                _click_fechar_by_dialog_rect(w, api, processo_id)

            time.sleep(0.5)
            fechados += 1

        if not found_extra:
            break

    if fechados > 0:
        api.log_progress(processo_id, f"Fechados {fechados} dialog(s) residual(is).")

def run_automation(processo_id, file_path, hospital_data, is_local_mode):
    config = load_config()
    api = ApiClient(config, is_local_mode)
    
    api.log_progress(processo_id, "--- Iniciando Automacao SISAIH01 ---", level="INFO")
    vigilante = None
    
    try:
        # Step 1: Verificar/Abrir Aplicacao (retorna app, window, e toolbar)
        app, main_window, toolbar = step1_check_open.execute(config, api, processo_id)
        
        # Iniciar a thread vigilante
        vigilante = Vigilante(app, api, processo_id)
        vigilante.start_watch()
        
        # Step 2: Cadastros -> Hospitais
        step2_cadastro.execute(config, api, processo_id, app, main_window, toolbar, hospital_data)
        _fechar_dialogs_residuais(app, api, processo_id, main_window)

        if vigilante.error_detected:
            raise Exception(f"Vigilante abortou execucao: {vigilante.error_detected}")

        # Step 3: Manutencao -> Importar -> Producao
        step3_importar.execute(config, api, processo_id, app, main_window, toolbar, file_path)
        _fechar_dialogs_residuais(app, api, processo_id, main_window)

        # Step 4: Processamento -> Consistir Producao
        step4_consistir.execute(config, api, processo_id, app, main_window, toolbar)
        _fechar_dialogs_residuais(app, api, processo_id, main_window)

        # Step 5: Processamento -> Apurar Previa
        step5_apurar.execute(config, api, processo_id, app, main_window, toolbar)
        _fechar_dialogs_residuais(app, api, processo_id, main_window)

        # Step 6: Processamento -> Exportar para SIHD
        step6_exportar_sihd.execute(config, api, processo_id, app, main_window, toolbar, hospital_data, file_path)
        _fechar_dialogs_residuais(app, api, processo_id, main_window)

        api.notify_completion(processo_id, status="COMPLETED")
        
    except Exception as e:
        error_details = traceback.format_exc()
        api.log_progress(processo_id, f"Falha Critica: {e}", level="ERROR")
        api.log_progress(processo_id, error_details, level="DEBUG")
        api.notify_completion(processo_id, status="FAILED", error_message=str(e))
        
    finally:
        if vigilante:
            vigilante.stop_watch()
        api.log_progress(processo_id, "--- Automacao SISAIH01 Encerrada ---", level="INFO")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automacao SISAIH01 RPA Worker")
    parser.add_argument("--local", action="store_true", help="Modo local sem chamadas HTTP")
    parser.add_argument("--processo_id", default="local_test_id_123")
    parser.add_argument("--mock_data", type=str, help="JSON string com dados do hospital")
    parser.add_argument("--file_path", default="C:\\test_file.txt")
    
    args = parser.parse_args()
    
    hospital_data = {
        "cnes": "227023-4",
        "nome": "GETULIO VARGAS",
        "logradouro": "ROMEU CAETANO GUIDA",
        "numero": "22",
        "bairro": "JOCA",
        "telefone": "2649-2006",
        "cep": "21020-124",
        "orgaoEmissor": "M330080001",
        "esferaAdministrativa": "PUBLICO",
        "cpfDiretorClinico": "24561770704",
        "cnsDiretorClinico": "705001439978854",
        "nomeDiretor": "JORGE LUIZ LINCHTENFELS RIBEIRO"
    }

    if args.mock_data:
        hospital_data = json.loads(args.mock_data)

    run_automation(args.processo_id, args.file_path, hospital_data, args.local)
