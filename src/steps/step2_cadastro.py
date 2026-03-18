import time
from pywinauto.application import Application

# Indices dos botoes na toolbar principal
MENU_CADASTRO = 0
MENU_PRODUCAO = 1
MENU_PROCESSAMENTO = 2
MENU_RELATORIOS = 3
MENU_CONSULTA = 4
MENU_AJUDA = 5


def execute(config, api, processo_id, app, main_window, toolbar, hospital_data):
    """
    Etapa 2: CADASTRO -> HOSPITAL -> Preencher formulario -> Gravar [F5]
    """
    api.log_progress(processo_id, "Iniciando Etapa 2: Cadastro de Hospital")
    
    # 1. Abrir formulario via menu CADASTRO -> HOSPITAL
    from steps.step1_check_open import click_menu
    click_menu(main_window, toolbar, MENU_CADASTRO, "HOSPITAL")
    
    api.log_progress(processo_id, "Menu CADASTRO > HOSPITAL clicado. Aguardando formulario...")
    time.sleep(3)  # Dar mais tempo pro formulario carregar
    
    # 2. Coletar os controles TDBEdit e TDBComboBox
    # O formulario pode estar como child da janela principal ou como janela separada
    # Buscamos em TODAS as janelas do app
    edits = []
    combos = []
    
    for w in app.windows():
        for ctrl in w.descendants():
            cls = ctrl.class_name()
            if cls == 'TDBEdit':
                edits.append(ctrl)
            elif cls == 'TDBComboBox':
                combos.append(ctrl)
    
    # 3. Ordenar por posicao Y (top) e depois X (left), como a leitura de um formulario
    edits.sort(key=lambda c: (c.rectangle().top, c.rectangle().left))
    
    api.log_progress(processo_id, f"Encontrados {len(edits)} campos Edit e {len(combos)} ComboBox.")
    
    # Debug: printar campos ordenados para validar mapeamento
    for i, e in enumerate(edits):
        print(f"    [{i}] Text: '{e.window_text()}' | Rect: {e.rectangle()}")
    
    # 4. Mapear campos pelo indice (ordenados por Y, X — da esquerda-direita, cima-baixo)
    # Baseado no formulario real do SISAIH01:
    #   [0]  CNES           (1a linha, esquerda)
    #   [1]  Nome           (1a linha, direita) 
    #   [2]  Cod Logr       (2a linha, esquerda)
    #   [3]  Logradouro     (2a linha, direita)
    #   [4]  Numero         (3a linha, esquerda)
    #   [5]  Complemento    (3a linha, direita)
    #   [6]  Bairro         (4a linha, esquerda)
    #   [7]  Telefone       (4a linha, direita)
    #   [8]  CEP            (5a linha, esquerda)
    #   [9]  Municipio      (5a linha, centro)
    #   [10] Orgao Emissor  (6a linha, esquerda)
    #   [11] CPF Diretor    (7a linha, esquerda)
    #   [12] CNS Diretor    (7a linha, direita)
    #   [13] Nome Diretor   (8a linha)
    # ComboBox:
    #   [0]  Esfera Admin.  (6a linha, direita)
    
    field_map = [
        ("cnes", "CNES"),
        ("nome", "Nome"),
        ("codLogradouro", "Cod Logradouro"),
        ("logradouro", "Logradouro"),
        ("numero", "Numero"),
        ("complemento", "Complemento"),
        ("bairro", "Bairro"),
        ("telefone", "Telefone"),
        ("cep", "CEP"),
        ("municipio", "Municipio"),
        ("orgaoEmissor", "Orgao Emissor"),
        ("cpfDiretorClinico", "CPF Diretor Clinico"),
        ("cnsDiretorClinico", "CNS Diretor Clinico"),
        ("nomeDiretor", "Nome do Diretor"),
    ]
    
    # 5. Preencher os campos Edit
    for i, (key, label) in enumerate(field_map):
        if i >= len(edits):
            api.log_progress(processo_id, f"[Warning] Indice {i} ({label}) fora do range de edits ({len(edits)})", level="WARNING")
            break
            
        value = hospital_data.get(key, "")
        if value:
            try:
                edit_ctrl = edits[i]
                edit_ctrl.click_input()  # Foca no campo
                time.sleep(0.1)
                edit_ctrl.set_edit_text(value)  # Limpa e preenche
                api.log_progress(processo_id, f"  Campo '{label}' preenchido: {value}")
            except Exception as e:
                api.log_progress(processo_id, f"[Warning] Falha ao preencher '{label}': {e}", level="WARNING")
    
    # 6. Preencher Esfera Administrativa (ComboBox)
    esfera = hospital_data.get("esferaAdministrativa", "")
    if esfera and combos:
        try:
            combo = combos[0]  # Unico ComboBox no formulario
            combo.select(esfera)
            api.log_progress(processo_id, f"  Campo 'Esfera Administrativa' selecionado: {esfera}")
        except Exception as e:
            api.log_progress(processo_id, f"[Warning] Falha no ComboBox Esfera: {e}", level="WARNING")
    
    # 7. Salvar: pressionar F5 (Gravar)
    api.log_progress(processo_id, "Salvando cadastro (F5)...")
    from pywinauto import keyboard as kb
    kb.send_keys("{F5}")
    time.sleep(2)
    
    # 8. Fechar o formulario de cadastro
    api.log_progress(processo_id, "Fechando formulario de cadastro...")
    from utils.window_utils import fechar_dialog_robusto
    fechar_dialog_robusto(app, api, processo_id, ['Hospital'], 'Etapa 2')

    api.log_progress(processo_id, "Etapa 2 concluida: Cadastro de Hospital salvo com sucesso.")
    return True
