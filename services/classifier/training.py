import pandas as pd
df = pd.read_csv("your_big_lyrics_file.csv")

# Keep only the lyrics column and drop NaNs
df = df[["lyrics"]].dropna()
df = df[df["lyrics"].str.len() > 100]  # filter out super short ones

# Add label for human-written
df["label"] = 0

# Save it
df.to_csv("human_lyrics_cleaned.csv", index=False)
