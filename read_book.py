#!/usr/bin/env python3
"""
Example script to read and display a saved children's book.
Usage: python read_book.py generated_books/book_20251005_143022
"""

import json
import sys
import os
from PIL import Image


def read_book(book_folder: str):
    """Read and display information about a saved book."""

    # Read the JSON metadata
    json_path = os.path.join(book_folder, "book_data.json")

    if not os.path.exists(json_path):
        print(f"Error: Could not find book_data.json in {book_folder}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        book_data = json.load(f)

    # Display book information
    print("=" * 80)
    print("📚 CHILDREN'S BOOK")
    print("=" * 80)
    print(f"\n📝 Prompt: {book_data['prompt']}")
    print(f"🕐 Generated: {book_data['generated_at']}")
    print(f"📄 Total Pages: {len(book_data['pages'])}")
    print("\n" + "=" * 80)

    # Display each page
    for page in book_data['pages']:
        page_num = page['page_number']
        text = page['text']
        image_file = page['image_file']
        image_path = os.path.join(book_folder, image_file)

        print(f"\n📖 Page {page_num}")
        print("-" * 80)
        print(f"Text: {text}")
        print(f"Image: {image_file}")

        # Check if image exists
        if os.path.exists(image_path):
            img = Image.open(image_path)
            print(f"Image size: {img.size[0]}x{img.size[1]} pixels")
        else:
            print("⚠️  Warning: Image file not found")

    print("\n" + "=" * 80)
    print("✅ Book data loaded successfully!")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python read_book.py <book_folder_path>")
        print("\nExample:")
        print("  python read_book.py generated_books/book_20251005_143022")

        # Try to find the most recent book
        if os.path.exists("generated_books"):
            books = [d for d in os.listdir("generated_books")
                     if os.path.isdir(os.path.join("generated_books", d))]
            if books:
                books.sort(reverse=True)
                latest_book = os.path.join("generated_books", books[0])
                print(f"\n📚 Found most recent book: {latest_book}")
                print("Reading it now...\n")
                read_book(latest_book)
            else:
                print("\n⚠️  No books found in generated_books folder.")
        sys.exit(1)

    book_folder = sys.argv[1]

    if not os.path.exists(book_folder):
        print(f"Error: Folder '{book_folder}' does not exist")
        sys.exit(1)

    read_book(book_folder)
