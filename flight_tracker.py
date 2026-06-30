import os
import requests
import json

# ==========================================
# CONFIGURATION & SETUP
# ==========================================
# 1. API Setup — pulled from GitHub Actions Secrets (set in repo Settings)
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY", "")

# 2. Discord Setup
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 3. Flight Details
ORIGIN = "BOM"           # Mumbai
DESTINATION = "KUL"      # Kuala Lumpur
DEPART_DATE = "2026-10-01" # Checking ONLY Oct 1st
RETURN_DATE = "2026-10-06" # YYYY-MM-DD
CURRENCY = "INR"
TARGET_AIRLINE = "Batik Air" # Tracking any direct Batik Air flight

# ==========================================
# MAIN LOGIC
# ==========================================

def get_flight_price():
    """Fetches the exact round-trip flight price pairing from Google Flights via SerpApi."""
    print(f"🔍 Searching outbound flights from {ORIGIN} to {DESTINATION} departing on {DEPART_DATE}...")
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": ORIGIN,
        "arrival_id": DESTINATION,
        "outbound_date": DEPART_DATE,
        "return_date": RETURN_DATE,
        "currency": CURRENCY,
        "hl": "en",
        "type": "1", # Force strictly Round Trip pricing
        "api_key": SERPAPI_API_KEY
    }

    try:
        # --- STEP 1: FIND OUTBOUND FLIGHT ---
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        all_outbound = data.get("best_flights", []) + data.get("other_flights", [])
        outbound_option = None
        
        for option in all_outbound:
            flights_info = option.get("flights", [])
            # STRICT MATCH: Must be a direct flight (1 leg) and match the target airline
            if len(flights_info) == 1 and flights_info[0].get("airline", "") == TARGET_AIRLINE:
                outbound_option = option
                break
                
        if not outbound_option:
            print(f"⚠️ Could not find direct outbound flight on {TARGET_AIRLINE} for {DEPART_DATE}.")
            return None
            
        departure_token = outbound_option.get("departure_token")
        if not departure_token:
            print(f"⚠️ Could not get departure token for outbound {TARGET_AIRLINE} flight.")
            return None
            
        # --- STEP 2: FIND RETURN FLIGHT ---
        print(f"🔍 Found outbound {TARGET_AIRLINE} flight. Now finding return flight...")
        params["departure_token"] = departure_token # This tells Google we selected the first flight
        
        response_return = requests.get(url, params=params)
        response_return.raise_for_status()
        data_return = response_return.json()
        
        all_return = data_return.get("best_flights", []) + data_return.get("other_flights", [])
        return_option = None
        
        for option in all_return:
            flights_info = option.get("flights", [])
            # STRICT MATCH: Must be a direct flight (1 leg) and match the target airline
            if len(flights_info) == 1 and flights_info[0].get("airline", "") == TARGET_AIRLINE:
                return_option = option
                break
                
        if not return_option:
            print(f"⚠️ Could not find direct return flight on {TARGET_AIRLINE} for {RETURN_DATE}.")
            return None
            
        # --- STEP 3: EXTRACT FINAL ROUND-TRIP DATA ---
        # The price in the return_option is the final consolidated round-trip price!
        price = return_option.get("price")
        
        # Extract specific airline names and numbers for display
        outbound_leg = outbound_option.get("flights", [])[0]
        return_leg = return_option.get("flights", [])[0]
        
        outbound_str = f"{outbound_leg.get('airline', 'Unknown')} {outbound_leg.get('flight_number', '')}".strip()
        return_str = f"{return_leg.get('airline', 'Unknown')} {return_leg.get('flight_number', '')}".strip()
        
        flight_numbers = f"Outbound: {outbound_str}\n   • Return: {return_str}"
        airlines = outbound_leg.get("airline", "Unknown")
        
        return {"price": price, "airlines": airlines, "flight_numbers": flight_numbers}
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data from SerpApi: {e}")
        return None

def send_discord_message(flight_info):
    """Sends a formatted message to your Discord channel."""
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL is not set (check your repo secrets).")
        return

    price = flight_info["price"]
    airlines = flight_info["airlines"]
    
    # Format the message to look nice in Discord
    message = (
        f"✈️ **Round-Trip Alert: {ORIGIN} ⇄ {DESTINATION}** ✈️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Consolidated Price:** ₹{price:,}\n"
        f"🛫 **Airline:** {airlines}\n"
        f"🔢 **Flights:**\n   • {flight_info.get('flight_numbers', 'Unknown')}\n"
        f"📅 **Dates:** {DEPART_DATE} to {RETURN_DATE}\n"
        f"🔗 [Check on Google Flights](https://www.google.com/flights?hl=en)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    payload = {
        "content": message,
        "username": "Flight Deal Bot",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/3182/3182984.png" # Optional: plane icon
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("✅ Discord message sent successfully! Check your server.")
    except Exception as e:
        print(f"❌ Failed to send Discord message: {e}")

if __name__ == "__main__":
    if not SERPAPI_API_KEY:
        print("⚠️ SERPAPI_API_KEY is not set (check your repo secrets). Exiting.")
        exit(1)

    # 1. Get the price
    flight_data = get_flight_price()
    
    # 2. If we found a price, send it to Discord
    if flight_data and flight_data.get("price"):
        send_discord_message(flight_data)
