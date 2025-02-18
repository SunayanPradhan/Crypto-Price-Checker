import asyncio
import json
import os
import string
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker
import requests

# Prompt constants for user interaction
STEP_ONE = "Which cryptocurrency would you like to check? For example, Bitcoin or Ethereum."
REPEAT_PROMPT = "I'm sorry, I didn't get that. Please repeat the cryptocurrency name."

class CryptoPriceCheckerCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    price_report: str = ""

    @classmethod
    def register_capability(cls) -> "MatchingCapability":
        # Load configuration from config.json in the same directory
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        with open(config_path, "r") as f:
            data = json.load(f)
        return cls(
            unique_name=data["unique_name"],
            matching_hotwords=data["matching_hotwords"],
        )

    def normalize_input(self, text: str) -> str:
        # Remove leading/trailing whitespace, convert to lowercase,
        # remove punctuation, and remove spaces.
        normalized = text.strip().lower()
        normalized = normalized.translate(str.maketrans("", "", string.punctuation))
        normalized = normalized.replace(" ", "")
        return normalized

    def fetch_crypto_price(self, coin: str) -> bool:
        # Normalize the coin name
        normalized_coin = self.normalize_input(coin)
        print(f"[DEBUG] Normalized coin: {normalized_coin}")
        
        # Map common names to API identifiers if needed.
        coin_mapping = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum",
            "litecoin": "litecoin",
            # Add more mappings as needed
        }
        coin_id = coin_mapping.get(normalized_coin, normalized_coin)
        try:
            # Using the CoinGecko API (no API key required)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            print(f"[DEBUG] Fetching URL: {url}")
            response = requests.get(url)
            data = response.json()
            print(f"[DEBUG] API Response: {data}")
            if coin_id in data and "usd" in data[coin_id]:
                price = data[coin_id]["usd"]
                self.price_report = f"The current price of {normalized_coin.capitalize()} is ${price:,} USD."
                return True
            else:
                self.price_report = (
                    f"Sorry, I could not retrieve the price for {normalized_coin.capitalize()}. "
                    "Please check the cryptocurrency name and try again."
                )
                return False
        except Exception as e:
            self.price_report = "An error occurred while fetching the cryptocurrency price. Please try again later."
            print(f"[DEBUG] Exception in fetch_crypto_price: {e}")
            return False

    async def first_setup(self, coin: str):
        if coin == "":
            prompt = STEP_ONE
            while True:
                answer = await self.capability_worker.run_io_loop(prompt)
                if answer is None:
                    prompt = REPEAT_PROMPT
                    continue
                normalized_answer = self.normalize_input(answer)
                print(f"[DEBUG] User transcription after normalization: {normalized_answer}")
                res = self.fetch_crypto_price(normalized_answer)
                if not res:
                    prompt = REPEAT_PROMPT
                    continue
                break
        else:
            normalized_coin = self.normalize_input(coin)
            if not self.fetch_crypto_price(normalized_coin):
                self.price_report = "Incorrect cryptocurrency name, please try again."

        # Speak the price report (or error message) once
        await self.capability_worker.speak(self.price_report)
        await asyncio.sleep(1)
        self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self.worker)
        coin = ""  # Start without a preset coin so the system will prompt the user.
        asyncio.create_task(self.first_setup(coin))
