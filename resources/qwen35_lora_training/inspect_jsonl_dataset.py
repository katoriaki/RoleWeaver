import argparse
import random

from datasets import load_dataset


def main():
    parser = argparse.ArgumentParser(description="Inspect a JSONL SFT dataset")
    parser.add_argument("--data-file", default="meiling_sft_updated_v2.jsonl")
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    dataset = load_dataset("json", data_files=args.data_file, split="train")
    print("dataset size:", len(dataset))
    print("columns:", dataset.column_names)
    print("sample[0]:", dataset[0])

    for i in random.sample(range(len(dataset)), min(args.samples, len(dataset))):
        print("=" * 50)
        print(dataset[i])


if __name__ == "__main__":
    main()
