// Script to scrape ForexFactory economic calendar using Firecrawl MCP
const axios = require('axios');
const fs = require('fs');

// Function to scrape ForexFactory calendar
async function scrapeForexFactoryCalendar() {
  try {
    console.log('Scraping ForexFactory calendar...');
    
    // Define the request payload for the firecrawl_scrape tool
    const payload = {
      name: "firecrawl_scrape",
      arguments: {
        url: "https://www.forexfactory.com/calendar",
        formats: ["html"],  // Use HTML format to preserve structure
        onlyMainContent: true,
        waitFor: 5000, // Wait 5 seconds for the page to fully load with JavaScript
        timeout: 60000, // 60 seconds timeout
        mobile: false
      }
    };

    // Send the request to the Firecrawl MCP server
    const response = await axios.post('http://localhost:3000/call_tool', payload, {
      headers: {
        'Content-Type': 'application/json',
      }
    });

    if (response.data.isError) {
      console.error('Error from Firecrawl MCP server:', response.data.content[0].text);
      return null;
    }
    
    console.log('Successfully scraped ForexFactory calendar');
    
    // Save the raw HTML to a file for inspection
    fs.writeFileSync('forexfactory_raw.html', response.data.content[0].text);
    console.log('Raw HTML saved to forexfactory_raw.html');
    
    // Parse the HTML to extract calendar events
    const events = parseForexFactoryCalendar(response.data.content[0].text);
    return events;
  } catch (error) {
    console.error('Error scraping ForexFactory calendar:', error.message);
    return null;
  }
}

// Function to parse the ForexFactory calendar HTML
function parseForexFactoryCalendar(html) {
  try {
    console.log('Parsing ForexFactory calendar HTML...');
    
    // Simple regex-based parsing (not as robust as a proper HTML parser)
    const events = [];
    let currentDate = '';
    
    // Extract calendar rows
    const rowRegex = /<tr[^>]*class="[^"]*calendar_row[^"]*"[^>]*>([\s\S]*?)<\/tr>/g;
    let rowMatch;
    
    while ((rowMatch = rowRegex.exec(html)) !== null) {
      const rowContent = rowMatch[1];
      
      // Check if this is a date header row
      if (rowContent.includes('calendar__date')) {
        const dateMatch = rowContent.match(/data-date="([^"]+)"/);
        if (dateMatch) {
          currentDate = dateMatch[1];
        }
        continue;
      }
      
      // Extract event details
      const event = {
        date: currentDate
      };
      
      // Time
      const timeMatch = rowContent.match(/calendar__time[^>]*>([^<]+)</);
      if (timeMatch) {
        event.time = timeMatch[1].trim();
      }
      
      // Currency
      const currencyMatch = rowContent.match(/calendar__currency[^>]*>([^<]+)</);
      if (currencyMatch) {
        event.currency = currencyMatch[1].trim();
      }
      
      // Impact (look for high/medium/low impact classes)
      if (rowContent.includes('impact--high')) {
        event.impact = 'high';
      } else if (rowContent.includes('impact--medium')) {
        event.impact = 'medium';
      } else if (rowContent.includes('impact--low')) {
        event.impact = 'low';
      } else {
        event.impact = 'unknown';
      }
      
      // Event name
      const eventMatch = rowContent.match(/calendar__event[^>]*>([^<]+)</);
      if (eventMatch) {
        event.event = eventMatch[1].trim();
      }
      
      // Forecast
      const forecastMatch = rowContent.match(/calendar__forecast[^>]*>([^<]+)</);
      if (forecastMatch) {
        event.forecast = forecastMatch[1].trim();
      }
      
      // Previous
      const previousMatch = rowContent.match(/calendar__previous[^>]*>([^<]+)</);
      if (previousMatch) {
        event.previous = previousMatch[1].trim();
      }
      
      // Actual
      const actualMatch = rowContent.match(/calendar__actual[^>]*>([^<]+)</);
      if (actualMatch) {
        event.actual = actualMatch[1].trim();
      }
      
      // Only add events with at least date and currency
      if (event.date && event.currency) {
        events.push(event);
      }
    }
    
    console.log(`Extracted ${events.length} events from ForexFactory calendar`);
    return events;
  } catch (error) {
    console.error('Error parsing ForexFactory calendar:', error.message);
    return [];
  }
}

// Main function
async function main() {
  // Scrape ForexFactory calendar
  const events = await scrapeForexFactoryCalendar();
  
  if (events && events.length > 0) {
    // Save the events to a JSON file
    fs.writeFileSync('forexfactory_calendar.json', JSON.stringify(events, null, 2));
    console.log('ForexFactory calendar saved to forexfactory_calendar.json');
    
    // Display a sample of the events
    console.log('\nSample events:');
    console.log(JSON.stringify(events.slice(0, 3), null, 2));
  } else {
    console.log('No events extracted from ForexFactory calendar');
  }
}

// Run the main function
main().catch(console.error); 