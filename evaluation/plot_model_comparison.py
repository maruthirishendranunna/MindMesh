import os
import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = "evaluation/model_comparison_results.csv"
OUTPUT_DIR = "evaluation/plots_by_dataset"

os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_csv(INPUT_CSV)
df.columns = [c.strip() for c in df.columns]

# Group by dataset + model
summary = (
    df.groupby(["dataset", "model"])
    .agg(
        avg_keyword_accuracy=("keyword_accuracy_score", "mean"),
        avg_response_time=("response_time_seconds", "mean"),
        avg_word_count=("answer_word_count", "mean"),
        total_errors=("error", lambda x: sum(1 for v in x if str(v).strip())),
    )
    .reset_index()
)

# Save dataset-wise summary
summary.to_csv("evaluation/model_comparison_summary_by_dataset.csv", index=False)

datasets = summary["dataset"].unique()

for dataset in datasets:
    dataset_df = summary[summary["dataset"] == dataset].copy()
    dataset_name = dataset.replace("_adapter", "")

    # -----------------------------
    # 1. Accuracy chart per dataset
    # -----------------------------
    plt.figure(figsize=(8, 5))
    plt.bar(dataset_df["model"], dataset_df["avg_keyword_accuracy"])
    plt.title(f"{dataset_name.upper()} - Model Accuracy Comparison")
    plt.xlabel("Model")
    plt.ylabel("Average Keyword Accuracy")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/{dataset_name}_accuracy_comparison.png", dpi=300)
    plt.close()

    # -----------------------------
    # 2. Response time chart per dataset
    # -----------------------------
    plt.figure(figsize=(8, 5))
    plt.bar(dataset_df["model"], dataset_df["avg_response_time"])
    plt.title(f"{dataset_name.upper()} - Model Response Time Comparison")
    plt.xlabel("Model")
    plt.ylabel("Average Response Time (seconds)")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/{dataset_name}_response_time_comparison.png", dpi=300)
    plt.close()

    # -----------------------------
    # 3. Output length chart per dataset
    # -----------------------------
    plt.figure(figsize=(8, 5))
    plt.bar(dataset_df["model"], dataset_df["avg_word_count"])
    plt.title(f"{dataset_name.upper()} - Model Output Length Comparison")
    plt.xlabel("Model")
    plt.ylabel("Average Word Count")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/{dataset_name}_output_length_comparison.png", dpi=300)
    plt.close()

    # -----------------------------
    # 4. Combined normalized chart per dataset
    # -----------------------------
    combined = dataset_df[
        ["model", "avg_keyword_accuracy", "avg_response_time", "avg_word_count"]
    ].copy()

    combined["accuracy_norm"] = (
        combined["avg_keyword_accuracy"] / combined["avg_keyword_accuracy"].max()
        if combined["avg_keyword_accuracy"].max() != 0 else 0
    )

    combined["time_norm"] = (
        combined["avg_response_time"] / combined["avg_response_time"].max()
        if combined["avg_response_time"].max() != 0 else 0
    )

    combined["words_norm"] = (
        combined["avg_word_count"] / combined["avg_word_count"].max()
        if combined["avg_word_count"].max() != 0 else 0
    )

    x = range(len(combined))
    width = 0.25

    plt.figure(figsize=(10, 6))
    plt.bar([i - width for i in x], combined["accuracy_norm"], width=width, label="Accuracy")
    plt.bar(x, combined["time_norm"], width=width, label="Response Time")
    plt.bar([i + width for i in x], combined["words_norm"], width=width, label="Output Length")

    plt.title(f"{dataset_name.upper()} - Normalized Model Comparison")
    plt.xlabel("Model")
    plt.ylabel("Normalized Score")
    plt.xticks(x, combined["model"], rotation=25, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/{dataset_name}_combined_comparison.png", dpi=300)
    plt.close()

print("✅ Dataset-wise graphs created successfully!")
print(f"Saved in: {OUTPUT_DIR}")
print("✅ Dataset-wise summary saved: evaluation/model_comparison_summary_by_dataset.csv")