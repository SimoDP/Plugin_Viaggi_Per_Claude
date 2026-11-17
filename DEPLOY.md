# Deploy del server MCP su Coolify (per usarlo da claude.ai)

Il file `server/viaggi_mcp.py` funziona in due modalità:
- `MCP_TRANSPORT=stdio` (default): lo avvia Claude Code in locale, come da README.
- `MCP_TRANSPORT=http`: server remoto, endpoint `https://<dominio>/<MCP_TOKEN>/mcp`.

Il token nel percorso fa da password: chi non lo conosce riceve 404.
Trattalo come una password (non metterlo nel repo, non condividere l'URL).

## 1. Repo

Metti questa cartella in un repo GitHub (anche privato). Il Dockerfile è in `server/`.

## 2. Nuova risorsa su Coolify (nell'istanza che hai già)

1. Progetto esistente (o nuovo) → **+ New → Application** → sorgente: il repo GitHub
   (per un repo privato serve la GitHub App di Coolify).
2. **Build Pack:** Dockerfile — **Base Directory:** `/server` — **Dockerfile:** `Dockerfile`.
3. **Ports Exposes:** `8000`.
4. **Domains:** `https://viaggi.tuodominio.it` (crea prima il record DNS A/CNAME
   verso l'IP del server Oracle). Il certificato lo genera Coolify.
5. **Environment Variables:**
   - `SERPAPI_KEY` = la tua chiave SerpApi
   - (opzionale) `MCP_ALLOWED_HOSTS` = `viaggi.tuodominio.it` — accetta richieste solo per quel dominio
   - `MCP_TOKEN` = un segreto lungo, generalo con:
     ```bash
     python3 -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
6. **Deploy.** Verifica: `https://viaggi.tuodominio.it/health` deve rispondere `ok`.

L'immagine `python:3.12-slim` è multi-architettura: va bene sull'ARM di Oracle.

## 3. Collegarlo a claude.ai

1. claude.ai → Impostazioni → Connettori → **Aggiungi connettore personalizzato**.
2. Nome: `viaggi` — URL: `https://viaggi.tuodominio.it/<MCP_TOKEN>/mcp`
3. Nessun OAuth da configurare. Salva e abilitalo nella chat.

Ora `/pianifica-viaggio` da claude.ai (browser o app) usa i tool via API.

## 4. Test veloce da terminale

```bash
URL="https://viaggi.tuodominio.it/<MCP_TOKEN>/mcp"
curl -s -X POST "$URL" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```
Deve restituire l'elenco dei 10 tool.

## Note

- Se il token trapela: cambia `MCP_TOKEN` su Coolify, ridistribuisci e aggiorna l'URL del connettore.
- Ogni chiamata a voli/hotel consuma ricerche SerpApi: il token protegge anche la tua quota.
- Nominatim/Overpass chiedono un uso moderato; per uso personale nessun problema.
