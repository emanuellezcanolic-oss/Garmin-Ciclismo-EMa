"""Lee los artículos de entrenamiento-optimo.com vía su SITEMAP (el mapa que
la web publica para ser leído), desde el runner de GitHub (internet abierto).
"""

import re
import time

import requests
from bs4 import BeautifulSoup

ROOT = "https://entrenamiento-optimo.com"
H = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}
SKIP = ("/product", "/tienda", "/carrito", "/cart", "/checkout", "/my-account",
        "/wp-", "/tag/", "/categor", "/aviso", "/politica", "/cookies",
        "/contacto", "/author", "/user")


def get(url):
    try:
        return requests.get(url, headers=H, timeout=60)
    except Exception as e:
        print(f"  (error {url}: {e})")
        return None


def locs(xml):
    return re.findall(r"<loc>\s*(.*?)\s*</loc>", xml or "", re.I)


def clean(soup):
    for t in soup(["script", "style", "nav", "footer", "header", "form", "noscript", "aside"]):
        t.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    txt = re.sub(r"\n{3,}", "\n\n", main.get_text("\n"))
    return re.sub(r"[ \t]{2,}", " ", txt).strip()


def main():
    # 1) encontrar el índice de sitemaps
    index_xml = ""
    for cand in ("/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml", "/sitemap-index.xml"):
        r = get(ROOT + cand)
        if r is not None and r.ok and "<loc" in r.text.lower():
            print(f"Sitemap índice: {cand}")
            index_xml = r.text
            break
    if not index_xml:
        print("No encontré sitemap.")
        return

    sub = locs(index_xml)
    # 2) sub-sitemaps de posts/artículos (no productos, páginas, taxonomías)
    post_maps = [u for u in sub if u.endswith(".xml") and re.search(r"post|articul|blog", u, re.I)
                 and not re.search(r"product|page|categor|tax|user|author", u, re.I)]
    if not post_maps:  # si el índice ya trae URLs directas
        post_maps = []
    print(f"Sub-sitemaps de artículos: {post_maps or '(usar índice directo)'}")

    urls = set()
    pools = post_maps if post_maps else [None]
    for pm in pools:
        xml = get(pm).text if pm else index_xml
        for u in locs(xml):
            if u.endswith(".xml"):
                continue
            if u.rstrip("/") == ROOT:
                continue
            if any(s in u.lower() for s in SKIP):
                continue
            urls.add(u)

    urls = sorted(urls)
    print(f"\n=== {len(urls)} artículos/páginas encontrados ===")
    for u in urls:
        print(" -", u)

    print("\n=== CONTENIDO ===")
    for i, u in enumerate(urls[:60], 1):
        r = get(u)
        if r is None or not r.ok:
            print(f"\n[{i}] {u} -> HTTP {getattr(r,'status_code','?')}")
            continue
        s = BeautifulSoup(r.text, "html.parser")
        h1 = s.find("h1")
        print(f"\n\n########## [{i}] {(h1.get_text().strip() if h1 else u)}")
        print(f"URL: {u}")
        print(clean(s)[:3500])
        time.sleep(1)


if __name__ == "__main__":
    main()
