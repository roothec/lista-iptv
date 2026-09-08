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
python3 lista.py                      # las 12 categorías
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

No llega a un número exacto: unos cuantos streams van y vienen, así que cada
`--check` encuentra ~10 muertos nuevos y resucita otros tantos, y el total
oscila un 1%. No es un problema — de eso se encarga el reintento de los 30
días. Y la diferencia que queda con el cron va siempre en la dirección buena:
añade dos o tres URLs de repuesto sin verificar, nunca recupera la lista negra.

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

Son **dos líneas por canal**: el `#EXTINF` y debajo su URL. Una URL suelta no
es un canal y se ignora — el generador te avisa por pantalla con el número de
línea, así que si algo no aparece, mira lo que dijo.

Luego `git add extra.m3u && git commit -m "nuevo canal" && git push`. **El push
dispara el workflow**, que regenera y publica en un minuto; después recarga la
playlist en SS IPTV. La URL del televisor no cambia nunca.

La URL tiene que ser una **emisión** (normalmente `.m3u8`). Un `.m3u` casi
siempre es una *lista* de cientos de canales, y el televisor no puede
reproducir una lista: por ahí no se añaden canales.

## Más canales del catálogo

Eso no va por `extra.m3u`, va por el filtro. Se edita `GRUPOS` en `lista.py`
para una categoría nueva ([las de iptv-org][cats]), o se amplían los idiomas:

```bash
python3 lista.py --check --langs spa,eng,por,jpn   # añade portugués y japonés
python3 lista.py --cats animation,movies           # o recorta a lo que veas
```

Con `--check`, para no publicar canales sin verificar. Y ojo: es normal que
haya que repetirlo (ver la lista negra, más abajo).

[cats]: https://iptv-org.github.io/api/categories.json

## Mantenimiento

El workflow `regenerar.yml` la rehace **cada lunes**, y también en cada push a
`extra.m3u`, `lista.py` o `muertos.txt` (para no esperar al lunes por un canal
nuevo). Hace commit sólo si cambió algo.

Lleva un **suelo de seguridad**: si la lista regenerada tiene menos del 60% de
los canales que ya había, no publica y el workflow falla a la vista. Si la API
de iptv-org cambia de forma o se cae a medias, prefieres un correo de error a
una playlist mutilada en el televisor.

Los canales caen constantemente: hoy hay **439 streams en la lista negra** y
quedan **1533 canales**, todos verificados desde casa. Conviene pasar un
`--check` de vez en cuando y subir `mi-lista.m3u` junto con `muertos.txt`.
