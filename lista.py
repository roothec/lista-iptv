#!/usr/bin/env python3
"""Genera una lista M3U personalizada a partir de la API de iptv-org.

  lista.py                 -> genera mi-lista.m3u con las categorias por defecto
  lista.py --check         -> ademas verifica que cada stream responda (mas lento)
  lista.py --cats anime,documentary --langs spa,eng

Los canales propios van en extra.m3u (mismo formato M3U). Se anaden al final
y el regenerado semanal NUNCA los pisa, porque viven en otro fichero.

Filtra lo que NO sirve en SS IPTV: streams que exigen user-agent o referrer
propios, porque la app del televisor no puede mandar esas cabeceras.

--check apunta lo que no responde en muertos.txt, y TODAS las ejecuciones lo
leen para excluirlo. Sin eso el regenerado semanal (que corre sin --check, a
proposito, porque el runner de GitHub esta en EE.UU.) devolveria cada lunes
los canales muertos que ya habias podado desde casa.
"""
import argparse, collections, datetime, json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://iptv-org.github.io/api"
MUERTOS = "muertos.txt"
GRUPOS = {
    "animation": "Anime y animacion", "documentary": "Documentales",
    "science": "Ciencia", "culture": "Cultura", "education": "Educacion",
    "kids": "Infantil", "movies": "Cine", "series": "Series",
    "news": "Noticias", "music": "Musica", "comedy": "Comedia",
    "sports": "Deportes",
}

def baja(nombre):
    with urllib.request.urlopen(f"{API}/{nombre}.json", timeout=60) as r:
        return json.load(r)

# Probamos con dos cabeceras: un navegador y algo parecido a lo que manda el
# televisor. Solo damos un stream por muerto si falla con las DOS, porque
# muerto significa lista negra, y de ahi no sale hasta el reintento de 30 dias:
# un falso positivo cuesta un canal que si funcionaba.
UAS = ("Mozilla/5.0",
       "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/94 Safari/537.36")

def vivo(url):
    for ua in UAS:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", ua)
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False

def lee_muertos(ruta=MUERTOS):
    """URL -> fecha en que se comprobo, desde casa, que no responde."""
    fuera = {}
    try:
        for l in open(ruta, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#"):
                url, _, fecha = l.partition("\t")
                fuera[url] = fecha or "1970-01-01"
    except FileNotFoundError:
        pass
    return fuera

def escribe_muertos(muertos, ruta=MUERTOS):
    """Ordenado por URL: asi el diff de git solo muestra lo que cambio."""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("# Streams que no respondieron al verificar DESDE CASA (lista.py --check).\n"
                "# Todas las ejecuciones los excluyen, incluido el regenerado semanal, que\n"
                "# corre sin --check: sin este fichero volverian cada lunes.\n"
                "# Lo mantiene el propio script, no hace falta editarlo a mano.\n")
        for url, fecha in sorted(muertos.items()):
            f.write(f"{url}\t{fecha}\n")

def propios(ruta="extra.m3u"):
    """Lee extra.m3u: los canales que anade el usuario a mano.

    Cada canal son DOS lineas: #EXTINF y debajo su URL. Todo lo que no encaje
    se avisa por stderr con su numero de linea; antes se descartaba en silencio
    y era el error facil al editar a mano (una URL suelta no es un canal).
    """
    try:
        lineas = [(n, l.strip()) for n, l in enumerate(open(ruta, encoding="utf-8"), 1)]
    except FileNotFoundError:
        return []

    def aviso(n, texto):
        print(f"{ruta}:{n}: {texto}", file=sys.stderr)

    fuera, pend = [], None
    for n, l in lineas:
        if not l:
            continue
        if l.startswith("#EXTINF"):
            if pend:
                aviso(pend[0], "este #EXTINF no tiene URL debajo, se ignora")
            if "group-title=" in l:
                info = l
            elif l.startswith("#EXTINF:-1"):
                info = l.replace("#EXTINF:-1", '#EXTINF:-1 group-title="Mios"', 1)
            else:
                info = l
                aviso(n, 'sin group-title y sin "#EXTINF:-1": el canal saldra sin grupo')
            pend = (n, info)
        elif not l.startswith("#"):
            if not pend:
                aviso(n, f"URL sin su linea #EXTINF encima, se ignora: {l[:60]}")
                continue
            if l.endswith(".m3u"):
                aviso(n, "ojo, un .m3u suele ser una LISTA de canales, no una "
                         "emision: el televisor no puede reproducirla. Para mas "
                         "canales del catalogo se usa --cats, no extra.m3u")
            fuera.append((pend[1], l)); pend = None
    if pend:
        aviso(pend[0], "este #EXTINF no tiene URL debajo, se ignora")
    return fuera


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cats", default=",".join(GRUPOS))
    p.add_argument("--langs", default="spa,eng")
    p.add_argument("--check", action="store_true")
    p.add_argument("--reintentar", type=int, default=30, metavar="DIAS",
                   help="con --check, da otra oportunidad a los muertos de hace "
                        "mas de DIAS dias (0 = a todos). Los canales resucitan.")
    p.add_argument("-o", "--salida", default="mi-lista.m3u")
    a = p.parse_args()
    cats, langs = set(a.cats.split(",")), set(a.langs.split(","))

    # lista negra: sin --check se respeta tal cual; con --check, los que llevan
    # mas de --reintentar dias apuntados vuelven a la carrera por si resucitaron.
    muertos = lee_muertos()
    reintenta = set()
    if a.check:
        limite = (datetime.date.today() - datetime.timedelta(days=a.reintentar)).isoformat()
        reintenta = {u for u, f in muertos.items() if f <= limite}
    bloqueadas = set(muertos) - reintenta

    canales = {c["id"]: c for c in baja("channels")}

    # logos: un endpoint aparte. Sin esto el televisor muestra los canales
    # sin imagen. Preferimos los marcados en uso, y de esos el mas grande.
    logos = {}
    for l in baja("logos"):
        cid, url = l.get("channel"), l.get("url")
        if not cid or not url or not url.startswith("https"):
            continue
        peso = (bool(l.get("in_use")), (l.get("width") or 0) * (l.get("height") or 0))
        if cid not in logos or peso > logos[cid][0]:
            logos[cid] = (peso, url)
    logos = {k: v[1] for k, v in logos.items()}
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
    catalogo = set()
    for s in baja("streams"):
        cid, url = s.get("channel"), s.get("url")
        if not url:
            continue
        catalogo.add(url)
        if not cid or s.get("user_agent") or s.get("referrer"):
            continue
        if url in bloqueadas:
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
        hoy = datetime.date.today().isoformat()
        nuevos = revividos = 0
        for t, o in zip(sel, ok):
            url = t[4]["url"]
            if o:
                revividos += muertos.pop(url, None) is not None
            else:
                nuevos += url not in muertos
                muertos[url] = hoy
        sel = [t for t, o in zip(sel, ok) if o]
        # lo que ya no esta en el catalogo no hace falta seguir bloqueandolo
        olvidados = [u for u in muertos if u not in catalogo]
        for u in olvidados:
            del muertos[u]
        escribe_muertos(muertos)
        aviso = f"  no responden: {nuevos} nuevos | en la lista negra: {len(muertos)}"
        if revividos:
            aviso += f" | resucitados: {revividos}"
        if olvidados:
            aviso += f" | fuera del catalogo: {len(olvidados)}"
        print(aviso, file=sys.stderr)
    elif bloqueadas:
        print(f"lista negra: {len(bloqueadas)} streams excluidos sin verificar",
              file=sys.stderr)

    sel.sort(key=lambda t: (t[0], t[1]))
    with open(a.salida, "w", encoding="utf-8") as f:
        f.write('#EXTM3U x-tvg-url="https://iptv-org.github.io/epg/index.xml"\n')
        for grupo, nombre, pais, cid, s in sel:
            logo = f' tvg-logo="{logos[cid]}"' if cid in logos else ""
            f.write(f'#EXTINF:-1 tvg-id="{cid}"{logo} group-title="{grupo}",{nombre} [{pais}]\n{s["url"]}\n')

    extra = propios()
    if extra:
        with open(a.salida, "a", encoding="utf-8") as f:
            for info, url in extra:
                f.write(f"{info}\n{url}\n")

    print(f"{a.salida}: {len(sel) + len(extra)} canales ({len(extra)} propios)")
    for g, n in collections.Counter(t[0] for t in sel).most_common():
        print(f"   {g:<22}{n:>5}")

main()
