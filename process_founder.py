import asyncio
import json
import os

from flask import jsonify
from google import genai

API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

# Define the StartUp schema
StartUp = {
    "type": "object",
    "properties": {
        "Name": {"type": "string"},
        "Industry": {"type": "string"},
        "Description": {"type": "string"},
        "Location": {"type": "string"},
        "funding": {"type": "number"},
        "stage": {"type": "string"},
        "score": {"type": "number"},
        # Add any other fields your schema needs
    },
}


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
    # print(response_data, "response_data")
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

    return complete_startup_data


# Process founders data from JSON file - now properly defined as async
async def process_founders():
    try:
        # Check if the founder_data.json file exists
        if not os.path.exists("founder_data.json"):
            print("Error: Founder data file not found")
            return

        # Read the founder data from the JSON file
        with open("founder_data.json", "r", encoding="utf-8") as f:
            founder_data = json.load(f)

        if not founder_data:
            print("No founder data found in file")
            return

        # Process each founder entry
        processed_founder_data = []
        processed_count = 0
        for data in founder_data:
            # Fill missing fields for each startup entry
            data = await fill_startup_data(data)
            processed_count += 1
            # Save the processed data back to a JSON file
            # Collect all processed data to save at the end
            processed_founder_data.append(data)

        # Save all processed founder data to a JSON file
        if processed_founder_data:
            try:
                with open("processed_founder_data.json", "w", encoding="utf-8") as f:
                    json.dump(processed_founder_data, f, indent=2, ensure_ascii=False)
                print(
                    f"Successfully saved {len(processed_founder_data)} processed founder records to processed_founder_data.json"
                )
            except Exception as e:
                print(f"Error saving processed founder data to JSON: {str(e)}")
        else:
            print("No processed founder data to save")
        print(f"Successfully processed {processed_count} founder records")

    except Exception as e:
        print(f"Error processing founder data: {str(e)}")


# Run the async function with asyncio
if __name__ == "__main__":
    asyncio.run(process_founders())
