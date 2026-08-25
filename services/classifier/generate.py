import pandas as pd
import re
import requests
import time
import csv
import json

input_path = "data/song_lyrics.csv"
output_path = "data/human_lyrics_cleaned_25k.csv"
chunksize = 100_000
max_rows = 25_000
rows_written = 0
header_written = False

def clean_lyrics(text):
    if pd.isna(text):
        return ""
    text = re.sub(r"\[.*?\]", "", text)            # remove [Chorus], [Verse 1], etc.
    text = re.sub(r"\s+", " ", text)               # normalize whitespace
    return text.strip()

def load_from_csv():
    with open(output_path, mode='w', encoding='utf-8') as f_out:
        for chunk in pd.read_csv(input_path, chunksize=chunksize):
            if "lyrics" not in chunk.columns:
                raise ValueError("Column 'lyrics' not found in CSV!")

            chunk = chunk[["lyrics"]].dropna()
            chunk = chunk[chunk["lyrics"].str.len() > 100]

            # 🧼 Clean lyrics: remove [brackets] + collapse whitespace
            chunk["lyrics"] = chunk["lyrics"].astype(str).apply(clean_lyrics)

            chunk["label"] = 0  # human-written

            # Write only what's needed to stay within limit
            remaining = max_rows - rows_written
            if remaining <= 0:
                break

            chunk_to_write = chunk.iloc[:remaining]
            chunk_to_write.to_csv(f_out, index=False, header=not header_written)
            rows_written += len(chunk_to_write)
            header_written = True

            print(f"✅ Wrote {rows_written} rows...")

    print("🎉 Done. Cleaned file saved to", output_path)


NUM_LYRICS = 10
API_URL = "http://localhost:1234/v1/chat/completions"

HEADERS = {
    "Content-Type": "application/json"
}

SYSTEM_PROMPT = """
Generate lyrics for a song.
"""

def generate_lyrics():
    body = {
        "model": "qwen:chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
        ],
        "temperature": 1.0,
        "max_tokens": 4096
    }
    try:
        response = requests.post(API_URL, headers=HEADERS, json=body)
        response.raise_for_status()

        raw_content = response.json()['choices'][0]['message']['content'].strip()
        parsed = json.loads(raw_content)

        return parsed['lyrics']
    except Exception as e:
        print("❌ Error:", e)
        return None
def remove_think_blocks(text):
    return re.sub(r'<\s*think\s*>.*?<\s*/\s*think\s*>', '', text, flags=re.DOTALL | re.IGNORECASE)

def save_to_csv(lyrics_list, filename="ai_lyrics.csv"):
    with open(filename, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["lyrics", "label"])
        writer.writeheader()
        for lyric in lyrics_list:
            writer.writerow({"lyrics": lyric, "label": 1})

def main():
    lyrics_data = []
    while len(lyrics_data) < NUM_LYRICS:
        print(f"🔄 Generating lyric {len(lyrics_data)+1}/{NUM_LYRICS}...")
        lyric = generate_lyrics()
        lyric = remove_think_blocks(lyric)
        if lyric:
            lyrics_data.append(lyric)
        time.sleep(1)  # Optional: avoid overloading local server
    save_to_csv(lyrics_data)
    print("✅ Done. Saved to ai_lyrics.csv.")

if __name__ == "__main__":
    main()
