"""Persist only final composition images; no wardrobe writes, try-on or point charges."""
import base64
import hashlib
import json
import struct
import time
import uuid
import zlib
from urllib.parse import urlsplit

import httpx
from pydantic import Field

from .errors import StylistError
from .models import Model, Reply
from .wardrobe_image import IMAGE_HOSTS

RENDERER = "flatlay-transparent-v4"
MAX_PNG_BYTES = 4 * 1024 * 1024


class CompositionInput(Model):
    version: int = Field(ge=1)
    look_index: int = Field(ge=0, le=6)
    theme: str = Field(pattern=r"^(female|male)$")
    image_data: str = Field(max_length=5592430)
    retry: bool = False


def validate_png(value):
    if not value.startswith("data:image/png;base64,"):
        raise StylistError("invalid_composition", "搭配图格式不正确。", 422)
    try:
        image = base64.b64decode(value.split(",", 1)[1], validate=True)
        if len(image) > MAX_PNG_BYTES or image[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError()
        offset, data, header, ended = 8, [], None, False
        while offset < len(image):
            length = int.from_bytes(image[offset:offset+4], "big")
            chunk = image[offset+4:offset+8]
            body = image[offset+8:offset+8+length]
            crc = image[offset+8+length:offset+12+length]
            if len(crc) != 4 or zlib.crc32(chunk+body) != int.from_bytes(crc, "big"):
                raise ValueError()
            if header is None and chunk != b"IHDR":
                raise ValueError()
            if chunk == b"IHDR":
                if header is not None or length != 13:
                    raise ValueError()
                header = struct.unpack(">IIBBBBB", body)
                if header[:3] != (960, 1200, 8) or header[3] != 6 or header[4:] != (0, 0, 0):
                    raise ValueError()
            if chunk == b"IDAT":
                data.append(body)
            offset += length + 12
            if chunk == b"IEND":
                ended = length == 0 and offset == len(image)
                break
        if not ended or not header:
            raise ValueError()
        expected = (960 * (4 if header[3] == 6 else 3) + 1) * 1200
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(b"".join(data), expected+1)
        if len(decoded) != expected or not decoder.eof or decoder.unused_data:
            raise ValueError()
        return image
    except (ValueError, zlib.error, struct.error, IndexError) as exc:
        raise StylistError("invalid_composition", "搭配图格式或尺寸不正确，请重新整理图片。", 422) from exc


class Compositions:
    def __init__(self, store):
        self.store = store

    def _key(self, owner, cid, version, index, theme):
        if theme not in {"female", "male"} or version < 1 or not 0 <= index <= 6:
            raise StylistError("invalid_composition", "搭配图参数不正确。", 422)
        with self.store.connection() as conn:
            row = conn.execute("SELECT reply_json FROM stylist_messages WHERE owner_id=? AND conversation_id=? AND version=?",
                               (owner, cid, version)).fetchone()
        if not row:
            raise StylistError("composition_not_found", "找不到当前账号的这套搭配。", 404)
        reply = Reply.model_validate_json(row["reply_json"])
        if index >= len(reply.looks) or not reply.looks[index].items or any(p.source != "user" for p in reply.looks[index].items):
            raise StylistError("composition_not_found", "找不到可保存的个人衣橱搭配。", 404)
        # Theme is presentation only: both assistants reuse the same transparent image.
        return hashlib.sha256(json.dumps([owner, cid, version, index, RENDERER]).encode()).hexdigest()

    def get(self, owner, cid, version, index, theme):
        key = self._key(owner, cid, version, index, theme)
        with self.store.connection() as conn:
            row = conn.execute("SELECT status,image_url FROM stylist_outfit_images WHERE id=? AND owner_id=?", (key, owner)).fetchone()
        if row and row["status"] == "completed":
            return {"status": "completed", "image_url": row["image_url"], "theme": theme}
        return {"status": row["status"] if row else "missing", "theme": theme}

    async def save(self, upstream, cid, request):
        owner = await upstream.identity()
        key = self._key(owner, cid, request.version, request.look_index, request.theme)
        image = validate_png(request.image_data)
        digest = hashlib.sha256(image).hexdigest()
        claim = uuid.uuid4().hex
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM stylist_outfit_images WHERE id=? AND owner_id=?", (key, owner)).fetchone()
            if row and row["status"] == "completed":
                return {"status": "completed", "image_url": row["image_url"], "theme": request.theme}
            if row and row["status"] == "processing" and row["lease_until"] > time.time():
                raise StylistError("composition_processing", "这套搭配图还在保存，请稍后重新加载。", 409)
            if row and not request.retry:
                raise StylistError("composition_retry_required", "搭配图尚未保存完成，请手动重试。", 409)
            if row:
                conn.execute("UPDATE stylist_outfit_images SET status='processing',claim=?,lease_until=?,image_digest=? WHERE id=? AND owner_id=?",
                             (claim, time.time()+60, digest, key, owner))
            else:
                conn.execute("INSERT INTO stylist_outfit_images(id,owner_id,conversation_id,status,claim,lease_until,image_digest,image_url) VALUES(?,?,?,'processing',?,?,?,'')",
                             (key, owner, cid, claim, time.time()+60, digest))
        try:
            result = await upstream.upload_outfit_image(request.image_data)
            url = str(result.get("url", "") if isinstance(result, dict) else "").replace("http://", "https://", 1)
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in IMAGE_HOSTS or parsed.username or parsed.password or parsed.port not in {None, 443}:
                raise StylistError("composition_upload_unknown", "保存结果尚未确认，请手动重试。", 502)
        except Exception:
            with self.store.connection() as conn:
                conn.execute("UPDATE stylist_outfit_images SET status='failed' WHERE id=? AND owner_id=? AND claim=?", (key, owner, claim))
            raise
        with self.store.connection() as conn:
            conn.execute("UPDATE stylist_outfit_images SET status='completed',image_url=?,lease_until=0 WHERE id=? AND owner_id=? AND claim=?",
                         (url, key, owner, claim))
        return {"status": "completed", "image_url": url, "theme": request.theme}

    async def download(self, owner, cid, version, index, theme, transport=None):
        result = self.get(owner, cid, version, index, theme)
        if result["status"] != "completed":
            raise StylistError("composition_not_found", "搭配图还未保存完成。", 404)
        try:
            async with httpx.AsyncClient(timeout=25, trust_env=False, follow_redirects=False, transport=transport) as client:
                async with client.stream("GET", result["image_url"]) as response:
                    if response.status_code != 200:
                        raise httpx.HTTPError("image_unavailable")
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(data)+len(chunk)>MAX_PNG_BYTES:
                            raise httpx.HTTPError("image_too_large")
                        data.extend(chunk)
            validate_png("data:image/png;base64,"+base64.b64encode(data).decode())
            return bytes(data)
        except httpx.HTTPError as exc:
            raise StylistError("composition_download_failed", "这张搭配图暂时无法下载，请稍后重试。", 502) from exc
