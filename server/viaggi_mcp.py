# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2", "httpx>=0.27"]
# ///
"""Server MCP "viaggi": raccoglie dati di viaggio da API pubbliche.

Fonti:
- SerpApi (Google Flights / Google Hotels)  -> richiede SERPAPI_KEY
- Nominatim (OpenStreetMap)                 -> geocodifica, gratis
- Overpass (OpenStreetMap)                  -> punti di interesse, gratis
- Open-Meteo                                -> meteo previsto / storico, gratis
- Transitous (MOTIS)                        -> mezzi pubblici, gratis
- OSRM demo                                 -> distanza in auto / a piedi, gratis
- Wikivoyage (MediaWiki API)                -> guida della città, gratis
- Frankfurter (BCE)                         -> tassi di cambio, gratis

Ogni tool restituisce dati compatti. In caso di errore restituisce
{"errore": ...} invece di sollevare eccezioni, così la skill può
spostare il caso nella sezione "Da controllare a mano".
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("viaggi")

UA = {"User-Agent": "viaggi-plugin/0.1 (uso personale)"}
TIMEOUT = httpx.Timeout(30.0)
SERPAPI = "https://serpapi.com/search.json"


def _get(url: str, params: dict[str, Any] | None = None) -> Any:
    with httpx.Client(headers=UA, timeout=TIMEOUT, follow_redirects=True) as c:
        r = c.get(url, params={k: v for k, v in (params or {}).items() if v is not None})
        r.raise_for_status()
        return r.json()


def _safe(fn):
    """Decoratore: trasforma le eccezioni in {"errore": ...}."""
    import functools

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except httpx.HTTPStatusError as e:
            return {"errore": f"HTTP {e.response.status_code}: {e.response.text[:300]}"}
        except Exception as e:  # noqa: BLE001
            return {"errore": f"{type(e).__name__}: {e}"}

    return wrapper


def _serpapi_key() -> str:
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        raise RuntimeError("SERPAPI_KEY non impostata: voli e hotel via API non disponibili")
    return key


# ---------------------------------------------------------------- voli


def _volo_compatto(f: dict) -> dict:
    legs = f.get("flights", [])
    return {
        "prezzo_eur": f.get("price"),
        "durata_tot_min": f.get("total_duration"),
        "scali": max(len(legs) - 1, 0),
        "attese_scalo_min": [l.get("duration") for l in f.get("layovers", [])],
        "tratte": [
            {
                "compagnia": l.get("airline"),
                "volo": l.get("flight_number"),
                "da": l.get("departure_airport", {}).get("id"),
                "partenza": l.get("departure_airport", {}).get("time"),
                "a": l.get("arrival_airport", {}).get("id"),
                "arrivo": l.get("arrival_airport", {}).get("time"),
            }
            for l in legs
        ],
        "note": f.get("extensions", [])[:4],
        "departure_token": f.get("departure_token"),
    }


@mcp.tool()
@_safe
def cerca_voli(
    partenza: str,
    arrivo: str,
    data_andata: str,
    data_ritorno: str | None = None,
    adulti: int = 1,
    bagagli_stiva: int = 0,
    max_scali: int | None = None,
) -> dict:
    """Cerca voli su Google Flights (via SerpApi).

    partenza/arrivo: codici IATA, anche più di uno separati da virgola
    (es. "VRN,BGY,VCE"). Date in formato YYYY-MM-DD.
    max_scali: 0 = solo diretti, 1 = max 1 scalo, None = indifferente.
    Per i voli andata e ritorno i prezzi sono totali A/R; per vedere i
    voli di ritorno usare cerca_voli_ritorno con il departure_token.
    """
    stops = {None: 0, 0: 1, 1: 2, 2: 3}.get(max_scali, 0)
    data = _get(
        SERPAPI,
        {
            "engine": "google_flights",
            "departure_id": partenza.replace(" ", ""),
            "arrival_id": arrivo.replace(" ", ""),
            "outbound_date": data_andata,
            "return_date": data_ritorno,
            "type": 1 if data_ritorno else 2,
            "adults": adulti,
            "bags": bagagli_stiva or None,
            "stops": stops,
            "currency": "EUR",
            "hl": "it",
            "gl": "it",
            "api_key": _serpapi_key(),
        },
    )
    voli = data.get("best_flights", []) + data.get("other_flights", [])
    return {
        "link_google_flights": data.get("search_metadata", {}).get("google_flights_url"),
        "andamento_prezzi": data.get("price_insights"),
        "voli": [_volo_compatto(f) for f in voli[:15]],
    }


@mcp.tool()
@_safe
def cerca_voli_ritorno(
    partenza: str, arrivo: str, data_andata: str, data_ritorno: str, departure_token: str
) -> dict:
    """Voli di ritorno abbinabili a un volo di andata (usa il departure_token
    restituito da cerca_voli). Stessi partenza/arrivo/date della ricerca originale."""
    data = _get(
        SERPAPI,
        {
            "engine": "google_flights",
            "departure_id": partenza.replace(" ", ""),
            "arrival_id": arrivo.replace(" ", ""),
            "outbound_date": data_andata,
            "return_date": data_ritorno,
            "departure_token": departure_token,
            "currency": "EUR",
            "hl": "it",
            "gl": "it",
            "api_key": _serpapi_key(),
        },
    )
    voli = data.get("best_flights", []) + data.get("other_flights", [])
    return {"voli_ritorno": [_volo_compatto(f) for f in voli[:10]]}


# ---------------------------------------------------------------- hotel


@mcp.tool()
@_safe
def cerca_hotel(
    luogo: str,
    check_in: str,
    check_out: str,
    adulti: int = 2,
    prezzo_max_notte: int | None = None,
    voto_min: float | None = None,
) -> dict:
    """Cerca hotel su Google Hotels (via SerpApi).

    luogo: testo libero, meglio se include il quartiere
    (es. "hotel Baixa Lisbona"). voto_min: 3.5, 4.0 o 4.5 (scala Google).
    Restituisce per ogni hotel il property_token da usare in prezzi_hotel.
    """
    rating = {3.5: 7, 4.0: 8, 4.5: 9}.get(voto_min) if voto_min else None
    data = _get(
        SERPAPI,
        {
            "engine": "google_hotels",
            "q": luogo,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adulti,
            "max_price": prezzo_max_notte,
            "rating": rating,
            "currency": "EUR",
            "hl": "it",
            "gl": "it",
            "api_key": _serpapi_key(),
        },
    )
    out = []
    for p in data.get("properties", [])[:20]:
        out.append(
            {
                "nome": p.get("name"),
                "tipo": p.get("type"),
                "stelle": p.get("extracted_hotel_class"),
                "voto": p.get("overall_rating"),
                "recensioni": p.get("reviews"),
                "prezzo_notte": (p.get("rate_per_night") or {}).get("extracted_lowest"),
                "prezzo_totale": (p.get("total_rate") or {}).get("extracted_lowest"),
                "coordinate": p.get("gps_coordinates"),
                "sito": p.get("link"),
                "servizi": p.get("amenities", [])[:8],
                "property_token": p.get("property_token"),
            }
        )
    return {"hotel": out}


@mcp.tool()
@_safe
def prezzi_hotel(property_token: str, check_in: str, check_out: str, adulti: int = 2) -> dict:
    """Confronta i prezzi di UN hotel tra i vari siti (Booking, Expedia,
    sito ufficiale...). Il campo "ufficiale": true indica il sito dell'hotel."""
    data = _get(
        SERPAPI,
        {
            "engine": "google_hotels",
            "q": "hotel",
            "property_token": property_token,
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": adulti,
            "currency": "EUR",
            "hl": "it",
            "gl": "it",
            "api_key": _serpapi_key(),
        },
    )
    righe = []
    for p in data.get("featured_prices", []) + data.get("prices", []):
        righe.append(
            {
                "fonte": p.get("source"),
                "ufficiale": bool(p.get("official")),
                "prezzo_notte": (p.get("rate_per_night") or {}).get("extracted_lowest"),
                "prezzo_totale": (p.get("total_rate") or {}).get("extracted_lowest"),
                "cancellazione_gratuita": p.get("free_cancellation"),
                "link": p.get("link"),
            }
        )
    # deduplica per fonte tenendo il prezzo più basso
    best: dict[str, dict] = {}
    for r in righe:
        k = r["fonte"] or "?"
        if k not in best or (r["prezzo_totale"] or 1e9) < (best[k]["prezzo_totale"] or 1e9):
            best[k] = r
    return {
        "nome": data.get("name"),
        "indirizzo": data.get("address"),
        "sito_hotel": data.get("link"),
        "prezzi": sorted(best.values(), key=lambda r: r["prezzo_totale"] or 1e9),
    }


# ---------------------------------------------------------------- luoghi


@mcp.tool()
@_safe
def geocodifica(indirizzo: str) -> dict:
    """Coordinate di un luogo (aeroporto, hotel, quartiere, monumento) via OpenStreetMap."""
    res = _get(
        "https://nominatim.openstreetmap.org/search",
        {"q": indirizzo, "format": "jsonv2", "limit": 3, "accept-language": "it"},
    )
    return {
        "risultati": [
            {"nome": r.get("display_name"), "lat": float(r["lat"]), "lon": float(r["lon"]), "tipo": r.get("type")}
            for r in res
        ]
    }


CATEGORIE_OSM = {
    "attrazioni": '["tourism"~"attraction|viewpoint|artwork"]',
    "musei": '["tourism"~"museum|gallery"]',
    "storico": '["historic"~"monument|castle|ruins|memorial|archaeological_site"]',
    "parchi": '["leisure"~"park|garden"]',
    "mercati": '["amenity"="marketplace"]',
}


@mcp.tool()
@_safe
def punti_interesse(lat: float, lon: float, raggio_m: int = 2000, categoria: str = "attrazioni") -> dict:
    """Punti di interesse vicino a una coordinata (OpenStreetMap / Overpass).
    categoria: attrazioni | musei | storico | parchi | mercati."""
    filtro = CATEGORIE_OSM.get(categoria, CATEGORIE_OSM["attrazioni"])
    q = f"""[out:json][timeout:25];
    (node{filtro}["name"](around:{raggio_m},{lat},{lon});
     way{filtro}["name"](around:{raggio_m},{lat},{lon}););
    out center 60;"""
    with httpx.Client(headers=UA, timeout=TIMEOUT) as c:
        r = c.post("https://overpass-api.de/api/interpreter", data={"data": q})
        r.raise_for_status()
        els = r.json().get("elements", [])
    out = []
    for e in els:
        t = e.get("tags", {})
        pos = e.get("center") or e
        out.append(
            {
                "nome": t.get("name:it") or t.get("name"),
                "tipo": t.get("tourism") or t.get("historic") or t.get("leisure") or t.get("amenity"),
                "lat": pos.get("lat"),
                "lon": pos.get("lon"),
                "wikipedia": t.get("wikipedia"),
                "orari": t.get("opening_hours"),
                "sito": t.get("website"),
            }
        )
    # prima quelli con voce Wikipedia: di solito i più rilevanti
    out.sort(key=lambda x: x["wikipedia"] is None)
    return {"punti": out[:40]}


@mcp.tool()
@_safe
def guida_wikivoyage(citta: str, lingua: str = "it") -> dict:
    """Sezioni principali della guida Wikivoyage di una città
    (come arrivare, come spostarsi, cosa vedere, cosa fare...). Testo ripulito."""
    api = f"https://{lingua}.wikivoyage.org/w/api.php"
    s = _get(api, {"action": "parse", "page": citta, "prop": "sections", "format": "json", "redirects": 1})
    if "error" in s:
        return {"errore": s["error"].get("info", "pagina non trovata")}
    interessanti = re.compile(
        r"arrivare|spostarsi|vedere|fare|dormire|sicurezza|get in|get around|see|do\b", re.I
    )
    sezioni = [x for x in s["parse"]["sections"] if x.get("toclevel") == 1 and interessanti.search(x["line"])]
    out = {}
    for sec in sezioni[:6]:
        p = _get(
            api,
            {"action": "parse", "page": citta, "section": sec["index"], "prop": "wikitext", "format": "json", "redirects": 1},
        )
        txt = p["parse"]["wikitext"]["*"]
        txt = re.sub(r"\{\{[^{}]*\}\}", "", txt)
        txt = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", txt)
        txt = re.sub(r"<[^>]+>|'''?|==+", "", txt)
        out[sec["line"]] = re.sub(r"\n{3,}", "\n\n", txt).strip()[:3000]
    return {"fonte": f"https://{lingua}.wikivoyage.org/wiki/{citta.replace(' ', '_')}", "sezioni": out}


# ---------------------------------------------------------------- spostamenti


@mcp.tool()
@_safe
def tragitto(
    da_lat: float, da_lon: float, a_lat: float, a_lon: float, partenza_iso: str | None = None
) -> dict:
    """Come andare da A a B: itinerari con mezzi pubblici (Transitous) e,
    per confronto, tempo/distanza in auto e a piedi (OSRM).
    partenza_iso: es. "2027-03-12T14:30:00+01:00" (orario di atterraggio + 30 min)."""
    risultato: dict[str, Any] = {}
    try:
        tp = _get(
            "https://api.transitous.org/api/v1/plan",
            {"fromPlace": f"{da_lat},{da_lon}", "toPlace": f"{a_lat},{a_lon}", "time": partenza_iso},
        )
        itins = []
        for it in tp.get("itineraries", [])[:4]:
            itins.append(
                {
                    "durata_min": round(it.get("duration", 0) / 60),
                    "cambi": it.get("transfers"),
                    "partenza": it.get("startTime"),
                    "arrivo": it.get("endTime"),
                    "tratte": [
                        {
                            "mezzo": l.get("mode"),
                            "linea": l.get("routeShortName") or l.get("headsign"),
                            "da": (l.get("from") or {}).get("name"),
                            "a": (l.get("to") or {}).get("name"),
                            "min": round(l.get("duration", 0) / 60),
                        }
                        for l in it.get("legs", [])
                    ],
                }
            )
        risultato["mezzi_pubblici"] = itins or "nessun itinerario trovato"
    except Exception as e:  # noqa: BLE001
        risultato["mezzi_pubblici"] = {"errore": str(e)[:200]}
    for profilo, nome in (("driving", "auto_taxi"), ("foot", "a_piedi")):
        try:
            r = _get(
                f"https://router.project-osrm.org/route/v1/{profilo}/{da_lon},{da_lat};{a_lon},{a_lat}",
                {"overview": "false"},
            )
            rt = r["routes"][0]
            risultato[nome] = {"km": round(rt["distance"] / 1000, 1), "min": round(rt["duration"] / 60)}
        except Exception as e:  # noqa: BLE001
            risultato[nome] = {"errore": str(e)[:200]}
    risultato["nota"] = "Prezzi dei biglietti e del taxi non inclusi: verificarli sui siti ufficiali."
    return risultato


# ---------------------------------------------------------------- meteo e cambio


@mcp.tool()
@_safe
def meteo(lat: float, lon: float, data_inizio: str, data_fine: str) -> dict:
    """Meteo per le date del viaggio. Entro 16 giorni: previsioni.
    Più avanti: dati reali delle stesse date dell'anno scorso (indicativi)."""
    d0, d1 = date.fromisoformat(data_inizio), date.fromisoformat(data_fine)
    daily = "temperature_2m_max,temperature_2m_min,precipitation_sum"
    if d0 <= date.today() + timedelta(days=15):
        tipo, url, a, b = "previsione", "https://api.open-meteo.com/v1/forecast", d0, d1
    else:
        tipo, url = "storico anno precedente (indicativo)", "https://archive-api.open-meteo.com/v1/archive"
        a, b = d0.replace(year=d0.year - 1), d1.replace(year=d1.year - 1)
    r = _get(
        url,
        {"latitude": lat, "longitude": lon, "daily": daily, "timezone": "auto",
         "start_date": a.isoformat(), "end_date": b.isoformat()},
    )
    d = r.get("daily", {})
    giorni = [
        {"data": t, "max": mx, "min": mn, "pioggia_mm": p}
        for t, mx, mn, p in zip(d.get("time", []), d.get("temperature_2m_max", []),
                                d.get("temperature_2m_min", []), d.get("precipitation_sum", []))
    ]
    return {"tipo": tipo, "giorni": giorni}


@mcp.tool()
@_safe
def cambio(da: str = "EUR", a: str = "GBP") -> dict:
    """Tasso di cambio ufficiale BCE (Frankfurter). Utile se si paga in valuta locale."""
    r = _get("https://api.frankfurter.app/latest", {"from": da.upper(), "to": a.upper()})
    return {"data": r.get("date"), "tasso": r.get("rates", {}).get(a.upper()), "da": da.upper(), "a": a.upper()}


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    from starlette.responses import PlainTextResponse

    return PlainTextResponse("ok")


def main() -> None:
    """MCP_TRANSPORT=stdio (default, Claude Code in locale) oppure http (server remoto).

    In modalità http l'endpoint è https://<dominio>/<MCP_TOKEN>/mcp : il token
    nel percorso fa da password, così funziona con qualsiasi client
    (connettori personalizzati di claude.ai compresi) senza OAuth.
    """
    if os.environ.get("MCP_TRANSPORT", "stdio").lower() != "http":
        mcp.run()
        return
    token = os.environ.get("MCP_TOKEN", "").strip()
    if len(token) < 24 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise SystemExit("MCP_TOKEN mancante o debole: usa almeno 24 caratteri [A-Za-z0-9_-]")
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = int(os.environ.get("PORT", "8000"))
    mcp.settings.streamable_http_path = f"/{token}/mcp"
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    # FastMCP, creato con host di default 127.0.0.1, attiva una protezione
    # anti DNS-rebinding che accetta solo Host "localhost": dietro al proxy di
    # Coolify il Host è il tuo dominio e ogni richiesta riceverebbe 421.
    # Se MCP_ALLOWED_HOSTS è impostata (es. "viaggi.tuodominio.it") accetta solo
    # quei domini; altrimenti disattiva il controllo (l'accesso è già protetto dal token).
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(hosts),
        allowed_hosts=hosts + [f"{h}:*" for h in hosts],
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
