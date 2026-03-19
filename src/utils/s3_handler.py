import os
import boto3
from botocore.config import Config


class S3Handler:
    def __init__(self, config):
        aws_cfg = config.get('aws', {})
        self.bucket = aws_cfg.get('s3_bucket', '')
        self.region = aws_cfg.get('region', 'sa-east-1')
        endpoint_url = aws_cfg.get('s3_endpoint_url')

        client_kwargs = {'region_name': self.region}
        if endpoint_url:
            client_kwargs['endpoint_url'] = endpoint_url
            client_kwargs['aws_access_key_id'] = aws_cfg.get('access_key_id', 'minioadmin')
            client_kwargs['aws_secret_access_key'] = aws_cfg.get('secret_access_key', 'minioadmin')
            client_kwargs['config'] = Config(s3={'addressing_style': 'path'})

        self.client = boto3.client('s3', **client_kwargs)

    def download_file(self, s3_key, local_path):
        """Baixa arquivo do S3 para o path local, criando diretorios se necessario."""
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        response = self.client.get_object(Bucket=self.bucket, Key=s3_key)
        with open(local_path, 'wb') as f:
            for chunk in response['Body'].iter_chunks(1024 * 1024):
                f.write(chunk)
        return local_path

    def upload_file(self, local_path, s3_key):
        """Faz upload de arquivo local para o S3."""
        self.client.upload_file(local_path, self.bucket, s3_key)
        return s3_key
