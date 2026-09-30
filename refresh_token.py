"""
Uzun ömürlü Instagram token'ı 60 gün geçerlidir. Bu script süresini 60 gün uzatır.
En az 24 saatlik ve süresi dolmamış bir token gerekir. Ayda bir çalıştırmak yeterli.

    IG_ACCESS_TOKEN=... python refresh_token.py
Çıkan yeni token'ı GitHub Secrets'taki IG_ACCESS_TOKEN'a yapıştır.
(Facebook Sayfası akışı kullanıyorsan — GRAPH_HOST=graph.facebook.com — token'ı Meta'nın
 Access Token Tool'undan yenile; bu script yalnızca Instagram girişi akışı içindir.)
"""
import os
import sys

import requests

tok = os.getenv("IG_ACCESS_TOKEN") or sys.exit("IG_ACCESS_TOKEN yok")
r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
d = r.json()
if "access_token" not in d:
    sys.exit(f"Yenilenemedi: {d}")
print("Yeni token (", d.get("expires_in", 0) // 86400, "gün geçerli):\n", d["access_token"], sep="")
