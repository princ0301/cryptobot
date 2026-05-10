import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


async def test_coindcx_public():
    print("\nTesting CoinDCX public API...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.coindcx.com/exchange/ticker")
            response.raise_for_status()
            tickers = response.json()

        if tickers:
            print(f"Sample ticker keys: {list(tickers[0].keys())}")
            print(f"Sample market value: {tickers[0].get('market')}")

        inr_pairs = [ticker for ticker in tickers if "INR" in str(ticker.get("market", ""))]
        btc_inr = [ticker for ticker in inr_pairs if "BTC" in str(ticker.get("market", ""))]
        eth_inr = [ticker for ticker in inr_pairs if "ETH" in str(ticker.get("market", ""))]
        bnb_inr = [ticker for ticker in inr_pairs if "BNB" in str(ticker.get("market", ""))]

        print(f"Total INR pairs found: {len(inr_pairs)}")

        if btc_inr:
            ticker = btc_inr[0]
            print(f"BTC/INR -> market='{ticker['market']}' price=INR {float(ticker.get('last_price', 0)):,.2f}")
        else:
            print("BTC/INR not found")

        if eth_inr:
            ticker = eth_inr[0]
            print(f"ETH/INR -> market='{ticker['market']}' price=INR {float(ticker.get('last_price', 0)):,.2f}")
        else:
            print("ETH/INR not found")

        if bnb_inr:
            ticker = bnb_inr[0]
            print(f"BNB/INR -> market='{ticker['market']}' price=INR {float(ticker.get('last_price', 0)):,.2f}")
        else:
            print("BNB/INR not found and may not be listed on CoinDCX")
    except Exception as exc:
        print(f"CoinDCX public API failed: {exc}")


async def test_fear_greed():
    print("\nTesting Fear & Greed API...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.alternative.me/fng/?limit=1")
            response.raise_for_status()
            data = response.json()
            score = data["data"][0]["value"]
            label = data["data"][0]["value_classification"]
            print(f"Fear & Greed API working. Score: {score} ({label})")
    except Exception as exc:
        print(f"Fear & Greed API failed: {exc}")


async def test_coingecko():
    print("\nTesting CoinGecko API...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://api.coingecko.com/api/v3/global")
            response.raise_for_status()
            data = response.json()
            btc_dominance = data["data"]["market_cap_percentage"]["btc"]
            print(f"CoinGecko API working. BTC Dominance: {btc_dominance:.1f}%")
    except Exception as exc:
        print(f"CoinGecko API failed: {exc}")


async def test_groq():
    print("\nTesting Groq API...")
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or "your_" in api_key:
        print("GROQ_API_KEY not set in .env")
        print("Get a key at console.groq.com")
        return

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": 'Reply with just: {"status": "ok"}'}],
            max_tokens=20,
        )
        reply = response.choices[0].message.content.strip()
        print(f"Groq API working. Response: {reply}")
    except Exception as exc:
        print(f"Groq API failed: {exc}")


def test_supabase():
    print("\nTesting Supabase connection...")
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")

    if not url or "your-project" in url:
        print("Supabase URL not configured in .env")
        return

    try:
        from supabase import create_client

        client = create_client(url, key)
        client.table("paper_portfolio").select("id").limit(1).execute()
        print("Supabase connected and tables are ready.")
    except Exception as exc:
        print(f"Supabase failed: {exc}")
        print("Make sure you ran the SQL schema in the Supabase dashboard")


def test_env_vars():
    print("\nChecking environment variables...")
    required = [
        "COINDCX_API_KEY",
        "COINDCX_API_SECRET",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "GROQ_API_KEY",
    ]
    all_set = True

    for variable in required:
        value = os.getenv(variable, "")
        if not value or "your_" in value:
            print(f"{variable} - NOT SET")
            all_set = False
        else:
            print(f"{variable} - set")

    if all_set:
        print("All env vars are configured.")


async def main():
    print("=" * 50)
    print("  CRYPTO AGENT - CONNECTION TEST")
    print("=" * 50)

    test_env_vars()
    await test_coindcx_public()
    await test_fear_greed()
    await test_coingecko()
    await test_groq()
    test_supabase()

    print("\n" + "=" * 50)
    print("  Done. Fix any failing checks before starting.")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
