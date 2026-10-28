
import time
from pathlib import Path
from io import BytesIO

import requests
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
IMAGE_DIR = BASE_DIR / "static" / "generated"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://aihorde.net/api/v2"

HEADERS = {
    "apikey": "0000000000",
    "Client-Agent": "CodeStoryAI:1.0:local"
}


def generate_scene_image(prompt, filename):
    """Generate an AI image for a story scene."""

    safe_filename = Path(filename).name
    image_path = IMAGE_DIR / safe_filename

    if image_path.suffix.lower() != ".png":
        image_path = image_path.with_suffix(".png")

    # Submit image generation request
    response = requests.post(
        f"{API_URL}/generate/async",
        headers=HEADERS,
        json={
            "prompt": prompt,
            "params": {
                "width": 512,
                "height": 512,
                "steps": 20,
                "n": 1
            },
            "nsfw": False,
            "censor_nsfw": True,
            "r2": True
        },
        timeout=30
    )

    response.raise_for_status()
    job = response.json()
    job_id = job.get("id")

    if not job_id:
        raise RuntimeError(f"Image request failed: {job}")

    print("Image request submitted. Waiting for generation...")

    # Check generation status
    start_time = time.time()

    while time.time() - start_time < 600:
        status_response = requests.get(
            f"{API_URL}/generate/check/{job_id}",
            headers=HEADERS,
            timeout=30
        )

        status_response.raise_for_status()
        status = status_response.json()

        if status.get("faulted"):
            raise RuntimeError("Image generation failed.")

        if status.get("done"):
            break

        print("Image is still in the queue...")
        time.sleep(5)
    else:
        raise TimeoutError("Image generation took too long.")

    # Retrieve generated image
    result_response = requests.get(
        f"{API_URL}/generate/status/{job_id}",
        headers=HEADERS,
        timeout=30
    )

    result_response.raise_for_status()
    result = result_response.json()

    generations = result.get("generations", [])

    if not generations:
        raise RuntimeError("No image was returned.")

    image_url = generations[0].get("img")

    if not image_url:
        raise RuntimeError("Image URL was not found.")

    # Download and save image
    image_response = requests.get(image_url, timeout=60)
    image_response.raise_for_status()

    image = Image.open(BytesIO(image_response.content))
    image.save(image_path, format="PNG")

    print(f"Image saved successfully: {image_path}")

    return f"generated/{image_path.name}"
