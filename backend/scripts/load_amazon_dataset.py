"""
Download Amazon products from HuggingFace and generate sample_products.json.

Dataset: milistu/AMAZON-Products-2023 (117K products, 30 categories)
Output:  backend/data/sample_products.json

Usage:
    python scripts/load_amazon_dataset.py [--products 500]
"""

import json
import sys
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_CATEGORIES = {
    "AMAZON FASHION",
    "All Beauty",
    "Handmade",
}

# Per-category cap to ensure diversity (total will be ~N_PRODUCTS)
PER_CATEGORY_CAP = 400

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "sample_products.json"
QDRANT_RESET_HINT = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_text(text: str | list | None) -> str:
    if not text:
        return ""
    if isinstance(text, list):
        text = " ".join(str(t) for t in text if t)
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text[:1000]  # cap description length


def extract_price(raw) -> float | None:
    if raw is None:
        return None
    try:
        price = float(str(raw).replace("$", "").replace(",", "").strip())
        return price if 0 < price < 10_000 else None
    except (ValueError, TypeError):
        return None


def build_product(row: dict, idx: int) -> dict | None:
    title = clean_text(row.get("title"))
    description = clean_text(row.get("description") or row.get("features"))
    image_url = row.get("image") or ""
    price = extract_price(row.get("price"))
    category = clean_text(row.get("main_category"))

    # Skip if missing critical fields
    if not title or not image_url or price is None:
        return None
    if not image_url.startswith("http"):
        return None
    if len(title) < 5:
        return None

    return {
        "id": f"amz_{idx:05d}",
        "name": title[:120],
        "description": description or title,
        "category": category.lower().replace(" ", "_") if category else "other",
        "price": round(price, 2),
        "image_url": image_url,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(n_products: int = 500) -> None:
    print(f"Loading dataset from HuggingFace (target: {n_products} products)...")
    print("This may take a minute on first run (downloads ~1.7 GB).\n")

    from datasets import load_dataset

    ds = load_dataset("milistu/AMAZON-Products-2023", split="train")
    print(f"Dataset loaded: {len(ds):,} total products")

    # Group by category with per-category cap for diversity
    from collections import defaultdict
    buckets: dict[str, list[dict]] = defaultdict(list)
    skipped = 0

    print("Filtering and cleaning products...")
    for i, row in enumerate(ds):
        cat = clean_text(row.get("main_category"))
        if cat not in TARGET_CATEGORIES:
            continue

        # Per-category cap
        if len(buckets[cat]) >= PER_CATEGORY_CAP:
            continue

        product = build_product(row, i)
        if product is None:
            skipped += 1
            continue

        buckets[cat].append(product)

        total = sum(len(v) for v in buckets.values())
        if total >= n_products * 2:  # collect 2x then trim for diversity
            break

    # Flatten and trim to n_products, preserving category diversity
    all_products: list[dict] = []
    for cat_products in buckets.values():
        all_products.extend(cat_products)

    # Shuffle for diversity then take n_products
    import random
    random.seed(42)
    random.shuffle(all_products)
    all_products = all_products[:n_products]

    # Re-assign clean sequential IDs
    for i, p in enumerate(all_products):
        p["id"] = f"amz_{i:05d}"

    print(f"\nProducts collected: {len(all_products)}")
    print(f"Skipped (missing fields): {skipped}")

    # Category breakdown
    from collections import Counter
    cats = Counter(p["category"] for p in all_products)
    print("\nCategory breakdown:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:40s} {count:4d}")

    # Price stats
    prices = [p["price"] for p in all_products]
    print(f"\nPrice range: ${min(prices):.2f} – ${max(prices):.2f}")
    print(f"Avg price:   ${sum(prices)/len(prices):.2f}")

    # Save
    OUTPUT_PATH.write_text(json.dumps(all_products, indent=2, ensure_ascii=False))
    print(f"\nSaved → {OUTPUT_PATH}")
    print(f"Total products: {len(all_products)}")

    if QDRANT_RESET_HINT:
        print("\nNext steps:")
        print("  1. Reset Qdrant collection:")
        print("     python scripts/reset_collection.py")
        print("  2. Index new products:")
        print("     python scripts/index_products.py --force")


if __name__ == "__main__":
    n = 500
    for arg in sys.argv[1:]:
        if arg.startswith("--products"):
            parts = arg.split("=")
            if len(parts) == 2:
                n = int(parts[1])
    main(n_products=n)
