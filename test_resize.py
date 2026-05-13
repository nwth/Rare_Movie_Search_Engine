"""Test image resize + SerpApi base64 Google Lens."""
import asyncio
import base64
import io
import httpx
from PIL import Image

SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"


async def test():
    # Load and resize image
    img = Image.open("testset/p2615193241.webp")
    print(f"Original: {img.size}")

    # Try different sizes to find the sweet spot
    for max_size in [300, 200, 150, 100]:
        im = img.copy()
        im.thumbnail((max_size, max_size))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=70)
        b64 = base64.b64encode(buf.getvalue()).decode()
        url_len = len(f"https://serpapi.com/search?api_key={SERPAPI_KEY[:8]}...&engine=google_lens&image_base64={b64}")
        print(f"\nSize {max_size}: JPEG={buf.tell()/1024:.0f}KB, Base64={len(b64)}chars, Est.URL={url_len}chars")

        if url_len > 7000:
            print("  -> TOO LONG, skip")
            continue

        # Test with SerpApi
        params = {
            "api_key": SERPAPI_KEY,
            "engine": "google_lens",
            "image_base64": b64,
        }
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get("https://serpapi.com/search", params=params)
            if r.status_code == 200:
                d = r.json()
                err = d.get("error")
                if err:
                    print(f"  Error: {err[:150]}")
                else:
                    vms = d.get("visual_matches", [])
                    print(f"  OK! Visual matches: {len(vms)}")
                    for i, v in enumerate(vms[:3]):
                        t = v.get("title") or v.get("source", "?")
                        print(f"    {i+1}. {str(t)[:70]}")
                    kg = d.get("knowledge_graph", {})
                    if kg:
                        title = kg.get("title", "")
                        print(f"    KG: {title}")
                    break  # Success!
            else:
                print(f"  Status {r.status_code}")
                if r.status_code == 414:
                    print("  -> URI Too Long, try smaller size")

    print("\nDone!")


asyncio.run(test())
