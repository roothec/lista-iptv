#!/usr/bin/env python3
"""Genera una lista M3U personalizada a partir de la API de iptv-org.

  lista.py                 -> genera mi-lista.m3u con las categorias por defecto
  lista.py --check         -> ademas verifica que cada stream responda (mas lento)
  lista.py --cats anime,documentary --langs spa,eng

Filtra lo que NO sirve en SS IPTV: streams que exigen user-agent o referrer
propios, porque la app del televisor no puede mandar esas cabeceras.
"""
import argparse, collections, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://iptv-org.github.io/api"
GRUPOS = {
    "animation": "Anime y animacion", "documentary": "Documentales",
    "science": "Ciencia", "culture": "Cultura", "education": "Educacion",
    "kids": "Infantil", "movies": "Cine", "series": "Series",
    "news": "Noticias", "music": "Musica", "comedy": "Comedia",
}

def baja(nombre):
    with urllib.request.urlopen(f"{API}/{nombre}.json", timeout=60) as r:
        return json.load(r)

def vivo(url):
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cats", default=",".join(GRUPOS))
    p.add_argument("--langs", default="spa,eng")
    p.add_argument("--check", action="store_true")
    p.add_argument("-o", "--salida", default="mi-lista.m3u")
    a = p.parse_args()
    cats, langs = set(a.cats.split(",")), set(a.langs.split(","))

    canales = {c["id"]: c for c in baja("channels")}
    idiomas = collections.defaultdict(set)
    for f in baja("feeds"):
        if f.get("channel"):
            idiomas[f["channel"]].update(f.get("languages") or [])

    # mejor stream por canal: sin cabeceras, https antes que http, mayor calidad
    def orden(s):
        cal = s.get("quality") or ""
        n = int("".join(ch for ch in cal if ch.isdigit()) or 0)
        return (s["url"].startswith("https"), n)
    mejor = {}
    for s in baja("streams"):
        cid = s.get("channel")
        if not cid or s.get("user_agent") or s.get("referrer"):
            continue
        if cid not in mejor or orden(s) > orden(mejor[cid]):
            mejor[cid] = s

    sel = []
    for cid, s in mejor.items():
        c = canales.get(cid)
        if not c or c["is_nsfw"] or c.get("closed"):
            continue
        propias = set(c["categories"]) & cats
        if not propias or (langs and not (idiomas[cid] & langs)):
            continue
        cat = sorted(propias)[0]
        sel.append((GRUPOS.get(cat, cat), c["name"], c["country"], cid, s))

    if a.check:
        print(f"verificando {len(sel)} streams...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=40) as ex:
            ok = list(ex.map(lambda t: vivo(t[4]["url"]), sel))
        muertos = len(sel) - sum(ok)
        sel = [t for t, o in zip(sel, ok) if o]
        print(f"  descartados por no responder: {muertos}", file=sys.stderr)

    sel.sort(key=lambda t: (t[0], t[1]))
    with open(a.salida, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://iptv-org.github.io/epg/index.xml"\n')
        for grupo, nombre, pais, cid, s in sel:
            f.write(f'#EXTINF:-1 tvg-id="{cid}" group-title="{grupo}",{nombre} [{pais}]\n{s["url"]}\n')

    print(f"{a.salida}: {len(sel)} canales")
    for g, n in collections.Counter(t[0] for t in sel).most_common():
        print(f"   {g:<22}{n:>5}")

main()
