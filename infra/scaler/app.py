"""
Lambda escaladora — Verifica a fila SQS e lança instâncias EC2 conforme demanda.

Invocada pelo EventBridge a cada 1 minuto, uma vez para cada ambiente (dev/prod).
O evento contém {"environment": "dev"} ou {"environment": "prod"}.
"""
import os

import boto3

ec2 = boto3.client('ec2')
sqs = boto3.client('sqs')


def handler(event, context):
    env = event.get('environment', 'dev')
    queue_url = os.environ[f'QUEUE_URL_{env.upper()}']
    template_name = os.environ[f'LAUNCH_TEMPLATE_{env.upper()}']
    max_instances = int(os.environ.get('MAX_INSTANCES', '3'))

    # 1. Mensagens visíveis na fila
    attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=['ApproximateNumberOfMessagesVisible'],
    )
    msgs_visible = int(attrs['Attributes']['ApproximateNumberOfMessagesVisible'])

    if msgs_visible == 0:
        return {'launched': 0, 'reason': 'queue empty'}

    # 2. Instâncias já rodando/subindo nesse ambiente
    reservations = ec2.describe_instances(Filters=[
        {'Name': 'tag:Service', 'Values': ['sihd-converter']},
        {'Name': 'tag:Environment', 'Values': [env]},
        {'Name': 'instance-state-name', 'Values': ['running', 'pending']},
    ])['Reservations']
    running = sum(len(r['Instances']) for r in reservations)

    # 3. Quantas faltam (respeitando o máximo)
    needed = min(msgs_visible - running, max_instances - running)
    if needed <= 0:
        return {'launched': 0, 'running': running, 'msgs': msgs_visible}

    # 4. Lançar instâncias
    ec2.run_instances(
        LaunchTemplate={'LaunchTemplateName': template_name},
        MinCount=needed,
        MaxCount=needed,
    )

    print(f"[Scaler] env={env} msgs={msgs_visible} running={running} launched={needed}")
    return {'launched': needed, 'running': running, 'msgs': msgs_visible}
