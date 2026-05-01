import os
import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = "evaluation/model_comparison_summary.csv"
OUTPUT_DIR = "evaluation/plots"

os.makedirs(OUTPUT_DIR, exist_ok=True)

df = pd.read_csv(INPUT_CSV)

# Clean column names just in case
df.columns = [c.strip() for c in df.columns]

# Create display name
df["display_model"] = df["model"].astype(str)

# -----------------------------
# 1. Accuracy chart
# -----------------------------
plt.figure(figsize=(8, 5))
plt.bar(df["display_model"], df["avg_keyword_accuracy"])
plt.title("Model Accuracy Comparison")
plt.xlabel("Model")
plt.ylabel("Average Keyword Accuracy")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/model_accuracy_comparison.png", dpi=300)
plt.close()

# -----------------------------
# 2. Response time chart
# -----------------------------
plt.figure(figsize=(8, 5))
plt.bar(df["display_model"], df["avg_response_time"])
plt.title("Model Response Time Comparison")
plt.xlabel("Model")
plt.ylabel("Average Response Time (seconds)")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/model_response_time_comparison.png", dpi=300)
plt.close()

# -----------------------------
# 3. Output length chart
# -----------------------------
plt.figure(figsize=(8, 5))
plt.bar(df["display_model"], df["avg_word_count"])
plt.title("Model Output Length Comparison")
plt.xlabel("Model")
plt.ylabel("Average Word Count")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/model_output_length_comparison.png", dpi=300)
plt.close()

# -----------------------------
# 4. Combined normalized chart
# -----------------------------
combined = df[["display_model", "avg_keyword_accuracy", "avg_response_time", "avg_word_count"]].copy()

combined["accuracy_norm"] = combined["avg_keyword_accuracy"] / combined["avg_keyword_accuracy"].max()
combined["time_norm"] = combined["avg_response_time"] / combined["avg_response_time"].max()
combined["words_norm"] = combined["avg_word_count"] / combined["avg_word_count"].max()

x = range(len(combined))
width = 0.25

plt.figure(figsize=(10, 6))
plt.bar([i - width for i in x], combined["accuracy_norm"], width=width, label="Accuracy")
plt.bar(x, combined["time_norm"], width=width, label="Response Time")
plt.bar([i + width for i in x], combined["words_norm"], width=width, label="Output Length")

plt.title("Normalized Model Comparison")
plt.xlabel("Model")
plt.ylabel("Normalized Score")
plt.xticks(x, combined["display_model"], rotation=25, ha="right")
plt.legend()
plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/combined_model_comparison.png", dpi=300)
plt.close()

print("✅ Graphs created successfully!")
print(f"Saved in: {OUTPUT_DIR}")