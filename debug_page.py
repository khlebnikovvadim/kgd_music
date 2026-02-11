#!/usr/bin/env python3
"""
Debug script to see what's on the Yandex Music page
"""

import re
from playwright.sync_api import sync_playwright
import time

url = 'https://music.yandex.ru/artist/7927866'

print("Loading page and extracting text...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Show browser
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        locale='ru-RU',
    )
    page = context.new_page()

    page.goto(url, wait_until='domcontentloaded')
    time.sleep(5)  # Wait for JS

    # Get all visible text
    visible_text = page.inner_text('body')

    print("\n" + "="*60)
    print("VISIBLE TEXT ON PAGE (first 3000 chars)")
    print("="*60)
    print(visible_text[:3000])

    print("\n" + "="*60)
    print("SEARCHING FOR KEYWORDS")
    print("="*60)

    keywords = ['слушател', 'listener', 'тыс', 'млн', 'месяц']
    for keyword in keywords:
        matches = re.findall(f'.{{0,50}}{keyword}.{{0,50}}', visible_text, re.IGNORECASE)
        if matches:
            print(f"\n✓ Found '{keyword}':")
            for match in matches[:3]:  # Show first 3
                print(f"  {match.strip()}")
        else:
            print(f"\n✗ Not found: '{keyword}'")

    print("\n" + "="*60)
    print("PAGE TITLE")
    print("="*60)
    print(page.title())

    print("\n" + "="*60)
    print("CHECKING SPECIFIC SELECTORS")
    print("="*60)

    selectors = [
        'h1',
        '[class*="title"]',
        '[class*="stat"]',
        '[class*="listener"]',
        'div',
    ]

    for selector in selectors:
        elements = page.query_selector_all(selector)
        print(f"\n{selector}: {len(elements)} elements")
        for elem in elements[:3]:
            try:
                text = elem.inner_text()[:100]
                if 'слушател' in text.lower():
                    print(f"  → {text}")
            except:
                pass

    browser.close()

print("\n" + "="*60)
print("Debug complete!")
print("="*60)
