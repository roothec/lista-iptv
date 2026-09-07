# lista-iptv

Lista M3U generada desde la API de [iptv-org](https://github.com/iptv-org/iptv),
pensada para **SS IPTV** en un televisor LG webOS.

## Para la TV

En SS IPTV: *Configuración → Contenido → Playlist externa*, y pega esta URL:

```
https://raw.githubusercontent.com/roothec/lista-iptv/main/mi-lista.m3u
```

## Qué hace el generador

`lista.py` construye la lista filtrando lo que no sirve en un televisor:

- **Descarta los streams que exigen `user-agent` o `referrer` propios.** SS IPTV
  no puede mandar esas cabeceras, así que esos canales nunca arrancarían.
- **Prefiere HTTPS** y la mayor calidad cuando un canal tiene varias URLs.
- **Excluye NSFW** y canales marcados como cerrados.
- Escribe `tvg-id` y apunta al EPG de iptv-org, para tener guía de programación.

```bash
python3 lista.py                      # las 11 categorías
python3 lista.py --check              # además comprueba que cada stream responda
python3 lista.py --cats animation,documentary --langs spa
```

`--check` conviene ejecutarlo **desde casa**, no en Actions: el runner de GitHub
está en Estados Unidos y descartaría canales que aquí funcionan perfectamente.

## Añadir canales propios

Los canales que metas a mano van en **`extra.m3u`**, nunca en `mi-lista.m3u`
(ese lo regenera el cron desde cero cada lunes y se los llevaría por delante).

```
#EXTINF:-1 group-title="Mios",Nombre del canal
https://servidor/stream/playlist.m3u8
```

Luego `git add extra.m3u && git commit -m "nuevo canal" && git push`. En la TV,
recarga la playlist en SS IPTV y aparece. La URL del televisor no cambia nunca.

Si lo que quieres es *más* canales del catálogo, no propios, se toca el filtro:

```bash
python3 lista.py --langs spa,eng,por,jpn    # añade portugués y japonés
python3 lista.py --cats animation,movies    # o recorta a lo que veas
```

## Mantenimiento

El workflow `regenerar.yml` la rehace cada lunes y hace commit solo si cambió
algo. Los canales caen constantemente: en la primera verificación, 278 de 1625
(un 17%) ya no respondían.
