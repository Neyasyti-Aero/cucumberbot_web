import io

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from config import settings


class MinioClient:
    def __init__(self) -> None:
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_buckets()

    def _ensure_buckets(self) -> None:
        for bucket in [settings.minio_bucket_maps, settings.minio_bucket_logs]:
            try:
                self._s3.head_bucket(Bucket=bucket)
            except ClientError:
                self._s3.create_bucket(Bucket=bucket)

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._s3.upload_fileobj(
            io.BytesIO(data),
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    async def download(self, bucket: str, key: str) -> bytes:
        buf = io.BytesIO()
        self._s3.download_fileobj(bucket, key, buf)
        return buf.getvalue()

    async def delete(self, bucket: str, key: str) -> None:
        self._s3.delete_object(Bucket=bucket, Key=key)

    async def presigned_url(self, bucket: str, key: str, expires: int = 3600) -> str:
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )


_minio: MinioClient | None = None


def get_minio_client() -> MinioClient:
    global _minio
    if _minio is None:
        _minio = MinioClient()
    return _minio
