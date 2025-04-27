import json
import os
import random

from bson import ObjectId
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# MongoDB connection
client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
db = client["startup_database"]
companies_collection = db["startups"]
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)


class StartUpEvaluation(BaseModel):
    score: int
    funding: int
    stage: str


def evaluate_startup_score(startup):
    """
    Evaluates a startup and returns a score based on various metrics using Gemini AI.

    Args:
        startup (dict): Dictionary containing startup information

    Returns:
        float: Score between 0-100 indicating startup potential
    """
    try:
        # Prepare the prompt with startup data
        prompt = f"""
        Consider the following startup metrics and evaluate a score from 0-100:

        Company Overview:
        - Name: {startup.get('Name', 'Unknown')}
        - Industry: {startup.get('Industry', 'Unknown')} 
        - Location: {startup.get('Location', 'Unknown')}
        - Launch Date: {startup.get('Launch Date', 'Unknown')}
        - Description: {startup.get('Description', 'Unknown')}

        Traction & Growth:
        - Early Metrics: {startup.get('Early Metrics', 'Unknown')}
        - Press Coverage: {startup.get('Press', 'Unknown')}

        Team:
        - Founders: {startup.get('Founders', 'Unknown')}
        - Website: {startup.get('Website', 'Unknown')}
        - Funding Status: {startup.get('Funding Status', 'Unknown')}

        Based on these metrics and considering:
        1. Market opportunity and growth potential
        2. Team background and execution ability
        3. Traction and early validation
        4. Overall company positioning

        Please provide a single numerical score between 0-100.
        From funding status, determine the state of the startup and funding in dollars as number.

        return your response as:
        {{
            "score": int,
            "funding": int,
            "stage": str
        }}
    """
        # Call Gemini API to get the score
        # Note: Implementation of actual API call would go here
        # For now returning a placeholder score based on revenue as fallback
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": StartUpEvaluation,
            },
        )
        response_data = json.loads(response.text)

        print(response_data, "response_data")
        # Add the score to the startup dictionary
        startup["score"] = min(response_data["score"], 100)
        startup["funding"] = response_data["funding"]
        startup["stage"] = response_data["stage"]
        print(json.dumps(startup, indent=4), "startup")
        return startup

    except Exception as e:
        print(f"Error evaluating startup: {str(e)}")
        return 0


def get_all_companies():
    try:
        # Fetch all documents from the collection
        companies = list(companies_collection.find())

        # Convert ObjectId to string for each document
        for company in companies:
            company["_id"] = str(company["_id"])

        return companies
    except Exception as e:
        print(f"Error fetching companies: {str(e)}")
        return []


def normalize_scores_z_score(companies):
    """
    Normalize the scores of all companies using Z-score standardization.
    This method produces scores based on how many standard deviations a company is from the mean.
    Z-score = (x - mean) / standard_deviation
    """
    try:
        # Extract scores
        scores = [
            company.get("score", 0) for company in companies if "score" in company
        ]

        if not scores:
            print("No scores found to normalize")
            return

        # Calculate mean and standard deviation
        mean_score = sum(scores) / len(scores)
        std_dev = (sum((x - mean_score) ** 2 for x in scores) / len(scores)) ** 0.5

        # Avoid division by zero
        if std_dev == 0:
            print("Standard deviation is zero, all companies have the same score")
            return

        # Normalize each company's score using Z-score
        for company in companies:
            if "score" in company:
                # Apply Z-score normalization
                z_score = (company["score"] - mean_score) / std_dev

                # Convert to a 0-100 scale (typically z-scores range from -3 to +3)
                # Scale to make most scores fall between 0-100
                normalized_score = min(max((z_score + 3) * (100 / 6), 0), 100)
                company["score"] = round(normalized_score, 2)

                # Update in database
                companies_collection.update_one(
                    {"_id": ObjectId(company["_id"])},
                    {
                        "$set": {
                            "score": company["score"],
                            "funding": company["funding"],
                            "stage": company["stage"],
                        }
                    },
                )

        # Print normalized scores for all companies
        print("\nZ-Score Normalized Scores:")
        for company in companies:
            if "score" in company:
                company_name = company.get("name", "Unknown Company")
                print(f"{company_name}: {company['score']}")

        print(
            f"Successfully normalized scores using Z-score for {len(companies)} companies"
        )

    except Exception as e:
        print(f"Error normalizing scores with Z-score: {str(e)}")


def redistribute_data(data, jitter_percent=0.03):
    new_data = []
    for value in data:
        # Normalize from [80, 90] to [0, 1]
        normalized = (value - 80) / 10
        # Stretch to [5, 95]
        stretched = normalized * 90 + 5
        # Add random jitter (± jitter_percent * 90)
        jitter = random.uniform(-jitter_percent, jitter_percent) * 90
        jittered = stretched + jitter
        # Clamp to [5, 95]
        jittered = max(5, min(95, jittered))
        new_data.append(jittered)
    return new_data


def normalize_scores_with_percentile(companies):
    """
    Normalize company scores using percentile ranking to create a more evenly distributed score range.
    This approach is less sensitive to outliers than Z-score or min-max normalization.
    """
    try:
        # Extract scores
        scores = [
            company.get("score", 0) for company in companies if "score" in company
        ]

        if not scores:
            print("No scores found to normalize")
            return

        # Sort scores for percentile calculation
        sorted_scores = sorted(scores)

        # Normalize each company's score using percentile ranking
        for company in companies:
            if "score" in company:
                # Calculate percentile rank (0-100 scale)
                rank = sorted_scores.index(company["score"])
                percentile = (
                    (rank / (len(sorted_scores) - 1)) * 100
                    if len(sorted_scores) > 1
                    else 50
                )

                # Apply sigmoid transformation to spread out the middle values
                # This creates a more balanced distribution with fewer companies clustered at extremes
                if percentile < 50:
                    adjusted_score = 25 * (percentile / 50) ** 0.8
                else:
                    adjusted_score = 75 + 25 * ((percentile - 50) / 50) ** 1.2

                company["score"] = round(adjusted_score)

                # Update in database
                companies_collection.update_one(
                    {"_id": ObjectId(company["_id"])},
                    {
                        "$set": {
                            "score": company["score"],
                            "funding": company["funding"],
                            "stage": company["stage"],
                        }
                    },
                )

        # Print normalized scores for all companies
        print("\nPercentile-Based Normalized Scores:")
        for company in companies:
            if "score" in company:
                company_name = company.get("Name", "Unknown Company")
                print(f"{company_name}: {company['score']}")

        print(
            f"Successfully normalized scores using percentile ranking for {len(companies)} companies"
        )

    except Exception as e:
        print(f"Error normalizing scores with percentile ranking: {str(e)}")


if __name__ == "__main__":
    # Fetch and print all companies
    all_companies = get_all_companies()
    print(f"Found {len(all_companies)} companies:")
    for company in all_companies:
        company = evaluate_startup_score(company)

        # Collect all scores for normalization
        all_scores = [c.get("score", 0) for c in all_companies if "score" in c]

        # Normalize scores after all companies have been evaluated
        if (
            len(all_companies) == all_companies.index(company) + 1
        ):  # If this is the last company
            normalize_scores_with_percentile(all_companies)
