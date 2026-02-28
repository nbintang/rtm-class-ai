from src.config import get_settings
from src.storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.aws_s3_bucket:
            raise ValueError("AWS_S3_BUCKET is not set")

        try:
            import boto3
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"boto3 is required for S3 backend: {exc}") from exc

        self.bucket = settings.aws_s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )

    def upload_bytes(self, key: str, content: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return f"s3://{self.bucket}/{key}"

    def download_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

