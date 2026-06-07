import json
from flask import Flask, render_template, request, jsonify
from g4f.client import Client
import os

app = Flask(__name__)

client = Client()

BUDGET_LABELS = {
    "budget": "Budget (₹800–₹2000/night)",
    "mid": "Mid-range (₹2000–₹5000/night)",
    "premium": "Premium (₹5000–₹10000/night)",
    "luxury": "Luxury (₹10000+/night)"
}

# IMPORTANT:
# Keep the schema OUTSIDE the f-string.
JSON_SCHEMA = r"""
{
    "summary": {{
      "total_distance_km": 850,
      "total_drive_hours": 14.5,
      "total_days": 2,
      "best_route_name": "NH48 via Pune",
      "terrain": "mix of ghat sections and highway"
    }},
    "fuel": {{
      "total_liters": 56.7,
      "total_cost_inr": 5953,
      "recommended_fuel_stops": ["Pune", "Kolhapur"],
      "tank_fills_approx": 2
    }},

    "tolls": {
        "total_toll_cost_inr": 845,
        "total_toll_count": 4
      },
      
    "days": [
      {{
        "day": 1,
        "from": "Mumbai",
        "to": "Kolhapur",
        "drive_hours": 7.5,
        "distance_km": 380,
        "start_time": "06:00 AM",
        "arrive_time": "02:30 PM",
        "checkpoints": [
          {{
            "name": "Mumbai (Start)",
            "type": "start",
            "cumulative_km": 0,
            "segment_km": 0,
            "segment_time_min": 0,
            "eta": "06:00 AM",
            "notes": "Departure point"
          }},
          {{
            "name": "Pune",
            "type": "mid",
            "cumulative_km": 150,
            "segment_km": 150,
            "segment_time_min": 165,
            "eta": "08:45 AM",
            "notes": "Fuel & breakfast stop"
          }},
          {{
            "name": "Kolhapur",
            "type": "night",
            "cumulative_km": 380,
            "segment_km": 230,
            "segment_time_min": 225,
            "eta": "02:30 PM",
            "notes": "Night halt"
          }}
        ],
        "night_stay": {{
          "city": "Kolhapur",
          "why": "Major city, culturally rich, great food scene",
          "hotels": [
            {{"name": "Hotel Pavillion", "type": "Mid-range", "stars": 4, "price_approx": "₹2500-3500/night", "highlight": "Central location, clean rooms"}},
            {{"name": "The Shalini Palace Hotel", "type": "Heritage", "stars": 4, "price_approx": "₹4000-6000/night", "highlight": "Heritage property, palace ambience"}}
          ],
          "food": [
            {{"name": "Kolhapuri Thali at Padma Guest House", "cuisine": "Kolhapuri", "must_try": "Tambda & Pandhra Rassa", "type": "Local"}},
            {{"name": "Opal Restaurant", "cuisine": "Multi-cuisine", "must_try": "Misal Pav", "type": "Restaurant"}}
          ]
        }}
      }}
    ],
    "tips": [
      "Start early to avoid city traffic",
      "Ghat sections need careful driving — avoid night driving",
      "Carry cash for toll booths"
    ]
  }
"""


def build_prompt(
    source,
    dest,
    mileage,
    max_drive_hours,
    hotel_budget,
    fuel_type
):
    budget_label = BUDGET_LABELS.get(
        hotel_budget,
        BUDGET_LABELS["mid"]
    )

    return f"""
You are an expert road trip planner.

Plan a realistic road trip by car.

SOURCE: {source}
DESTINATION: {dest}

Vehicle Mileage: {mileage} km/L
Fuel Type: {fuel_type}

Rules:
- Use real roads and highways.
- Use realistic driving times.
- No day should exceed {max_drive_hours} hours.
- Hotels must match budget: {budget_label}
- Include fuel calculations.
- Include toll calculations.
- Include checkpoints.
- Include food recommendations.
- If the distance is less than 1750 KM, make the route with one night stay only.
- If the distance is less than 70 KM, make the route with no night stay - only single day journey.
- Return ONLY valid JSON.
- No markdown.
- No explanations.

JSON STRUCTURE:

{JSON_SCHEMA}

Generate a realistic trip from {source} to {dest}. Get accurate  list for each tolls (car/lmv) and fuel prices and KMs. 
The data should be as accurate as possible. Suggest the most popular route possible.



"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/plan", methods=["POST"])
def plan():

    data = request.get_json() or {}

    source = data.get("source", "").strip()
    dest = data.get("dest", "").strip()

    mileage = float(data.get("mileage", 15))
    fuel_type = data.get("fuel_type", "petrol")

    max_drive_hours = str(
        data.get("max_drive_hours", "8")
    )

    hotel_budget = data.get(
        "hotel_budget",
        "mid"
    )

    if not source or not dest:
        return jsonify({
            "error": "Both source and destination are required."
        }), 400

    prompt = build_prompt(
        source,
        dest,
        mileage,
        max_drive_hours,
        hotel_budget,
        fuel_type
    )

    try:

        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            provider="GeminiCLI",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format={
                "type": "json_object"
            }
        )

        content = response.choices[0].message.content
        print(content)
        if not content:
            return jsonify({
                "error": "AI returned an empty response."
            }), 500

        trip_data = json.loads(content)

        return jsonify({
            "trip": trip_data
        })

    except json.JSONDecodeError as e:

        return jsonify({
            "error": f"Invalid JSON returned by AI: {str(e)}"
        }), 500

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    # For Flask:
    app.run(host="0.0.0.0", port=port)
    # For Uvicorn/FastAPI:
