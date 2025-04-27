import os
from datetime import datetime

import requests
from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from pymongo import MongoClient

# Load environment variables
load_dotenv()

app = Flask(__name__)

# MongoDB connection
client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
db = client["startup_database"]
companies_collection = db["startups"]


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
    return response.json()


@app.route("/api/ucla", methods=["GET"])
async def search():
    print("search")
    try:
        # Get query parameter
        query = request.args.get("query", "")
        # query = "Fintech startup founders"
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
