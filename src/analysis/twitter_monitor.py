import logging
import os
import requests
import base64
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class TwitterMonitor:
    """
    Handles Twitter API connections for Phase 5.
    Uses basic Bearer Token authentication (App-Only) to search tweets.
    """
    
    def __init__(self):
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api_secret = os.getenv("TWITTER_API_SECRET")
        self.bearer_token = None
        self._authenticate()
        
    def _authenticate(self):
        """Get Bearer Token using Key/Secret"""
        if not self.api_key or not self.api_secret:
            logger.warning("Twitter API keys missing.")
            return

        try:
            # Basic Auth encoding
            creds = f"{self.api_key}:{self.api_secret}"
            encoded = base64.b64encode(creds.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            }
            
            # Post to oauth2/token
            response = requests.post(
                "https://api.twitter.com/oauth2/token",
                headers=headers,
                data={"grant_type": "client_credentials"}
            )
            
            if response.status_code == 200:
                self.bearer_token = response.json().get("access_token")
                logger.info("✅ Twitter API Authenticated")
            else:
                logger.error(f"Twitter Auth Failed: {response.text}")
                
        except Exception as e:
            logger.error(f"Twitter connection error: {e}")

    def search_tweets(self, query, days=3):
        """
        Search recent tweets.
        NOTE: Standard Basic tier only allows 7-day search.
        """
        if not self.bearer_token:
            return None
            
        try:
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            
            # Use v2 search endpoint
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": f"{query} -is:retweet lang:en",
                "max_results": 10,
                "tweet.fields": "created_at,author_id,text"
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Twitter Rate Limit Hit")
                return {"error": "rate_limit"}
            else:
                logger.error(f"Twitter Search Error: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Twitter search exception: {e}")
            return None
