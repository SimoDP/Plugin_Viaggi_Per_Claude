# Plugin "viaggi"

Ricerca di viaggio completa, sempre con la stessa scaletta:
voli → zona → hotel (OTA vs sito ufficiale) → trasferimento → meteo → cosa visitare → report.

## Componenti

| Componente | Cosa fa |
|---|---|
| Skill `pianifica-viaggio` | La scaletta: ordine degli step, criteri di scarto, regola "se si blocca va in checklist", template del report |
| Server MCP `viaggi` (Python, locale) | 10 tool sulle API pubbliche |

### Tool MCP

| Tool | Fonte | Chiave |
|---|---|---|
| `cerca_voli`, `cerca_voli_ritorno` | Google Flights via SerpApi | `SERPAPI_KEY` |
| `cerca_hotel`, `prezzi_hotel` (con flag sito ufficiale) | Google Hotels via SerpApi | `SERPAPI_KEY` |
| `geocodifica` | Nominatim (OpenStreetMap) | no |
| `punti_interesse` | Overpass (OpenStreetMap) | no |
| `guida_wikivoyage` | Wikivoyage | no |
| `tragitto` | Transitous (mezzi pubblici) + OSRM (auto/piedi) | no |
| `meteo` | Open-Meteo (previsione o storico) | no |
| `cambio` | Frankfurter (tassi BCE) | no |

Non coperti da API (gestiti dalla skill via browser o checklist): prezzi sul sito
di Ryanair/Wizz/easyJet, prezzi sul sito ufficiale dell'hotel quando Google non li
mostra, prezzi dei biglietti dei trasporti locali, prenotazioni di musei.

## Installazione (Claude Code, in locale)

1. Installa [uv](https://docs.astral.sh/uv/): le dipendenze Python si installano da sole al primo avvio.
2. Crea un account gratuito su [serpapi.com](https://serpapi.com) e prendi la API key
   (il piano free ha un numero limitato di ricerche al mese: ogni chiamata
   `cerca_voli` / `cerca_hotel` / `prezzi_hotel` ne consuma una).
3. Esporta la chiave nella shell da cui lanci Claude Code:
   ```bash
   export SERPAPI_KEY="la-tua-chiave"
   ```
4. Avvia Claude Code caricando il plugin dalla cartella:
   ```bash
   claude --plugin-dir ./viaggi
   ```
   (Per averlo sempre installato senza flag, aggiungilo a un marketplace locale:
   vedi `claude plugin --help`.)
5. Usa: `/pianifica-viaggio Lisbona 12-16 marzo, 2 persone, solo bagaglio a mano, budget 900 €`

Senza `SERPAPI_KEY` il plugin funziona lo stesso: voli e hotel finiscono nella
checklist manuale, tutto il resto (trasferimenti, meteo, cosa visitare) resta automatico.

## Test rapido del server

```bash
uv run --script server/viaggi_mcp.py   # resta in attesa su stdio: Ctrl+C per uscire
```

## Note

- Nominatim e Overpass sono servizi gratuiti con limiti di uso corretto (circa 1 richiesta/s):
  vanno bene per uso personale.
- Il consumo di ricerche SerpApi per un viaggio tipico è ~10-20
  (voli su 1-3 combinazioni di date + 1 ricerca hotel + 5 confronti prezzi).

## Usarlo da claude.ai (senza PC acceso)

Vedi [DEPLOY.md](DEPLOY.md): stesso server in modalità HTTP su Coolify, collegato come connettore personalizzato.
