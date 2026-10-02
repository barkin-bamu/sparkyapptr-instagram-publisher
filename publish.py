"""
Üretilen carousel'i Instagram'a paylaşır (resmi Instagram Graph API — ücretsiz).

Akış:
  1) Görseller herkese açık bir adrese yüklenir (Instagram görseli URL'den çeker)
  2) Her görsel için "carousel öğesi" konteyneri oluşturulur
  3) CAROUSEL konteyneri + açıklama oluşturulur, hazır olması beklenir
  4) media_publish ile yayınlanır

Gerekli ortam değişkenleri (.env ya da GitHub Secrets):
  IG_USER_ID         Instagram profesyonel hesap ID'si
  IG_ACCESS_TOKEN    Uzun ömürlü erişim token'ı
  HOSTING            github | cloudinary | url   (varsayılan: github)

  HOSTING=github     -> GH_TOKEN, GH_REPO ("kullanici/repo", PUBLIC olmalı), GH_BRANCH (vars: main)
  HOSTING=cloudinary -> CLOUDINARY_CLOUD, CLOUDINARY_PRESET (unsigned upload preset)
  HOSTING=url        -> PUBLIC_BASE_URL (dosyaları kendin barındırıyorsan)

Opsiyonel:
  GRAPH_HOST     graph.instagram.com (Instagram girişi ile) | graph.facebook.com (Facebook Sayfası ile)
  GRAPH_VERSION  v23.0
"""
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

GRAPH_HOST = os.getenv("GRAPH_HOST", "graph.instagram.com")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v23.0")
API = f"https://{GRAPH_HOST}/{GRAPH_VERSION}"


def env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        sys.exit(f"Eksik ortam değişkeni: {name}")
    return v


# ---------------------------------------------------------------- barındırma
def host_github(files: list[Path], date: str) -> list[str]:
    token, repo = env("GH_TOKEN"), env("GH_REPO")
    branch = os.getenv("GH_BRANCH", "main")
    urls = []
    for f in files:
        path = f"media/{date}/{f.name}"
        api = f"https://api.github.com/repos/{repo}/contents/{path}"
        h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        sha = requests.get(api, headers=h, params={"ref": branch}, timeout=30).json().get("sha")
        body = {"message": f"media {date}/{f.name}", "branch": branch,
                "content": base64.b64encode(f.read_bytes()).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(api, headers=h, json=body, timeout=60)
        r.raise_for_status()
        urls.append(f"https://raw.githubusercontent.com/{repo}/{branch}/{path}")
    return urls


def host_cloudinary(files: list[Path], date: str) -> list[str]:
    cloud, preset = env("CLOUDINARY_CLOUD"), env("CLOUDINARY_PRESET")
    urls = []
    for f in files:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/image/upload",
                          data={"upload_preset": preset, "folder": f"ig/{date}"},
                          files={"file": f.open("rb")}, timeout=60)
        r.raise_for_status()
        urls.append(r.json()["secure_url"])
    return urls


def host_url(files: list[Path], date: str) -> list[str]:
    base = env("PUBLIC_BASE_URL").rstrip("/")
    return [f"{base}/{date}/{f.name}" for f in files]


HOSTS = {"github": host_github, "cloudinary": host_cloudinary, "url": host_url}


# A retry after a successful media_publish can create a duplicate Instagram post.
# The GitHub-backed ledger deliberately blocks retries after *any* started attempt;
# a person must inspect a failed/unfinished attempt before clearing its state.
def ledger_get(date: str, kind: str):
    repo, branch = env("GH_REPO"), os.getenv("GH_BRANCH", "main")
    api = f"https://api.github.com/repos/{repo}/contents/state/{date}-{kind}.json"
    headers = {"Authorization": f"Bearer {env('GH_TOKEN')}", "Accept": "application/vnd.github+json"}
    response = requests.get(api, headers=headers, params={"ref": branch}, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return json.loads(base64.b64decode(data["content"]).decode("utf-8")), data["sha"]


def ledger_put(date: str, kind: str, record: dict, sha: str | None = None):
    repo, branch = env("GH_REPO"), os.getenv("GH_BRANCH", "main")
    api = f"https://api.github.com/repos/{repo}/contents/state/{date}-{kind}.json"
    body = {"message": f"instagram {kind} ledger {date}", "branch": branch,
            "content": base64.b64encode((json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode()).decode()}
    if sha:
        body["sha"] = sha
    response = requests.put(api, headers={"Authorization": f"Bearer {env('GH_TOKEN')}", "Accept": "application/vnd.github+json"}, json=body, timeout=60)
    response.raise_for_status()
    return response.json()["content"]["sha"]


def start_ledger(files: list[Path], caption: str, date: str, kind: str):
    if os.getenv("PUBLISH_LEDGER", "github") != "github":
        raise RuntimeError("Günlük otomatik yayın için PUBLISH_LEDGER=github gerekli.")
    existing = ledger_get(date, kind)
    if existing:
        record, sha = existing
        if record.get("status") == "published":
            print(f"  · {kind} bugün zaten yayınlandı; atlanıyor.")
            return None, None
        # Instagram'ın Media Not Found yanıtı, creation_id'nin yayınlanmadığını
        # kesin olarak gösterir. Bu durumda yalnızca eksik biçimi yeniden kurmak güvenlidir.
        if record.get("status") == "failed" and "Media Not Found" in record.get("error", ""):
            print(f"  · başarısız {kind} yeniden hazırlanıyor.")
        else:
            raise RuntimeError(f"{date} için mevcut {kind} yayın kaydı var ({record.get('status')}); çift paylaşım engellendi.")
    digest = hashlib.sha256(caption.encode("utf-8"))
    for file in files:
        digest.update(file.read_bytes())
    record = {"date": date, "kind": kind, "status": "prepared", "content_sha256": digest.hexdigest(), "media_id": None}
    return record, ledger_put(date, kind, record, sha if existing else None)


# ---------------------------------------------------------------- instagram
def ig(method: str, path: str, **params):
    params["access_token"] = env("IG_ACCESS_TOKEN")
    r = requests.request(method, f"{API}/{path}", params=params, timeout=60)
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API hatası ({path}): {data.get('error', data)}")
    return data


def wait_ready(container_id: str, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = ig("GET", container_id, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Konteyner {container_id} durumu: {st}")
        time.sleep(4)
    raise TimeoutError(f"Konteyner {container_id} zamanında hazır olmadı")


def publish_carousel(image_urls: list[str], caption: str) -> str:
    if not 2 <= len(image_urls) <= 10:
        # API carousel sınırı: 2–10 öğe (uygulamada 20'ye kadar olsa da API'de 10)
        raise ValueError(f"Carousel 2-10 görsel olmalı, şu an {len(image_urls)}")
    uid = env("IG_USER_ID")
    children = []
    for u in image_urls:
        c = ig("POST", f"{uid}/media", image_url=u, is_carousel_item="true")
        children.append(c["id"])
        print(f"  · öğe hazırlandı: {c['id']}")
    for cid in children:
        wait_ready(cid)
    parent = ig("POST", f"{uid}/media", media_type="CAROUSEL",
                children=",".join(children), caption=caption)
    wait_ready(parent["id"])
    res = ig("POST", f"{uid}/media_publish", creation_id=parent["id"])
    return res["id"]


def publish_folder(folder: Path, dry_run=False) -> str | None:
    files = sorted(folder.glob("[0-9][0-9].jpg"))
    caption = (folder / "caption.txt").read_text(encoding="utf-8")
    date = folder.name
    if dry_run:
        print(f"[deneme] {len(files)} görsel, açıklama {len(caption)} karakter — paylaşılmadı.")
        return None
    record, ledger_sha = start_ledger(files, caption, date, "carousel")
    if record is None:
        return None
    host = HOSTS[os.getenv("HOSTING", "github")]
    try:
        urls = host(files, date)
        print(f"  ✓ {len(urls)} görsel yüklendi")
        media_id = publish_carousel(urls, caption)
    except Exception as error:
        record.update(status="failed", error=str(error))
        ledger_put(date, "carousel", record, ledger_sha)
        raise
    record.update(status="published", media_id=media_id)
    ledger_put(date, "carousel", record, ledger_sha)
    print(f"  ✓ Paylaşıldı! media id: {media_id}")
    return media_id


def publish_single(folder: Path, filename: str, media_type: str, caption: str, dry_run=False) -> str | None:
    file = folder / filename
    if not file.is_file():
        raise FileNotFoundError(f"{media_type} kaynağı bulunamadı: {file}")
    date, kind = folder.name, media_type.lower()
    if dry_run:
        print(f"[deneme] {kind}: {file.name} — paylaşılmadı.")
        return None
    record, ledger_sha = start_ledger([file], caption, date, kind)
    if record is None:
        return None
    try:
        url = HOSTS[os.getenv("HOSTING", "github")]([file], date)[0]
        container = ig("POST", f"{env('IG_USER_ID')}/media", media_type=media_type,
                       **({"video_url": url, "caption": caption, "share_to_feed": "true"} if media_type == "REELS" else {"image_url": url}))
        wait_ready(container["id"])
        media_id = ig("POST", f"{env('IG_USER_ID')}/media_publish", creation_id=container["id"])["id"]
    except Exception as error:
        record.update(status="failed", error=str(error))
        ledger_put(date, kind, record, ledger_sha)
        raise
    record.update(status="published", media_id=media_id)
    ledger_put(date, kind, record, ledger_sha)
    print(f"  ✓ {kind} paylaşıldı! media id: {media_id}")
    return media_id


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="örn. out/2026-09-30")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    publish_folder(a.folder, a.dry_run)
