# ForexFactory Economische Kalender

Deze tools halen economische evenementen op van de ForexFactory kalender en tonen ze in een geformatteerde tabel. De tool is ingesteld om te werken met GMT+8 tijdzone.

## Functies

* Haalt economische evenementen op van ForexFactory.com
* Toont evenementen in GMT+8 tijdzone
* Formatteert evenementen in een leesbare tabel met emoji's
* Toont valutavlaggen (🇺🇸, 🇪🇺, 🇬🇧, etc.)
* Toont impact niveau's (🔴 High, 🟠 Medium, 🟡 Low)
* Slaat gegevens op in JSON en tekstformaat

## Vereisten

* Python 3.6+
* Requests module
* BeautifulSoup4
* pytz

## Installatie

1. Download de scripts:
   * `get_today_events.py` - Python script voor het ophalen van gegevens
   * `run_today_events.sh` - Shell script om het Python script eenvoudig uit te voeren

2. Maak de scripts uitvoerbaar:
   ```bash
   chmod +x get_today_events.py
   chmod +x run_today_events.sh
   ```

3. Installeer de vereiste Python modules:
   ```bash
   pip install requests beautifulsoup4 pytz
   ```

## Gebruik

Voer het shell script uit om de economische kalender voor vandaag in GMT+8 tijdzone te zien:

```bash
./run_today_events.sh
```

### Opties

Je kunt het shell script uitvoeren met een `--full` optie om de volledige kalender te zien:

```bash
./run_today_events.sh --full
```

## Uitvoer

Het script genereert de volgende bestanden:

1. `forex_factory_data_YYYY-MM-DD.json` - Ruwe gegevens in JSON-formaat
2. `forex_factory_events_YYYY-MM-DD.txt` - Geformatteerde evenementen in een tabel

De uitvoer bevat:

* Datum en tijd in GMT+8 tijdzone
* Valuta met vlaggen (🇺🇸, 🇪🇺, 🇬🇧, etc.)
* Impact niveau (🔴 High, 🟠 Medium, 🟡 Low)
* Evenementnaam
* Actuele waarden (indien beschikbaar)
* Verwachte waarden (indien beschikbaar)
* Vorige waarden (indien beschikbaar)

## Voorbeeld uitvoer

```
ForexFactory Economic Calendar for Tuesday, May 13, 2025 (GMT+8)
================================================================================

| Tijd      | Valuta | Impact | Evenement                       | Actueel | Verwacht | Vorig    |
|-----------|--------|--------|--------------------------------|---------|----------|----------|
| 12:00am    | 🇬🇧 GBP   | 🟡      | MPC Member Taylor Speaks       |         |          |          |
| 2:00am     | 🇺🇸 USD   | 🟡      | Federal Budget Balance         |         | 256.4B   | -160.5B  |
| Tentative  | 🇺🇸 USD   | 🟡      | Loan Officer Survey            |         |          |          |
| 7:01am     | 🇬🇧 GBP   | 🟡      | BRC Retail Sales Monitor y/y   |         | 2.4%     | 0.9%     |
| 7:50am     | 🇯🇵 JPY   | 🟡      | BOJ Summary of Opinions        |         |          |          |
...
```

## Hoe het werkt

1. Het script haalt de HTML van de ForexFactory website op
2. Het parset de HTML met BeautifulSoup om de evenementen te extraheren
3. Het stelt de GMT+8 tijdzone in voor alle datumberekeningen
4. Het formatteert de geëxtraheerde gegevens in een leesbare tabel
5. Het slaat de gegevens op in JSON en tekstformaat

## Tijdzone

Het script gebruikt GMT+8 tijdzone (Asia/Singapore) voor alle tijden en datums. Dit wordt ingesteld via:

1. Environment variabelen in het shell script (`TZ="Asia/Singapore"`)
2. Een specifieke cookie in HTTP-requests (`gmt_offset=8`)
3. Python `pytz` tijdzone configuratie

## Foutafhandeling

Als het script geen gegevens kan ophalen van de ForexFactory website, zal het:

1. Een foutmelding weergeven
2. Proberen gegevens te laden van een eerder opgeslagen bestand (indien beschikbaar)
3. De gedownloade HTML opslaan in `forexfactory_calendar.html` voor debugging

## Bijdragen

Bijdragen zijn welkom! Voel je vrij om een issue te openen of een pull request te sturen.

## Licentie

Dit project is gelicenseerd onder de MIT Licentie - zie het LICENSE bestand voor details. 