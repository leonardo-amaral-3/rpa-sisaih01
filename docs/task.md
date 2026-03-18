# Checklist de Implementação: Conversão SISAIH01 → SIHD

Este documento acompanha o progresso da implementação da arquitetura definida em `implementation_plan.md`.

## Fase 1: RPA Python (PoC Local)
- [x] Criar estrutura do projeto Python (`sihd-converter`)
- [x] Implementar utilitários base (`api_client.py`, `wait.py`)
- [x] Step 1: `step1_check_open.py` — ✅ Testado na VM, conecta via `TFrmPrincipal`
- [x] Step 2: `step2_cadastro.py` — ✅ Testado na VM, preenche 14 TDBEdit + 1 TDBComboBox
- [x] Step 3: `step3_importar.py` — ✅ Testado na VM, importa arquivo via TBitBtn + fallback por classe
- [x] Step 4: `step4_consistir.py` — ✅ Testado na VM, mesma detecção robusta de botões Delphi
- [x] Thread Vigilante (`vigilante.py`)
- [x] Orquestrador (`sisaih_automation.py`)
- [ ] Padronização de arquivos (input/output paths) integrada no Worker

## Fase 2: Integração Orquestrador (Worker)
- [ ] Implementar consumo real do AWS SQS no Worker Python (`worker.py`)
- [ ] Implementar integração com S3 (`utils/s3_handler.py`)
- [ ] Implementar envio real de Logs para a API (`utils/api_client.py`)
- [ ] Implementar Auto-Shutdown inteligente (`utils/ec2_manager.py`)
- [ ] Atualizar script principal para consumir a fila até esvaziar e desligar a máquina

## Fase 3: Backend API + Banco de Dados
- [ ] Criar migração no banco: Status, Datas, S3 Key e Erros.
- [ ] Implementar endpoint `POST /processo/:id/encaminhar-secretaria`:
  - Enviar mensagem formatada para SQS
  - Disparar `StartInstances` via AWS SDK para ligar a EC2
- [ ] Implementar endpoint `GET /processo/:id/encaminhamento-status`
- [ ] Implementar endpoint `POST /processo/:id/rpa-logs`
- [ ] Implementar endpoint de Callback EC2 (`POST /processo/:id/conversion-callback`)
- [ ] Implementar endpoint `GET /processo/:id/download-sihd`

## Fase 4: Frontend (Web)
- [ ] Adicionar botão "Encaminhar para Secretaria" na interface de Processos
- [ ] Mapear dados do hospital e enviar no payload
- [ ] Implementar polling de `encaminhamento-status`
- [ ] Implementar exibição dos logs enviados pelo RPA na interface
- [ ] Tratar estados: Carregando, Concluído (botão de download), Erro (exibir log de falha)

## Fase 5: Infraestrutura (AWS CDK)
- [ ] Subir IAM Role da arquitetura para a API (Permissão StartInstances, SQS Send)
- [ ] Subir Fila SQS `sihd-conversion-queue` e DLQ
- [ ] Configurar EC2 (Task Scheduler) para rodar o script Python automatically on Startup
