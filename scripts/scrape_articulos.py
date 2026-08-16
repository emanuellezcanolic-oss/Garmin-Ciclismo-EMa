"""Lee los artículos de entrenamiento-optimo.com desde el runner de GitHub
(que tiene internet abierto) y los imprime para analizarlos.
"""

import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://entrenamiento-optimo.com/articulos/"
H = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Upgrade-Insecure-Requests": "1",
}
SKIP = ("/product", "/cart", "/checkout", "/my-account", "/wp-", "/tag/",
        "/category/", "facebook", "twitter", "instagram", "youtube", "wa.me",
        "mailto:", "tel:", "/tienda", "/carrito", "/aviso", "/politica",
        "/cookies", "/contacto", "#")


def clean_text(soup):
    for t in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        t.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    txt = re.sub(r"\n{3,}", "\n\n", main.get_text("\n"))
    return re.sub(r"[ \t]{2,}", " ", txt).strip()


def main():
    idx = requests.get(BASE, headers=H, timeout=60)
    idx.raise_for_status()
    soup = BeautifulSoup(idx.text, "html.parser")
    dom = urlparse(BASE).netloc

    links = {}
    for a in soup.select("a[href]"):
        href = urljoin(BASE, a.get("href", "").split("#")[0])
        if urlparse(href).netloc != dom:
            continue
        if any(s in href.lower() for s in SKIP):
            continue
        if href.rstrip("/") == BASE.rstrip("/"):
            continue
        text = " ".join(a.get_text(" ").split())
        if href not in links and (len(text) > 10 or "/articulo" in href):
            links[href] = text

    print(f"=== {len(links)} enlaces candidatos en el índice ===")
    for h, t in links.items():
        print(f"- {t[:80]} -> {h}")

    print("\n=== CONTENIDO DE CADA ARTÍCULO ===")
    for i, (href, title) in enumerate(links.items(), 1):
        try:
            r = requests.get(href, headers=H, timeout=60)
            r.raise_for_status()
            s = BeautifulSoup(r.text, "html.parser")
            h1 = s.find("h1")
            body = clean_text(s)
            print(f"\n\n########## [{i}] {(h1.get_text().strip() if h1 else title)}")
            print(f"URL: {href}")
            print(body[:4000])
        except Exception as e:
            print(f"\n[{i}] ERROR con {href}: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
