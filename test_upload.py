"""Test image upload + SerpApi pipeline."""
import asyncio
import base64
import httpx
import json

SERPAPI_KEY = "b9687056aeeec9b2bad9c145808896bd9b76a379ce6858618a372057e68c1057"


async def test_telegraph_upload():
    """Test telegra.ph upload with test image."""
    print("=" * 60)
    print("Test 1: Telegra.ph Upload")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=20) as c:
        with open("testset/p2615193241.webp", "rb") as f:
            files = {"file": ("image.jpg", f, "image/jpeg")}
            r = await c.post("https://telegra.ph/upload", files=files)
        print(f"Status: {r.status_code}")
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            src = data[0].get("src", "")
            if src:
                url = f"https://telegra.ph{src}" if src.startswith("/") else src
                print(f"Upload OK: {url}")

                # Test SerpApi with this URL
                print("\n--- SerpApi with uploaded URL ---")
                params = {
                    "api_key": SERPAPI_KEY,
                    "engine": "google_lens",
                    "url": url,
                    "auto_crop": "true",
                }
                r2 = await c.get("https://serpapi.com/search", params=params, timeout=20)
                d2 = r2.json()
                err = d2.get("error")
                if err:
                    print(f"SerpApi Error: {err[:200]}")
                else:
                    vms = d2.get("visual_matches", [])
                    print(f"Visual matches: {len(vms)}")
                    for i, v in enumerate(vms[:5]):
                        title = v.get("title") or v.get("source", "?")
                        print(f"  {i+1}. {str(title)[:70]}")
                    kg = d2.get("knowledge_graph", {})
                    if kg:
                        print(f"KG: {kg.get('title', '')}")
            else:
                print(f"No src in response: {data}")
        else:
            print(f"Upload failed: {r.text[:200]}")


async def test_pipeline_direct():
    """Test the full pipeline via Python imports."""
    print("\n" + "=" * 60)
    print("Test 2: Full pipeline via Python API")
    print("=" * 60)

    from core.image_search import ImageSearchOrchestrator

    with open("testset/p2615193241.webp", "rb") as f:
        img_bytes = f.read()
    b64 = base64.b64encode(img_bytes).decode()
    data_uri = f"data:image/webp;base64,{b64}"

    print(f"Data URI length: {len(data_uri)} chars")

    orch = ImageSearchOrchestrator()
    movie = await orch.identify_movie(data_uri)

    if movie:
        print(f"Identified: '{movie.title}' ({movie.year})")
        print(f"IMDb: {movie.imdb_id}")
        print(f"Poster: {str(movie.poster_url)[:60] if movie.poster_url else 'N/A'}")
    else:
        print("Could not identify movie")


async def main():
    await test_telegraph_upload()
    await test_pipeline_direct()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
