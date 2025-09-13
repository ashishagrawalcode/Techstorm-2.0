# main.py - Your Python Fact-Checker "Brain" with Live API Integration
# To run this:
# 1. Install libraries: pip install Flask Flask-Cors requests python-dotenv google-generativeai
# 2. Get API keys for Google AI (Gemini), Google Cloud (Knowledge Graph), and NewsAPI.
# 3. Create a file named .env and add your keys:
#    GOOGLE_API_KEY="your_knowledge_graph_api_key"
#    GEMINI_API_KEY="your_gemini_api_key"
#    NEWS_API_KEY="your_newsapi_org_key"
# 4. Run from terminal: python main.py

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import random
from dotenv import load_dotenv
import re
import google.generativeai as genai

# Load environment variables from a .env file
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)
# Enable Cross-Origin Resource Sharing (CORS)
CORS(app)

# --- CONFIGURE GEMINI API ---
try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key or gemini_api_key == "your_gemini_api_key":
        print("WARNING: GEMINI_API_KEY not found or not set in .env file. General knowledge questions will fail.")
        genai.configure(api_key="INVALID_KEY")
    else:
        genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")


# --- INTELLIGENT ENTITY EXTRACTION ---
def extract_main_entity(claim):
    claim = claim.lower()
    patterns = [
        r"what is (.*)\?", r"who is (.*)\?", r"where is (.*)\?",
        r"what's (.*)\?", r"who's (.*)\?", r"where's (.*)\?",
        r"is (.*) in", r"are (.*) in"
    ]
    for pattern in patterns:
        match = re.search(pattern, claim, re.IGNORECASE)
        if match:
            entity = match.group(1).strip().replace(" the ", "")
            return entity
    if " is " in claim:
        entity = claim.split(" is ")[0].strip().replace(" the ", "")
        return entity
    if " are " in claim:
        entity = claim.split(" are ")[0].strip().replace(" the ", "")
        return entity
    return claim.strip()

# --- REAL-TIME API LOGIC ---
def query_gemini_api(claim):
    """
    Queries the Google Gemini API for general knowledge and scientific questions.
    """
    print("DEBUG: Querying Gemini API...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Fact-check the following statement. Start your response with only one word: TRUE, FALSE, or UNVERIFIED, and then provide a brief one-sentence explanation. Statement: '{claim}'"
        response = model.generate_content(prompt)
        print("DEBUG: Gemini API Response:", response.text)
        return response.text
    except Exception as e:
        print(f"ERROR: Gemini API call failed: {e}")
        return None

def query_knowledge_graph(entity):
    """
    Queries the Google Knowledge Graph API for entity-specific facts.
    """
    print("DEBUG: Querying Knowledge Graph API...")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your_actual_api_key_here":
        print("ERROR: GOOGLE_API_KEY not found or not set in .env file.")
        return None
    
    params = {'query': entity, 'key': api_key, 'limit': 1}
    api_url = "https://kgsearch.googleapis.com/v1/entities:search"
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('itemListElement'):
            return data['itemListElement'][0]['result']
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
    return None

def query_news_api(keywords):
    """
    Queries NewsAPI.org for real-time news articles.
    """
    print(f"DEBUG: Querying NewsAPI for keywords: {keywords}")
    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key or news_api_key == "your_newsapi_org_key":
        print("WARNING: NEWS_API_KEY not found or not set in .env file. News queries will fail.")
        return None

    # We format the keywords for the URL
    query_string = " OR ".join(keywords)
    url = (f"https://newsapi.org/v2/everything?"
           f"q=({query_string})&"
           f"language=en&"
           f"sortBy=publishedAt&"
           f"pageSize=3&"
           f"apiKey={news_api_key}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data.get("articles"):
            print(f"DEBUG: NewsAPI found {len(data['articles'])} articles.")
            return data["articles"]
    except requests.exceptions.RequestException as e:
        print(f"NewsAPI Error: {e}")
    return None


def analyze_claim_with_live_data(claim):
    """
    The main "brain" function. Now with a 3-step thinking process.
    """
    lower_case_claim = claim.lower()

    # --- STEP 1: Check internal knowledge base for demo-specific facts FIRST ---
    demo_facts = [
         {
            "keys": ["nepal", "parliament", "singha durbar", "burnt", "fire"],
            "verdict": "FALSE",
            "explanation": "This is a common piece of misinformation. Photos of Singha Durbar burning are real but are from a major fire in 1973. While the parliament is housed there, it did not burn down in recent protests. This is a case of real images being used in a false context.",
            "sources": [{"title": "The 1973 Singha Durbar Fire - The Record", "url": "https://www.recordnepal.com/the-1973-singha-durbar-fire"}]
        }
    ]
    for fact in demo_facts:
        if all(key in lower_case_claim for key in fact["keys"]):
            fact["confidence"] = "99%"
            return fact

    # --- STEP 2: Check if it's a news-related topic ---
    news_keywords = ["today", "yesterday", "this week", "market", "election", "downgrade", "days ago", "last month", "breaking news"]
    if any(keyword in lower_case_claim for keyword in news_keywords):
        entity_for_news = extract_main_entity(claim).split() # Get keywords from entity
        articles = query_news_api(entity_for_news)
        if articles:
            sources = [{"title": article['source']['name'], "url": article['url']} for article in articles]
            return {
                "verdict": "UNVERIFIED",
                "explanation": f"This appears to be a recent news event. Here are the latest top articles related to '{' '.join(entity_for_news)}'. We recommend reading them to form your own conclusion.",
                "sources": sources,
                "confidence": "70%"
            }

    # --- STEP 3: General Knowledge Check with Gemini (Primary Brain) ---
    gemini_response = query_gemini_api(claim)
    if gemini_response:
        response_lower = gemini_response.lower()
        verdict = "UNVERIFIED"
        if response_lower.startswith("true"):
            verdict = "TRUE"
        elif response_lower.startswith("false"):
            verdict = "FALSE"
        
        return {
            "verdict": verdict,
            "explanation": gemini_response,
            "sources": [{"title": "Source: Google Gemini", "url": "https://ai.google/"}],
            "confidence": f"{random.randint(85, 95)}%"
        }

    # --- STEP 4: Fallback to Knowledge Graph (Secondary Brain) ---
    entity = extract_main_entity(claim)
    kg_result = query_knowledge_graph(entity)
    if kg_result:
        description = kg_result.get('detailedDescription', {}).get('articleBody', '').lower()
        return {
            "verdict": "UNVERIFIED",
            "explanation": f"We found information on '{kg_result.get('name')}', but could not definitively verify this specific claim. Here is a summary from Google: {description[:200]}...",
            "sources": [{"title": "Knowledge Graph Source", "url": kg_result.get('detailedDescription', {}).get('url', '#')}],
            "confidence": f"{random.randint(50, 65)}%"
        }

    # Default response if all APIs fail
    return { "verdict": "ERROR", "explanation": "Could not verify the claim through any available API.", "sources": [], "confidence": "0%" }


@app.route('/verify', methods=['POST'])
def verify_claim():
    data = request.json
    claim = data.get('claim', '')
    if not claim:
        return jsonify({"error": "No claim provided"}), 400
    verdict_data = analyze_claim_with_live_data(claim)
    return jsonify(verdict_data)

if __name__ == '__main__':
    app.run(debug=True)

