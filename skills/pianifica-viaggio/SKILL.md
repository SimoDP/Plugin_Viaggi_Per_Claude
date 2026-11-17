---
name: pianifica-viaggio
description: Pianifica un viaggio con una ricerca completa e sempre uguale - voli economici, hotel (confronto Booking vs sito ufficiale), trasferimento aeroporto-hotel, meteo e cosa visitare - e produce un report finale con checklist delle verifiche manuali. Usare quando l'utente dice "/pianifica-viaggio", "organizza un viaggio", "cerca voli e hotel per...", "voglio andare a ... dal ... al ...", "trova il viaggio più economico per...".
---

# Pianifica viaggio

Eseguire SEMPRE gli step in quest'ordine. Usare i tool del server MCP `viaggi`
per tutto ciò che ha un'API; usare il browser solo dove indicato; spostare
tutto il resto nella checklist finale.

## Regola generale: automatizza ciò che è automatizzabile, delega il resto

- Se una fonte risponde (tool MCP, pagina leggibile): raccogliere i dati.
- Se un tool restituisce `{"errore": ...}` o un sito presenta un blocco
  (captcha, login obbligatorio, prezzi non visibili, preventivo solo via mail):
  NON insistere e NON stimare. Al massimo 1 nuovo tentativo, poi passare oltre.
- Aggiungere ogni caso a "Da controllare a mano" con: cosa controllare,
  link diretto, dato già noto per confronto.
- Non inventare mai prezzi, orari o disponibilità. Ogni numero nel report
  deve venire da un tool o da una pagina effettivamente letta.

## Se i tool `viaggi` non sono disponibili

Controllare all'inizio se i tool del server `viaggi` sono presenti (anche come
connettore remoto). Se mancano, eseguire comunque tutti gli step con queste fonti,
e scrivere in cima al report: "Ricerca senza API: prezzi indicativi".
- Voli: ricerca web + browser su Google Flights / Skyscanner (prezzi indicativi).
- Hotel: browser su Booking e Google Hotels, poi sito ufficiale; senza browser → checklist.
- Trasferimenti: sito ufficiale dell'aeroporto (sezione "come arrivare in città").
- Meteo: ricerca web del clima medio del mese.
- Cosa visitare: Wikivoyage e siti turistici ufficiali della città.

## Step 0 — Preferenze e intervista

Leggere PRIMA `references/preferenze.md`: sono preferenze fisse, non chiederle.

Poi fare un'intervista con lo strumento di domande a scelta multipla
(AskUserQuestion), max 2 giri, max 4 domande per giro. Chiedere SOLO ciò che
la richiesta non dice già. Ogni domanda ha un default: se l'utente salta,
usare il default e scriverlo in cima al report ("Assunto: ...").
Se lo strumento non è disponibile, fare le stesse domande in un unico messaggio
di testo; se nessuno risponde (sessione non presidiata), usare i default.

Se manca la destinazione, chiedere un'idea (mare, città d'arte, natura...)
e proporre 3 città come opzioni.

**Giro 1 — logistica**
- Date: fisse / flessibili ±1 giorno / flessibili ±2 giorni (default: fisse)
- Persone: 1 / 2 / 3 / 4+ (default: 2)
- Bagaglio: solo zaino sotto il sedile / bagaglio a mano + trolley / stiva
  (default: bagaglio a mano + trolley)
- Budget totale: fino a 500 € / 500-1000 € / 1000-1500 € / nessun limite
  (default: nessun limite, ottimizzare comunque il prezzo)

**Giro 2 — stile del viaggio** (serve per zona, hotel e itinerario)
- Ritmo: rilassato / equilibrato / intenso (default: equilibrato)
- Interessi (scelta multipla): storia e musei / cibo / natura e panorami /
  vita notturna / shopping (default: storia e musei + cibo)
- Alloggio: hotel / appartamento / indifferente; colazione inclusa importante?
  (default: hotel, colazione non obbligatoria)
- Orari voli: ok partenze all'alba e rientri tardi / preferisco orari comodi
  (default: orari comodi, partenza dopo le 7:00, rientro entro le 23:00)

Riepilogare i parametri in 2-3 righe e partire senza chiedere conferma.

## Step 1 — Voli (MCP + verifica low cost)

1. `cerca_voli` con `partenza="VRN,BGY,VCE"` e `max_scali=0`.
   Se le date sono flessibili, ripetere per ogni combinazione di date (max 6 ricerche).
   Solo se NON c'è alcun volo diretto: ripetere con `max_scali=1` e segnalarlo.
   Applicare la regola di preferenza per Verona di `references/preferenze.md`.
2. Scartare: voli fuori dagli orari scelti, arrivi dopo le 23:00 se il trasferimento
   richiede mezzi pubblici; se si è dovuto ammettere uno scalo, attese > 3 h.
3. Tenere i 5 migliori per prezzo; considerare il bagaglio in stiva se richiesto
   (passare `bagagli_stiva`).
4. Per A/R, usare `cerca_voli_ritorno` con il `departure_token` dei primi 2-3.
5. Verifica low cost: se tra i 5 ci sono Ryanair, Wizz Air o easyJet e il browser
   è disponibile, aprire il sito della compagnia e verificare il prezzo finale
   con il bagaglio scelto. Se il sito blocca → checklist.
6. Includere sempre `link_google_flights` e, se presente, `andamento_prezzi`
   (prezzo basso/tipico/alto per quel periodo).

## Step 2 — Zona dove dormire

1. `geocodifica` della città e `guida_wikivoyage` (sezioni "dormire", "spostarsi").
2. Scegliere 1-2 quartieri che bilancino: vicinanza alle attrazioni principali,
   collegamento diretto con l'aeroporto, sicurezza. Motivare in una riga.

## Step 3 — Hotel (MCP, poi confronto sito ufficiale)

1. `cerca_hotel` con il quartiere nel testo (es. "hotel Baixa Lisbona"),
   date e adulti, `voto_min` 4.0 di default, `prezzo_max_notte` dal budget.
   Rispettare la scelta alloggio dell'intervista (hotel/appartamento, colazione).
2. Tenere i 5 migliori per rapporto prezzo/posizione/voto.
3. Per ognuno: `prezzi_hotel` con il `property_token`. Confrontare il prezzo
   più basso tra le OTA (Booking, Expedia...) con quello marcato `ufficiale: true`.
4. Se il sito ufficiale non compare nei prezzi: se il browser è disponibile,
   aprire `sito_hotel` e cercare il prezzo per le stesse date; altrimenti → checklist.
5. Confrontare SOLO tariffe equivalenti (stessa camera, stesse condizioni di
   cancellazione). Se le condizioni differiscono, indicarlo.

## Step 4 — Trasferimento aeroporto → hotel

Per i 2-3 hotel finalisti:
1. `geocodifica` dell'aeroporto di arrivo e coordinate dell'hotel (da `cerca_hotel`).
2. `tragitto` con `partenza_iso` = orario di atterraggio del volo migliore + 30 min.
3. Riportare opzione mezzi pubblici (linee, cambi, durata), tempo in taxi.
   I prezzi dei biglietti vanno verificati sul sito ufficiale del trasporto
   (cercare via web); se non si trovano → checklist.
4. Segnalare se l'arrivo è troppo tardi per i mezzi pubblici.

## Step 5 — Meteo e valuta

- `meteo` sulle coordinate della città per le date del viaggio. Indicare se è
  previsione o storico dell'anno precedente.
- Se la valuta locale non è EUR: `cambio`.

## Step 6 — Cosa visitare

1. `guida_wikivoyage` (sezioni "vedere", "fare") e `punti_interesse`
   (attrazioni, musei, storico) attorno al centro.
2. Filtrare per gli interessi scelti e dosare il numero di tappe sul ritmo
   (rilassato ~2-3 al giorno, equilibrato ~4, intenso ~6).
   Costruire un itinerario giorno per giorno raggruppando i luoghi vicini
   (usare le coordinate), con il primo e l'ultimo giorno alleggeriti in base
   agli orari dei voli. Indicare orari di apertura se disponibili.
3. Per musei/attrazioni che richiedono prenotazione → checklist con il link.

## Step 7 — Report

Produrre il report seguendo `references/report-template.md`.
Se è disponibile l'artifact type Docs, creare un doc; altrimenti un file Markdown.
Chiudere con il costo totale stimato (voli + hotel + trasferimenti noti) e
il confronto col budget.
