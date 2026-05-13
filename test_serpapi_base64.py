"""Test SerpApi Google Lens with base64-encoded local images."""
import asyncio
import base64
import httpx
import json
import pathlib

SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"


async def test_image(filename):
    """Test SerpApi image_base64 with a local image."""
    filepath = pathlib.Path("testset") / filename
    if not filepath.exists():
        print(f"File not found: {filename}")
        return

    b64 = base64.b64encode(filepath.read_bytes()).decode()
    print(f"\n{'=' * 60}")
    print(f"Testing: {filename} ({filepath.stat().st_size/1024:.0f} KB)")
    print(f"{'=' * 60}")

    form_data = {
        "api_key": SERPAPI_KEY,
        "engine": "google_lens",
        "image_base64": b64,
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://serpapi.com/search", data=form_data)
        data = r.json()

        error = data.get("error")
        if error:
            print(f"SerpApi Error: {error}")
            return

        kg = data.get("knowledge_graph", {})
        if kg:
            title = kg.get("title", "")
            desc = kg.get("description", "")
            print(f"Knowledge Graph:")
            print(f"  Title: {title}")
            print(f"  Desc:  {str(desc)[:100]}")

        ai = data.get("ai_overview", {})
        if ai:
            summary = ai.get("summary", str(ai))[:150]
            print(f"AI Overview:")
            print(f"  {summary}")

        vms = data.get("visual_matches", [])
        print(f"Visual Matches: {len(vms)}")
        for i, v in enumerate(vms[:5]):
            title = v.get("title") or v.get("source", "?")
            print(f"  {i+1}. {str(title)[:70]}")

        # Show top result text
        if vms:
            print(f"\nBest guess: {str(vms[0].get('title', '?'))[:80]}")

        print(f"\nResponse keys: {list(data.keys())}")


async def main():
    print("SerpApi base64 Image Search Test")
    print("Testing with testset images...")

    await test_image("p2615193241.webp")
    await test_image("p2898894527.webp")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
