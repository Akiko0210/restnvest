import json
import os
from datetime import datetime

import requests
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from pydantic import BaseModel
from pymongo import MongoClient

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB connection
client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
db = client["startup_database"]
companies_collection = db["startups"]
ucla_startups_collection = db["ucla_startups"]
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)


class StartUp(BaseModel):
    Description: str
    Founders: str
    Website: str = None
    Industry: list
    Early_Metrics: str
    Funding_Status: str
    Location: str
    Press: str
    score: int = 0
    funding: int = 0
    stage: str = ""


async def fill_startup_data(startup_data):

    prompt = f"""
    Fill the following startup data:
    {startup_data}
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-04-17",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": StartUp,
        },
    )

    response_data = json.loads(response.text)
    print(response_data, "response_data")
    # Merge startup_data with response_data
    # Start with the original startup_data
    complete_startup_data = (
        startup_data.copy() if isinstance(startup_data, dict) else {}
    )

    # Update with fields from response_data
    for key, value in response_data.items():
        # Only update if the field doesn't exist or is empty in the original data
        if key not in complete_startup_data or not complete_startup_data.get(key):
            complete_startup_data[key] = value

    # Ensure required fields are present
    if "score" not in complete_startup_data:
        complete_startup_data["score"] = response_data.get("score", 0)
    if "funding" not in complete_startup_data:
        complete_startup_data["funding"] = response_data.get("funding", 0)
    if "stage" not in complete_startup_data:
        complete_startup_data["stage"] = response_data.get("stage", "")

    print("Complete startup data:", complete_startup_data)
    return complete_startup_data


async def get_UCLA_alumnis(
    query: str,
):
    url = "https://search.linkd.inc/api/search/users"
    token = os.getenv("LINKD_API_KEY")
    headers = {"Authorization": f"Bearer {token}"}

    # Base parameters
    params = {"query": query, "school": ["UCLA"]}

    # Add any additional parameters

    response = requests.request("GET", url, headers=headers, params=params)

    data = response.json()

    results = data["results"]

    for result in results:

        # Process each result to extract founder information
        founder_data = []
        for result in results:
            # Check if the person has founder experience
            is_founder = False
            founder_experience = None

            if "experience" in result:
                for exp in result["experience"]:
                    if "title" in exp and (
                        "Founder" in exp["title"] or "Co-Founder" in exp["title"]
                    ):
                        is_founder = True
                        founder_experience = exp
                        break

            if is_founder and founder_experience:
                # Create a startup-like entry for this founder
                startup_data = {
                    "_id": str(result["profile"].get("id", "")),
                    "Name": founder_experience.get("company_name", "Unknown Company"),
                    "Description": result["profile"].get("headline", ""),
                    "Founders": result["profile"].get("name", ""),
                    "Founder_LinkedIn": {
                        result["profile"]
                        .get("name", ""): result["profile"]
                        .get("linkedin_url", "")
                    },
                    "Launch Date": (
                        founder_experience.get("start_date", "").split("T")[0]
                        if founder_experience.get("start_date")
                        else ""
                    ),
                    "Website": None,
                    "Industry": [],
                    "Early Metrics": "",
                    "Funding Status": "",
                    "Location": founder_experience.get(
                        "location", result["profile"].get("location", "")
                    ),
                    "Press": "",
                    "score": 0,
                    "funding": 0,
                    "stage": "",
                }

                founder_data.append(startup_data)
    # Save founder data to a JSON file
    for data in founder_data:
        await fill_startup_data(data)

    if founder_data:
        try:
            with open("founder_data.json", "w", encoding="utf-8") as f:
                json.dump(founder_data, f, indent=2, ensure_ascii=False)
            print(
                f"Successfully saved {len(founder_data)} founder records to founder_data.json"
            )
        except Exception as e:
            print(f"Error saving founder data to JSON: {str(e)}")
    else:
        print("No founder data found to save")

    return response.json()


# Process founders data from JSON file
async def process_founders():
    try:
        # Check if the founder_data.json file exists
        if not os.path.exists("founder_data.json"):
            return jsonify({"error": "Founder data file not found"}), 404

        # Read the founder data from the JSON file
        with open("founder_data.json", "r", encoding="utf-8") as f:
            founder_data = json.load(f)

        if not founder_data:
            return jsonify({"message": "No founder data found in file"}), 200

        # Process each founder entry
        processed_count = 0
        for data in founder_data:
            # Fill missing fields for each startup entry
            await fill_startup_data(data)
            processed_count += 1

        return jsonify(
            {
                "success": True,
                "message": f"Successfully processed {processed_count} founder records",
                "processed_count": processed_count,
            }
        )
    except Exception as e:
        print(f"Error processing founder data: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/ucla-startups", methods=["GET"])
async def get_ucla_startups():
    try:
        # Fetch all UCLA startups from the collection
        startups = list(ucla_startups_collection.find())

        # Convert ObjectId to string for JSON serialization
        for startup in startups:
            startup["_id"] = str(startup["_id"])

        return jsonify(startups)
    except Exception as e:
        print(f"Error fetching UCLA startups: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/ucla", methods=["GET"])
async def search():
    print("search")
    try:
        # Get query parameter
        # query = request.args.get("query", "")
        query = "Founders"
        print(query)

        # Execute query
        results = await get_UCLA_alumnis(query)
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/companies", methods=["POST"])
def get_companies():
    try:
        # Get filter parameters from request body
        filters = request.json

        # Build MongoDB query
        query = {}

        if "industry" in filters:
            query["Industry"] = {"$in": filters["industry"]}

        if "location" in filters:
            query["Location"] = filters["location"]

        if "funding" in filters:
            query["funding"] = {"$gte": filters["funding"]}

        if "stage" in filters:
            query["stage"] = filters["stage"]

        # Execute query
        print(query)
        companies = list(companies_collection.find(query))

        # Convert ObjectId to string for JSON serialization
        for company in companies:
            company["_id"] = str(company["_id"])

        return jsonify(companies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# default route
@app.route("/")
def index():
    return "Hello, World!"


if __name__ == "__main__":
    app.run(debug=False)
