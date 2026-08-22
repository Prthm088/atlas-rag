import asyncio
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from atlas.config import Settings
from atlas.errors import AppError


def validate_storage_path(path: str) -> str:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise AppError("invalid_storage_path", "The file path is invalid.")
    return candidate.as_posix()


class StorageProvider:
    async def exists(self, path: str) -> bool:
        raise NotImplementedError

    async def download(self, path: str) -> bytes:
        raise NotImplementedError

    async def delete(self, path: str) -> None:
        raise NotImplementedError

    async def create_signed_url(self, path: str, expires_seconds: int = 300) -> str:
        raise NotImplementedError


class SupabaseStorage(StorageProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise AppError("storage_not_configured", "Document storage is unavailable.", status_code=503)
        self.base_url = settings.supabase_url.rstrip("/")
        self.key = settings.supabase_service_role_key
        self.bucket = settings.supabase_storage_bucket

    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    def _object_url(self, path: str) -> str:
        safe_path = quote(validate_storage_path(path), safe="/")
        return f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{safe_path}"

    async def exists(self, path: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self._object_url(path),
                    headers={**self.headers, "Range": "bytes=0-0"},
                )
        except httpx.HTTPError as exc:
            raise AppError(
                "storage_unavailable",
                "Document storage is temporarily unavailable.",
                status_code=503,
            ) from exc
        if response.status_code == 404:
            return False
        if response.status_code not in (200, 206):
            raise AppError("storage_unavailable", "Document storage is temporarily unavailable.", status_code=503)
        return True

    async def download(self, path: str) -> bytes:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(self._object_url(path), headers=self.headers)
        except httpx.HTTPError as exc:
            raise AppError("storage_unavailable", "The document could not be downloaded.", status_code=503) from exc
        if response.status_code == 404:
            raise AppError("stored_file_missing", "The uploaded file could not be found.", status_code=422)
        if response.status_code != 200:
            raise AppError("storage_unavailable", "The document could not be downloaded.", status_code=503)
        return response.content

    async def delete(self, path: str) -> None:
        validate_storage_path(path)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    "DELETE",
                    f"{self.base_url}/storage/v1/object/{self.bucket}",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"prefixes": [path]},
                )
        except httpx.HTTPError as exc:
            raise AppError("storage_unavailable", "The document could not be deleted.", status_code=503) from exc
        if response.status_code not in (200, 404):
            raise AppError("storage_unavailable", "The document could not be deleted.", status_code=503)

    async def create_signed_url(self, path: str, expires_seconds: int = 300) -> str:
        safe_path = quote(validate_storage_path(path), safe="/")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{safe_path}",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"expiresIn": expires_seconds},
                )
        except httpx.HTTPError as exc:
            raise AppError("storage_unavailable", "The source link could not be created.", status_code=503) from exc
        if response.status_code != 200:
            raise AppError("storage_unavailable", "The source link could not be created.", status_code=503)
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise AppError("storage_unavailable", "The source link could not be created.", status_code=503)
        return signed if signed.startswith("http") else f"{self.base_url}/storage/v1{signed}"


class FilesystemStorage(StorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, path: str) -> Path:
        target = (self.root / validate_storage_path(path)).resolve()
        if self.root not in target.parents:
            raise AppError("invalid_storage_path", "The file path is invalid.")
        return target

    async def exists(self, path: str) -> bool:
        return await asyncio.to_thread(self._resolve(path).is_file)

    async def download(self, path: str) -> bytes:
        target = self._resolve(path)
        if not await asyncio.to_thread(target.is_file):
            raise AppError("stored_file_missing", "The uploaded file could not be found.", status_code=422)
        return await asyncio.to_thread(target.read_bytes)

    async def delete(self, path: str) -> None:
        target = self._resolve(path)
        if await asyncio.to_thread(target.exists):
            await asyncio.to_thread(target.unlink)

    async def create_signed_url(self, path: str, expires_seconds: int = 300) -> str:
        del expires_seconds
        validate_storage_path(path)
        return f"/api/v1/documents/local-file?path={quote(path, safe='')}"


def get_storage(settings: Settings) -> StorageProvider:
    if settings.storage_backend == "filesystem":
        return FilesystemStorage(settings.local_storage_path)
    return SupabaseStorage(settings)
