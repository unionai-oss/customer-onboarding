import pandas as pd
import numpy as np
import os
import math

# Directory to save datasets
OUTPUT_DIR = "./datasets"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Approximate target sizes (bytes)
TARGET_SIZES = {
    "50MB": 6 * 50 * 1024**2,
    "200MB": 6 * 200 * 1024**2,
    "500MB": 6 * 500 * 1024**2,
    "2GB": 6 * 2 * 1024**3,
    "5GB": 6 * 5 * 1024**3,
}

# Estimate: roughly 400 bytes per row (for 10 columns of mixed data)
BYTES_PER_ROW = 400


def estimate_rows(size_bytes: int) -> int:
    return math.ceil(size_bytes / BYTES_PER_ROW)


def generate_df(n: int) -> pd.DataFrame:
    """Generate a synthetic DataFrame with mixed data types."""
    return pd.DataFrame(
        {
            "id": np.arange(n, dtype=np.int64),
            "float_col": np.arange(n, dtype=np.float64) * 0.001,
            "category": np.random.choice(list("ABCDEFGHIJ"), size=n),
            "bool_col": np.random.choice([True, False], size=n),
            "text": np.random.choice(
                ["spooky castle", "haunted house", "pumpkin", "ghost", "bat"], size=n
            ),
            "int1": np.random.randint(0, 10000, size=n, dtype=np.int32),
            "int2": np.random.randint(0, 10000, size=n, dtype=np.int32),
            "float2": np.random.randn(n),
            "small_text": np.random.choice(["yes", "no"], size=n),
            "category2": np.random.choice(["A", "B", "C", "D"], size=n),
        }
    )


for label, size_bytes in TARGET_SIZES.items():
    n_rows = estimate_rows(size_bytes)
    print(f"Generating {label} dataset with ~{n_rows:,} rows...")

    df = generate_df(n_rows)

    file_path = os.path.join(OUTPUT_DIR, f"dataset_{label}.csv")

    # Write to Parquet (recommended for compactness and speed)
    df.to_csv(file_path, index=False)

    actual_size = os.path.getsize(file_path)
    print(f"✅ Saved {file_path} ({actual_size / 1024**2:.2f} MB)\n")

print("🎃 All datasets generated successfully!")
