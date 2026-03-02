#!/usr/bin/env python3
"""
Create top-30 artists by listener count
"""

import pandas as pd
import re

# Extract artist IDs from artists.txt
tracked_artists = set()
with open('artists.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            match = re.search(r'/artist/(\d+)', line)
            if match:
                tracked_artists.add(int(match.group(1)))

print(f"Found {len(tracked_artists)} unique artists in tracking list")

# Read exclude list
excluded_artists = set()
try:
    with open('exclude_artists.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Extract just the number, ignore comments
                artist_id = line.split('#')[0].strip()
                if artist_id.isdigit():
                    excluded_artists.add(int(artist_id))
    print(f"Found {len(excluded_artists)} artists to exclude")
except FileNotFoundError:
    print("No exclude list found, including all tracked artists")

# Read the CSV
df = pd.read_csv('data/artist_stats.csv')

# Get only the latest date
latest_date = df['date'].max()
df = df[df['date'] == latest_date]
print(f"Using data from: {latest_date}")

# Filter to only include tracked artists and exclude the excluded ones
df_filtered = df[df['artist_id'].isin(tracked_artists) & ~df['artist_id'].isin(excluded_artists)]
print(f"Filtered to {len(df_filtered)} artists (after exclusions)")

# Sort by listeners (descending) and take top 30
top30 = df_filtered.nlargest(30, 'lastMonthListeners')[['artist_id', 'artist_name', 'lastMonthListeners', 'genre', 'date']]

# Reset index and add rank
top30 = top30.reset_index(drop=True)
top30.index = top30.index + 1  # Start from 1
top30.index.name = 'rank'

# Save to file
output_file = 'data/top30_artists.csv'
top30.to_csv(output_file)

# Also create a readable text version
text_output = 'data/top30_artists.txt'
with open(text_output, 'w', encoding='utf-8') as f:
    f.write("="*70 + "\n")
    f.write("TOP-30 ARTISTS BY LISTENER COUNT\n")
    f.write(f"Data from: {latest_date}\n")
    f.write("="*70 + "\n\n")

    for idx, row in top30.iterrows():
        listeners = f"{int(row['lastMonthListeners']):,}" if pd.notna(row['lastMonthListeners']) else "N/A"
        f.write(f"{idx:2d}. {row['artist_name']:30s} | {listeners:>12s} listeners | {row['genre']}\n")

# Create markdown version with hyperlinks for Anytype
md_output = 'data/top30_artists.md'
with open(md_output, 'w', encoding='utf-8') as f:
    f.write("| Место | Проект | Слушателей за предыдущий месяц | Жанр |\n")
    f.write("|-------|--------|-------------------------------|------|\n")

    for idx, row in top30.iterrows():
        artist_id = int(row['artist_id'])
        artist_name = row['artist_name']
        listeners = f"{int(row['lastMonthListeners']):,}".replace(',', ' ') if pd.notna(row['lastMonthListeners']) else "N/A"
        genre = row['genre']
        link = f"https://music.yandex.ru/artist/{artist_id}"
        f.write(f"| {idx} | [{artist_name}]({link}) | {listeners} | {genre} |\n")

print(f"✓ Saved to: {md_output}")

# Display results
print("="*70)
print("TOP-30 ARTISTS BY LISTENER COUNT")
print("="*70)
for idx, row in top30.iterrows():
    listeners = f"{int(row['lastMonthListeners']):,}" if pd.notna(row['lastMonthListeners']) else "N/A"
    print(f"{idx:2d}. {row['artist_name']:30s} | {listeners:>12s} listeners | {row['genre']}")

print("\n" + "="*70)
print(f"✓ Saved to: {output_file}")
print(f"✓ Saved to: {text_output}")
print("="*70)
