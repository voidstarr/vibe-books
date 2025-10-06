# 📚 Children's Book Generator

An AI-powered application that generates complete children's books with story text and illustrations using OpenRouter API and Gradio.

## Features

- 📝 Generates a 10-page story script (1-2 sentences per page)
- 🎨 Creates 10 unique AI-generated illustrations using image generation models
- �️ **Style Consistency**: Uses the first generated image as a reference for all subsequent images to maintain consistent art style throughout the book
- �📖 Displays the complete storyboard in an interactive gallery
- 💾 Automatically saves each book to a timestamped folder with:
  - JSON metadata file with all page texts
  - Numbered PNG images (page_01.png through page_10.png)
  - Complete book data organized and ready to share
- 🖥️ User-friendly Gradio web interface

## Setup

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 2. Configure API Key

1. Get your OpenRouter API key from [https://openrouter.ai/keys](https://openrouter.ai/keys)
2. Open the `.env` file and replace `your_openrouter_api_key_here` with your actual API key:

```
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

### 3. Run the Application

```bash
python app.py
```

The Gradio interface will launch and provide you with a local URL (typically `http://127.0.0.1:7860`).

## Usage

1. Enter a story prompt in the text box (e.g., "A brave little mouse who goes on an adventure to find the moon cheese")
2. Click the "🎨 Generate Book" button
3. Wait while the AI:
   - Generates the 10-page story script
   - Creates 10 illustrations (one for each page)
   - Saves everything to a timestamped folder
4. View your complete children's book in the gallery!
5. Find your saved book in the `generated_books/` folder with structure:
   ```
   generated_books/
   └── book_20251005_143022/
       ├── book_data.json
       ├── page_01.png
       ├── page_02.png
       ├── ...
       └── page_10.png
   ```

## How It Works

1. **Story Generation**: Uses OpenRouter's LLM (Google Gemini by default) to create a cohesive 10-page story
2. **First Image Generation**: Creates the first illustration which establishes the art style
3. **Consistent Style Generation**: Uses the first image as a reference for pages 2-10, ensuring consistent character designs, color palettes, and artistic style throughout the book
4. **Storyboard Assembly**: Combines text and images into a gallery format for easy viewing
5. **Book Storage**: Saves each book to a timestamped folder with JSON metadata and numbered images

## Configuration

You can modify the LLM model in `app.py` by changing the `model` parameter in the `generate_story_script` function:

```python
model="google/gemini-2.5-flash-preview-09-2025"  # Change to your preferred model
```

You can also modify the image generation model in the `generate_image` function:

```python
model="google/gemini-2.5-flash-image-preview"  # Change to your preferred image model
```

### JSON Book Data Format

Each generated book includes a `book_data.json` file with the following structure:

```json
{
  "prompt": "Your original story prompt",
  "generated_at": "2025-10-05T14:30:22.123456",
  "pages": [
    {
      "page_number": 1,
      "text": "The text for page 1...",
      "image_file": "page_01.png"
    },
    ...
  ]
}
```

## Requirements

- Python 3.8+
- OpenRouter API key with credits
- Internet connection for API calls

## Notes

- Image generation may take a few minutes depending on API response times
- Ensure you have sufficient credits in your OpenRouter account
- The app uses OpenRouter's API for both text and image generation

## Acknowledgements

- Dex

## License

MIT License - Feel free to modify and use as needed!
