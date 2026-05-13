"""Debug SerpApi 400 error with resized image."""
import asyncio
import base64
import io
import httpx
from PIL import Image

SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"


async def test():
    img = Image.open("testset/p2615193241.webp")
    img.thumbnail((150, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"Image: 150px, {buf.tell()/1024:.0f}KB, base64={len(b64)}chars")

    # Try with dummy URL + image_base64 together
    print("\n--- image_base64 + dummy URL ---")
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_lens",
        "url": "https://example.com/test.jpg",
        "image_base64": b64,
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://serpapi.com/search", params=params)
        print(f"Status: {r.status_code}")
        d = r.json()
        err = d.get("error")
        if err:
            print(f"Error: {err}")
        else:
            vms = d.get("visual_matches", [])
            print(f"Visual matches: {len(vms)}")
            for i, v in enumerate(vms[:3]):
                t = v.get("title") or v.get("source", "?")
                print(f"  {i+1}. {str(t)[:70]}")

    # Also try with URL-based approach for comparison
    print("\n--- URL-based (Inception poster) ---")
    url_params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_lens",
        "url": "https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
    }
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://serpapi.com/search", params=url_params)
        print(f"Status: {r.status_code}")
        d = r.json()
        err = d.get("error")
        if err:
            print(f"Error: {err}")
        else:
            vms = d.get("visual_matches", [])
            print(f"Visual matches: {len(vms)}")
            for i, v in enumerate(vms[:3]):
                t = v.get("title") or v.get("source", "?")
                print(f"  {i+1}. {str(t)[:70]}")


asyncio.run(test())
