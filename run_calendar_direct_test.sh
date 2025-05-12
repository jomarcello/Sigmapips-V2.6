#!/bin/bash
# Script om de vereenvoudigde calendar service te testen met directe API (geen fallback)

# Stel omgevingsvariabelen in
export CALENDAR_FALLBACK="false"  # Fallback modus uitschakelen om directe API te testen
export DEBUG="true"  # Uitgebreide logging inschakelen

echo "=========================================="
echo "Directe TradingView API Calendar Test"
echo "=========================================="
echo ""
echo "Omgevingsvariabelen:"
echo "CALENDAR_FALLBACK: $CALENDAR_FALLBACK"
echo "DEBUG: $DEBUG"
echo ""
echo "Test wordt uitgevoerd met directe TradingView API..."
echo ""

# Voer de test uit
python test_calendar_config.py

# Controleer resultaat
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test succesvol afgerond! De directe TradingView API werkt correct."
else
    echo ""
    echo "❌ Test mislukt! Controleer de logs voor details."
fi

echo ""
echo "==========================================" 