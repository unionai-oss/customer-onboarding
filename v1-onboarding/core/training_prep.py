import shutil
import random
import os

SEED = 42


def create_split_dirs(class_names, dest_dir):
    for split in ["train", "test"]:
        for class_name in class_names:
            split_dir = os.path.join(dest_dir, split, class_name)
            os.makedirs(split_dir, exist_ok=True)


def split_and_copy(dest_dir, source_dir, split_ratio):
    random.seed(SEED)
    class_names = [
        d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))
    ]
    create_split_dirs(class_names, dest_dir)

    for class_name in class_names:
        class_dir = os.path.join(source_dir, class_name)
        images = [
            f
            for f in os.listdir(class_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        random.shuffle(images)

        split_idx = int(len(images) * split_ratio)
        train_files = images[:split_idx]
        test_files = images[split_idx:]

        for fname in train_files:
            src = os.path.join(class_dir, fname)
            dst = os.path.join(dest_dir, "train", class_name, fname)
            shutil.copy2(src, dst)

        for fname in test_files:
            src = os.path.join(class_dir, fname)
            dst = os.path.join(dest_dir, "test", class_name, fname)
            shutil.copy2(src, dst)

        print(
            f"Class '{class_name}': {len(images)} files split into "
            f"{len(train_files)} train, {len(test_files)} test"
        )
