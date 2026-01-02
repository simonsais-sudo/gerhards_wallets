import google.generativeai as genai
import os
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found")
            return
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def analyze_transaction(self, wallet_name, tx_data, relation_context=None):
        """
        Generates a short, punchy analysis of the transaction with structured output.
        """
        prompt = f"""You are an elite crypto analyst tracking whale movements. Analyze this transaction concisely and provide actionable insights.

Wallet: {wallet_name}
Transaction Data: {tx_data}
Additional Context: {relation_context if relation_context else "No additional context."}

Provide your analysis in this EXACT format:

**SENTIMENT:** [Choose ONE: 🚀 BULLISH | 🐻 BEARISH | ⚖️ NEUTRAL]

**TL;DR:** [One sharp sentence summarizing what happened]

**INSIGHT:** [Two sentences max - Why does this matter? What's the play?]

**ACTION:** [Choose ONE: 🟢 COPY | 🟡 MONITOR | 🔴 CAUTION | ⚪ NOISE]

Keep it brutally concise. No fluff. Degen-focused."""

        try:
            response = await self.model.generate_content_async(prompt)
            return self._format_response(response.text)
        except Exception as e:
            logger.error(f"AI Analysis failed: {e}")
            return "⚠️ **AI Analysis Unavailable**\n\nTemporary API issue. Check explorer for details."
    
    def _format_response(self, text: str) -> str:
        """
        Clean up AI response and ensure it's well-formatted.
        Truncate if too long.
        """
        # Remove excessive newlines
        text = '\n'.join(line for line in text.split('\n') if line.strip())
        
        # Truncate if too long (Telegram has limits)
        max_length = 800
        if len(text) > max_length:
            text = text[:max_length] + "...\n\n_[Response truncated]_"
        
        return text


    async def analyze_cluster(self, cluster_data):
        """
        Analyzes a group of wallets acting together.
        """
        prompt = f"""
        Multiple influencer wallets are moving. Analyze this behavior.
        
        Data: {cluster_data}
        
        Are they coordinating? Is this a cabal move?
        """
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Cluster Analysis failed: {e}")
            return "AI Analysis Unavailable"
