# Config Dinâmica via Env Vars — Preparação para AMI

## Status Atual

### Feito
- [x] `load_config()` em `src/sisaih_automation.py` lê env vars e sobrescreve valores do YAML
- [x] `config.yaml` limpo — sem placeholders, só valores estáticos (timeouts, paths, worker config)
- [x] Retrocompatível: sem env vars, usa valores do YAML / `config.local.yaml`

### Env vars suportadas
| Env Var | Sobrescreve | Fallback |
|---------|-------------|----------|
| `SQS_QUEUE_URL` | `aws.sqs_queue_url` | `''` |
| `S3_BUCKET` | `aws.s3_bucket` | `''` |
| `AWS_REGION` | `aws.region` | `us-east-1` |
| `API_BASE_URL` | `api.base_url` | `''` |
| `API_KEY` | `api.api_key` | `''` |

## Pendente — Deploy na EC2

### 1. Subir código atualizado na EC2
- Copiar `src/sisaih_automation.py` e `config.yaml` atualizados
- Método: git pull ou copia manual via RDP

### 2. Setar env vars permanentes no Windows
```powershell
# PowerShell como Admin na EC2:
[System.Environment]::SetEnvironmentVariable('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/ACCOUNT/sihd-converter-queue-dev', 'Machine')
[System.Environment]::SetEnvironmentVariable('S3_BUCKET', 'sihd-converter-files-dev', 'Machine')
[System.Environment]::SetEnvironmentVariable('API_BASE_URL', 'https://processos-api-dev.notoria.com', 'Machine')
[System.Environment]::SetEnvironmentVariable('API_KEY', '<chave>', 'Machine')
[System.Environment]::SetEnvironmentVariable('AWS_REGION', 'us-east-1', 'Machine')
```

### 3. Testar worker com env vars
- Reiniciar o Task Scheduler ou rodar `python worker.py` manualmente
- Confirmar que conecta na fila e API corretas

### 4. Criar AMI
```bash
aws ec2 create-image \
  --instance-id i-0d58e4b5cf2946fc0 \
  --name "sihd-converter-rpa-v1" \
  --description "Windows + SISAIH01 + RPA + config via env vars" \
  --no-reboot \
  --region us-east-1
```

## Futuro — CDK Construct + CI/CD (etapa separada)

### CDK Construct (`infra/sihd-converter-stack.ts`)
- EC2 a partir da AMI criada
- User Data injeta env vars no boot:
  ```
  <powershell>
  [System.Environment]::SetEnvironmentVariable('SQS_QUEUE_URL', '${queue.queueUrl}', 'Machine')
  [System.Environment]::SetEnvironmentVariable('S3_BUCKET', '${bucket.bucketName}', 'Machine')
  [System.Environment]::SetEnvironmentVariable('API_BASE_URL', '${apiUrl}', 'Machine')
  [System.Environment]::SetEnvironmentVariable('API_KEY', '${apiKey}', 'Machine')
  Restart-Service -Name "SihdConverterWorker" -Force
  </powershell>
  ```
- SQS queue, S3 bucket, IAM role criados pelo CDK
- Security Group com RDP restrito + egress para SQS/S3/API
- Auto-scaling: CloudWatch alarm na fila > 0 → start instance

### CI/CD
- GitHub Actions: push na branch → build AMI nova (Packer ou `create-image`)
- Deploy: atualiza Launch Template com AMI nova → replace instance
- Rollback: reverte para AMI anterior

### Melhorias no Worker
- Separar lógica de shutdown do worker (flag `--no-shutdown` para manutenção)
- Health check endpoint para o CDK/ALB monitorar
- Logs estruturados → CloudWatch Logs agent
