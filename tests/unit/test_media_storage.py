from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tiktok_factory.storage.media import LocalMediaStorage, SupabaseMediaStorage, persist_directory


def test_supabase_media_storage_uploads_with_server_auth(tmp_path: Path) -> None:
    source = tmp_path / "final.mp4"
    source.write_bytes(b"video-bytes")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["apikey"] = request.headers.get("apikey")
        seen["content_type"] = request.headers.get("content-type")
        seen["body"] = request.read()
        return httpx.Response(200, json={"Key": "runs/test/final.mp4"})

    storage = SupabaseMediaStorage(
        "https://project.supabase.co",
        "secret-value",
        bucket="tiktok-media",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    key = storage.put(source, "runs/test/final.mp4")

    assert key == "runs/test/final.mp4"
    assert seen == {
        "method": "POST",
        "url": "https://project.supabase.co/storage/v1/object/tiktok-media/runs/test/final.mp4",
        "authorization": "Bearer secret-value",
        "apikey": "secret-value",
        "content_type": "video/mp4",
        "body": b"video-bytes",
    }


def test_supabase_media_storage_materializes_private_object(tmp_path: Path) -> None:
    destination = tmp_path / "downloaded.mp4"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == (
            "https://project.supabase.co/storage/v1/object/authenticated/"
            "tiktok-media/runs/test/final.mp4"
        )
        assert request.headers["authorization"] == "Bearer secret-value"
        return httpx.Response(200, content=b"persisted-video")

    storage = SupabaseMediaStorage(
        "https://project.supabase.co",
        "secret-value",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = storage.materialize("runs/test/final.mp4", destination)

    assert result == destination
    assert destination.read_bytes() == b"persisted-video"


def test_supabase_media_storage_preserves_private_download_error(tmp_path: Path) -> None:
    destination = tmp_path / "missing.mp4"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b'{"message":"Object not found"}')

    storage = SupabaseMediaStorage(
        "https://project.supabase.co",
        "secret-value",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(RuntimeError, match="HTTP 404.*Object not found"):
        storage.materialize("runs/test/missing.mp4", destination)

    assert not destination.exists()


def test_persist_directory_uploads_supported_files_only(tmp_path: Path) -> None:
    output = tmp_path / "output"
    (output / "clips").mkdir(parents=True)
    (output / "clips" / "shot_1.mp4").write_bytes(b"clip")
    (output / "metadata.json").write_text("{}", encoding="utf-8")
    (output / "debug.txt").write_text("skip", encoding="utf-8")
    durable = LocalMediaStorage(tmp_path / "durable")

    keys = persist_directory(durable, output, "runs/correlation-1")

    assert keys == [
        "runs/correlation-1/clips/shot_1.mp4",
        "runs/correlation-1/metadata.json",
    ]
    assert (tmp_path / "durable" / keys[0]).read_bytes() == b"clip"
    assert (tmp_path / "durable" / keys[1]).read_text(encoding="utf-8") == "{}"
