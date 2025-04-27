import json
import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file


def search_users(
    query: str,
) -> Dict[str, Any]:
    url = "https://search.linkd.inc/api/search/users"
    token = os.getenv("LINKD_API_KEY")
    headers = {"Authorization": f"Bearer {token}"}

    # Base parameters
    params = {"query": query, "school": ["UCLA"]}

    # Add any additional parameters

    response = requests.request("GET", url, headers=headers, params=params)
    return response.json()


# Example usage
if __name__ == "__main__":
    # Basic search
    # results = search_users("People who are Investor")
    results = search_users("Start up founders")
    with open("linkd_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
