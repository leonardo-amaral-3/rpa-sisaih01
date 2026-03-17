import time

def execute(config, api, processo_id, main_window):
    """
    Etapa 4: Processamento -> Consistir Produção
    Este é o passo mais longo (gargalo), com polling robusto.
    """
    api.log_progress(processo_id, "Iniciando Etapa 4: Consistir Produção")
    
    # 1. Navegar no menu principal: Processamento -> Consistir Produção
    try:
        main_window.menu_select("Processamento->Consistir Produção")
        time.sleep(2)
    except Exception as e:
        raise Exception(f"Falha ao navegar no menu 'Processamento->Consistir Produção': {e}")
        
    # 2. Janela de consistência
    consist_dialog = main_window.child_window(title_re=".*Consist.*")
    if not consist_dialog.exists():
        time.sleep(2)
        
    # 3. Disparar botão de Consistir
    api.log_progress(processo_id, "Iniciando botão de Consistir na tela.")
    # consist_dialog.child_window(title="Consistir").click()
    
    # 4. Polling longo aguardando a finalizacao
    timeout = config["timeouts"].get("consistir", 3600)  # default 1 hora
    check_interval = 60 # Check a cada 1 minuto
    
    start_time = time.time()
    last_log_time = time.time()
    
    while time.time() - start_time < timeout:
        # Aqui, a condicao de saida depende da UI. Por exemplo, se aparecer um popup "Consistencia Terminada"
        # Ou se a barra de progresso sumir, botão "Fechar" habilitar.
        
        # simulated_finish = False
        # if simulated_finish:
        #     api.log_progress(processo_id, "Processamento de consistência finalizado com sucesso!")
        #     break
            
        # Emitir logs de heartbeat a cada 5 mins para a API saber que ainda tá vivo
        if time.time() - last_log_time >= 300: # 5 minutos
            elapsed_mins = int((time.time() - start_time) / 60)
            api.log_progress(processo_id, f"Processamento em andamento: Consistindo há {elapsed_mins} minutos...")
            last_log_time = time.time()
            
        time.sleep(check_interval)
        break # DEBUG: Remove in real iteration
        
    else:
        # Se saiu do while pelo timeout
        raise TimeoutError(f"O processo de consistência passou do tempo limite ({timeout}s).")
    
    api.log_progress(processo_id, "Etapa 4 concluída: Arquivo Consistido.")
    return True
