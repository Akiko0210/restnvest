import os
from datetime import datetime

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
            query["location"] = filters["location"]

        if "funding_status" in filters:
            query["funding_status"] = filters["funding_status"]

        if "monthly_revenue" in filters:
            query["monthly_revenue"] = {"$gte": filters["monthly_revenue"]}

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
    app.run(host="0.0.0.0", port=5000, debug=False)
