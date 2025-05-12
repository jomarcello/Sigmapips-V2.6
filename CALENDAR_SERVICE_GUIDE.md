# Vereenvoudigde Economic Calendar Service - Gebruikersgids

Deze gids legt uit hoe je de vereenvoudigde Economic Calendar service kunt gebruiken, testen en problemen kunt oplossen.

## Inhoudsopgave

1. [Overzicht](#overzicht)
2. [Configuratie](#configuratie)
3. [Gebruik in Code](#gebruik-in-code)
4. [Test Scripts](#test-scripts)
5. [Telegram Integratie](#telegram-integratie)
6. [Probleemoplossing](#probleemoplossing)
7. [Deployment](#deployment)

## Overzicht

De Economic Calendar service is vereenvoudigd om alleen de **directe TradingView API** te gebruiken voor het ophalen van economische kalendergegevens. Dit maakt de service betrouwbaarder en eenvoudiger te onderhouden.

### Belangrijkste kenmerken:

- Gebruikt directe HTTP verzoeken naar de TradingView Economic Calendar API
- Ingebouwde fallback mechanisme voor als de API niet beschikbaar is
- Caching van resultaten om API-verzoeken te verminderen
- Uitgebreide logging voor eenvoudige probleemoplossing

## Configuratie

### Omgevingsvariabelen

De service gebruikt de volgende omgevingsvariabelen:

| Variabele | Beschrijving | Standaardwaarde |
|-----------|--------------|-----------------|
| `CALENDAR_FALLBACK` | Schakelt fallback modus in als API calls mislukken | `false` |
| `DEBUG` | Schakelt uitgebreide logging in | `false` |
| `TELEGRAM_BOT_TOKEN` | Token voor Telegram bot (alleen nodig voor Telegram integratie) | - |
| `TELEGRAM_CHAT_ID` | Chat ID voor Telegram berichten (alleen nodig voor Telegram integratie) | - |

### Instellen van variabelen

In een shell script:

```bash
export CALENDAR_FALLBACK="true"
export DEBUG="true"
```

In Python code:

```python
import os
os.environ["CALENDAR_FALLBACK"] = "true"
os.environ["DEBUG"] = "true"
```

## Gebruik in Code

### Basis gebruik

```python
from trading_bot.services.calendar_service.calendar import EconomicCalendarService

# Initialiseer de service
calendar_service = EconomicCalendarService()

# Haal kalendergegevens op
events = await calendar_service.get_calendar(days_ahead=0, min_impact="Low")

# Formatteer de kalender voor weergave
formatted_calendar = await calendar_service.get_economic_calendar(
    currencies=["USD", "EUR", "GBP"],
    days_ahead=0,
    min_impact="Low"
)
```

### Ophalen van kalender voor een specifiek instrument

```python
# Haal kalender op voor een specifiek instrument (bijv. EURUSD)
instrument_calendar = await calendar_service.get_instrument_calendar(
    instrument="EURUSD",
    days_ahead=0,
    min_impact="Medium"
)
```

## Test Scripts

Er zijn twee test scripts beschikbaar:

### 1. Met fallback modus ingeschakeld

```bash
./run_calendar_test.sh
```

Dit script schakelt de fallback modus in, zodat de service altijd werkt, zelfs als de API niet beschikbaar is.

### 2. Met directe API (geen fallback)

```bash
./run_calendar_direct_test.sh
```

Dit script test de service met de directe TradingView API, zonder fallback.

## Telegram Integratie

Je kunt economische kalenderupdates naar Telegram sturen met het `send_direct_calendar_update.py` script:

### Test modus (alleen console output)

```bash
./send_direct_calendar_update.py --test --days=0 --impact=Medium --currencies=USD,EUR
```

### Verzenden naar Telegram

```bash
export TELEGRAM_BOT_TOKEN="jouw_bot_token"
export TELEGRAM_CHAT_ID="jouw_chat_id"

./send_direct_calendar_update.py --days=0 --impact=Medium --currencies=USD,EUR
```

Of met command line argumenten:

```bash
./send_direct_calendar_update.py --bot-token="jouw_bot_token" --chat-id="jouw_chat_id" --days=0 --impact=Medium
```

## Probleemoplossing

### API Verbindingsproblemen

Als de service geen verbinding kan maken met de TradingView API:

1. Controleer of je internetverbinding werkt
2. Controleer of de TradingView API endpoint bereikbaar is
3. Schakel DEBUG modus in om meer informatie te zien
4. Controleer of er geen rate limiting of IP-blokkering is

### Geen Kalendergegevens

Als de service geen kalendergegevens teruggeeft:

1. Controleer of je de juiste parameters gebruikt (dagen, impact niveau)
2. Probeer verschillende valuta's
3. Controleer of er economische gebeurtenissen zijn voor de geselecteerde dag
4. Schakel fallback modus in om te zien of dat helpt

### Debug Commando's

Debug de TradingView API verbinding:

```python
from trading_bot.services.calendar_service import debug_tradingview_api

# Voer debug uit
result = await debug_tradingview_api()
print(result)
```

Haal alle kalender events op zonder filtering:

```python
from trading_bot.services.calendar_service import get_all_calendar_events

# Haal alle events op
events = await get_all_calendar_events()
print(f"Aantal events: {len(events)}")
```

## Deployment

Bij deployment naar productie:

1. Stel `CALENDAR_FALLBACK="true"` in voor maximale betrouwbaarheid
2. Overweeg `DEBUG="false"` voor productie om log spam te voorkomen
3. Implementeer monitoring om te waarschuwen bij herhaalde API fouten
4. Overweeg een caching laag toe te voegen voor veelgebruikte kalendergegevens 