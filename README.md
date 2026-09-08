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
- **Salta lo apuntado en `muertos.txt`**, y si el mejor stream de un canal está
  ahí, se queda con la siguiente URL en vez de perder el canal.
- Escribe `tvg-id` y apunta al EPG de iptv-org, para tener guía de programación.

```bash
python3 lista.py                      # las 11 categorías
python3 lista.py --check              # además comprueba que cada stream responda
python3 lista.py --cats animation,documentary --langs spa
```

`--check` conviene ejecutarlo **desde casa**, no en Actions: el runner de GitHub
está en Estados Unidos y descartaría canales que aquí funcionan perfectamente.
Lo que no responde queda apuntado en `muertos.txt`, y de ahí no vuelve.

## La lista negra (`muertos.txt`)

El regenerado semanal corre **sin** `--check` a propósito, así que por sí solo no
sabe qué canales están muertos: antes devolvía cada lunes los que habías podado a
mano. `muertos.txt` es lo que arregla eso. Una URL por línea con su fecha:

```
http://103.157.248.140:8000/play/a015/index.m3u8	2026-09-08
```

- **Todas** las ejecuciones lo leen y excluyen esas URLs, incluido el cron.
- **Sólo `--check` lo escribe.** El cron nunca lo modifica.
- Lo mantiene el script: no hace falta editarlo a mano, y va ordenado por URL
  para que el diff de git muestre sólo lo que cambió.

Al bloquear una URL, su canal pasa a la siguiente que tenga, que está sin
verificar. Por eso **conviene repetir `--check` hasta que el número se
estabilice** — cada pasada prueba las URLs de repuesto de la anterior:

```
286 muertos nuevos -> 1340 canales
 42                -> 1392
 11                -> 1410
  2                -> 1409   (ya no se mueve)
```

Los canales resucitan: con `--check`, las entradas de hace más de 30 días
vuelven a la carrera, y si responden salen de la lista negra
(`--reintentar 0` para reintentarlas todas, `--reintentar 9999` para ninguna).
Las URLs que desaparecen del catálogo de iptv-org se borran solas.

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
algo. Los canales caen constantemente: hoy hay **354 streams en la lista negra**
y quedan **1409 canales**, todos verificados desde casa. Conviene pasar un
`--check` de vez en cuando y subir `mi-lista.m3u` junto con `muertos.txt`.
