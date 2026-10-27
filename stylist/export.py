"""Export the authenticated user's wardrobe images through the existing read API."""
import asyncio
import csv
import html
import json
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

from .errors import StylistError

IMAGE_HOST_SUFFIXES = ("aidacloset.com", "wxbjq.net.cn", "aliyuncs.com", "wxbjq.top")


def image_extension(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None


def allowed_image_url(url):
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    return parsed.scheme == "https" and not parsed.username and not parsed.password and any(
        host == suffix or host.endswith("." + suffix) for suffix in IMAGE_HOST_SUFFIXES)


def csv_value(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


async def export_wardrobe(upstream, root=Path("var/exports"), resume_folder=None):
    owner = await upstream.identity()
    records, total = {}, 0
    for page in range(1, 101):
        # No AI-outfit filter: include all normal wardrobe items, not just recommendation candidates.
        data = await upstream.get("/api/user_product/quick_edit_list", {"page": page, "page_size": 50})
        batch = data.get("list") or []
        total = (data.get("pagination") or {}).get("total", 0)
        for row in batch:
            raw_id = str(row.get("user_product_id", ""))
            if raw_id.isdecimal() and int(raw_id) > 0:
                records[raw_id] = row
        if not batch or page * 50 >= total:
            break
    folder = Path(resume_folder).resolve() if resume_folder else Path(root).resolve() / ("wardrobe_" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
    images = folder / "images"
    images.mkdir(parents=True, exist_ok=bool(resume_folder))
    semaphore = asyncio.Semaphore(8)
    rows = []
    progress = {"total_visible": total, "listed": len(records), "processed": 0, "downloaded": 0}

    def save_progress():
        (folder / "progress.json").write_text(json.dumps(progress, ensure_ascii=False, indent=2))

    async with httpx.AsyncClient(timeout=40, trust_env=False, follow_redirects=False) as client:
        async def download(pid, row):
            result = {"user_product_id": pid, "title": row.get("title") or "",
                      "class_name": row.get("class_name") or "", "secondary_class_name": row.get("secondary_class_name") or "",
                      "original_image": row.get("original_image") or "", "cutout_image": row.get("cutout_image") or "",
                      "local_file": "", "status": "missing", "error": "", "image_source": ""}
            async with semaphore:
                for field in ["cutout_image", "original_image"]:
                    existing = next(images.glob(f"{pid}_{field}.*"), None) if resume_folder else None
                    if existing and image_extension(existing.read_bytes()):
                        result.update(local_file="images/" + existing.name, status="downloaded", image_source=field, error="")
                        break
                    url = row.get(field)
                    if not url:
                        continue
                    # Historical rows use HTTP for these same image CDNs; prefer their HTTPS endpoint.
                    if url.startswith("http://"):
                        url = "https://" + url[7:]
                    if not allowed_image_url(url):
                        result.update(status="failed", error="image_host_not_allowed")
                        continue
                    try:
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            chunks, size = [], 0
                            async for chunk in response.aiter_bytes():
                                size += len(chunk)
                                if size > 25 * 1024 * 1024:
                                    raise StylistError("image_too_large", "图片大于25MiB")
                                chunks.append(chunk)
                            data = b"".join(chunks)
                        ext = image_extension(data)
                        if not ext:
                            raise StylistError("invalid_image", "返回内容不是可识别的图片")
                        name = f"{pid}_{field}{ext}"
                        await asyncio.to_thread((images / name).write_bytes, data)
                        result.update(local_file="images/" + name, status="downloaded", image_source=field, error="")
                        break
                    except (httpx.HTTPError, StylistError) as exc:
                        result.update(status="failed", error=exc.code if isinstance(exc, StylistError) else type(exc).__name__)
                progress["processed"] += 1
                progress["downloaded"] += result["status"] == "downloaded"
                rows.append(result)
                save_progress()
        save_progress()
        await asyncio.gather(*(download(pid, row) for pid, row in records.items()))
    rows.sort(key=lambda x: int(x["user_product_id"]), reverse=True)
    with (folder / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]) if rows else ["user_product_id", "status"])
        writer.writeheader()
        writer.writerows({key: csv_value(value) for key, value in row.items()} for row in rows)
    (folder / "manifest.json").write_text(json.dumps({"owner_id": owner, "total_visible": total,
        "listed": len(records), "items": rows}, ensure_ascii=False, indent=2))
    cards = []
    for row in rows:
        name = row["title"] or row["secondary_class_name"] or row["class_name"] or "未命名单品"
        image = f'<img loading="lazy" src="{html.escape(row["local_file"], quote=True)}" alt="{html.escape(name, quote=True)}">' if row["local_file"] else '<div class="missing">暂无可用图片</div>'
        cards.append(f'<article data-search="{html.escape(name + " " + row["class_name"], quote=True)}">{image}<h3>{html.escape(name)}</h3><p>#{row["user_product_id"]} · {html.escape(row["class_name"])} · {"抠图" if row["image_source"] == "cutout_image" else "原图" if row["image_source"] else html.escape(row["status"])}</p></article>')
    gallery = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>个人衣橱图片导出</title><style>
    *{box-sizing:border-box}body{font-family:-apple-system,"PingFang SC",sans-serif;margin:0;padding:28px;background:#f6f4ee;color:#354034}header{max-width:1400px;margin:auto auto 28px}h1{font-size:29px}header p{font-size:13px;color:#77816e}input{padding:13px;border:1px solid #d9ddcf;border-radius:10px;width:min(100%,450px);background:#fff}main{max-width:1400px;margin:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:16px}article{background:#fff;border:1px solid #e5e7dc;border-radius:13px;overflow:hidden}article img,.missing{width:100%;height:220px;object-fit:contain;background:#fff}h3{font-size:12px;line-height:1.6;margin:12px 12px 6px;max-height:3.2em;overflow:hidden}article p{font-size:10px;color:#8a9181;margin:0 12px 14px}.missing{display:grid;place-items:center;color:#999}a{color:#53684c}@media(max-width:450px){body{padding:16px}main{grid-template-columns:repeat(2,1fr);gap:10px}article img,.missing{height:180px}}</style><header><h1>你的衣橱 · 图片导出</h1><p>__SUMMARY__</p><p>每件衣物优先抠图，缺失或不可下载时尝试原图。图片保存在本地，不修改原数据库。</p><input id="search" placeholder="按衣物名称或分类筛选…" aria-label="筛选衣物"><p><a href="manifest.csv">下载清单 CSV</a> · <a href="manifest.json">查看完整清单</a></p></header><main>__CARDS__</main><script>document.getElementById('search').oninput=e=>{for(const card of document.querySelectorAll('article'))card.style.display=card.dataset.search.toLowerCase().includes(e.target.value.toLowerCase())?'':'none'}</script></html>'''
    failed = sum(r["status"] != "downloaded" for r in rows)
    summary = f"导出时间：{datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')} · 衣物{len(rows)}件 · 图片成功{len(rows)-failed}张 · 缺失/失败{failed}件"
    (folder / "gallery.html").write_text(gallery.replace("__SUMMARY__", summary).replace("__CARDS__", "".join(cards)))

    def archive():
        path = folder / "wardrobe-images.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
            selected = [folder / row["local_file"] for row in rows if row["local_file"]]
            for source in [folder / "gallery.html", folder / "manifest.csv", folder / "manifest.json", *selected]:
                output.write(source, source.relative_to(folder))
        return path
    zip_path = await asyncio.to_thread(archive)
    result = {"folder": str(folder), "gallery": str(folder / "gallery.html"), "archive": str(zip_path),
              "manifest": str(folder / "manifest.csv"), "items": len(rows), "downloaded": len(rows)-failed,
              "failed_or_missing": failed, "total_visible": total, "scan_complete": len(rows) >= total}
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result
