import gradio as gr
import os
from openai import OpenAI
from PIL import Image, ImageDraw
import io
import base64
import requests
from dotenv import load_dotenv
import json
from datetime import datetime
import concurrent.futures
import tempfile
import traceback

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Allow overriding models via environment variables for faster alternatives
# Set OPENROUTER_TEXT_MODEL and OPENROUTER_IMAGE_MODEL in your .env to change
TEXT_MODEL = os.getenv("OPENROUTER_TEXT_MODEL", "google/gemini-2.5-flash-preview-09-2025")
IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image-preview")


def image_to_base64_data_url(img: Image.Image) -> str:
    """
    Convert a PIL Image to a base64 data URL for use in API requests.
    """
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


def generate_story_script(prompt: str) -> list[str]:
    """
    Generate a 10-page children's book script based on the prompt.
    Each page should have 1-2 sentences.
    """
    system_message = """You are a children's book author. Generate a 10-page children's story script.
Each page should have exactly 1-2 sentences that are engaging, age-appropriate, and tell a cohesive story.
Format your response as exactly 10 pages, numbered 1-10, with each page on its own line starting with "Page X: " followed by the text."""

    try:
        response = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Write a 10-page children's story about: {prompt}"}
            ],
            temperature=0.7,
        )

        story_text = response.choices[0].message.content

        # Parse the story into pages
        pages = []
        lines = story_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if line.startswith('Page'):
                # Extract text after "Page X: "
                if ':' in line:
                    page_text = line.split(':', 1)[1].strip()
                    pages.append(page_text)

        # Ensure we have exactly 10 pages
        if len(pages) < 10:
            # If we didn't get 10 pages, split by sentences
            pages = story_text.split('.')[:10]
            pages = [p.strip() + '.' for p in pages if p.strip()]

        return pages[:10]  # Return exactly 10 pages

    except Exception as e:
        return [f"Error generating story: {str(e)}"] * 10


def generate_image(page_text: str, page_number: int, overall_prompt: str, reference_image: Image.Image = None) -> Image.Image:
    """
    Generate an image for a specific page using image generation through OpenRouter.
    If reference_image is provided, it will be used to maintain consistent style.
    """
    try:
        # Create a detailed image prompt based on the page text
        if reference_image is not None:
            image_prompt = f"""
            Children's book illustration. Use the same art style, color palette, and visual aesthetic as the reference image provided.
            Scene from a story about {overall_prompt}.
            This is page {page_number} of the book. Put the page number in the bottom right corner of the image.
            Page content: {page_text}
            
            IMPORTANT: Match the artistic style, character design, colors, and overall look of the reference image.
            """
        else:
            image_prompt = f"""
            Children's book illustration style, colorful and friendly
            Scene from a story about {overall_prompt}.
            This is page {page_number} of the book. Put the page number in the bottom right corner of the image.
            Page content: {page_text}
            """

        # Build the messages array
        messages = []

        if reference_image is not None:
            # Include the reference image in the message
            reference_data_url = image_to_base64_data_url(reference_image)
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Reference image for style:"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": reference_data_url
                        }
                    },
                    {
                        "type": "text",
                        "text": image_prompt
                    }
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": image_prompt
            })

        # Use chat completions endpoint with modalities for image generation
        response = client.chat.completions.create(
            model=IMAGE_MODEL,
            messages=messages,
            modalities=["image", "text"]
        )

        # Extract the image from the response
        message = response.choices[0].message

        # Validate structure
        if not (hasattr(message, 'model_extra') and isinstance(message.model_extra, dict)):
            raise Exception("No model_extra in image response")

        images_meta = message.model_extra.get('images') if isinstance(message.model_extra, dict) else None
        if not images_meta:
            raise Exception("No images in response")

        # Get the first image entry safely
        image_entry = images_meta[0]
        # Support either 'image_url' key or a direct url field
        image_data_url = None
        if isinstance(image_entry, dict):
            image_url_field = image_entry.get('image_url') or image_entry.get('url')
            if isinstance(image_url_field, dict):
                image_data_url = image_url_field.get('url')
            else:
                image_data_url = image_url_field

        if not image_data_url:
            raise Exception("No image URL/data found in response entry")

        # Helper to write debug bytes when decoding fails
        def _save_debug(bytes_blob: bytes, suffix: str = '.bin') -> str:
            try:
                fd, path = tempfile.mkstemp(prefix=f"vibe_image_debug_p{page_number}_", suffix=suffix, dir='.')
                with os.fdopen(fd, 'wb') as f:
                    f.write(bytes_blob)
                print(f"Saved debug image bytes to: {path}")
                return path
            except Exception as e:
                print(f"Failed to save debug file: {e}")
                return '<failed-to-save>'

        # If it's a data URL, decode and open
        if isinstance(image_data_url, str) and image_data_url.startswith('data:image'):
            try:
                base64_data = image_data_url.split(',', 1)[1]
                image_bytes = base64.b64decode(base64_data)
            except Exception as e:
                print(f"Failed to decode base64 image for page {page_number}: {e}")
                _save_debug(image_data_url.encode('utf-8'), suffix='.txt')
                raise

            try:
                img = Image.open(io.BytesIO(image_bytes))
                img.load()
                return img
            except Exception as e:
                print(f"PIL failed to open decoded image bytes for page {page_number}: {e}")
                _save_debug(image_bytes, suffix='.bin')
                raise
        else:
            # Otherwise treat it as a URL and download it
            try:
                img_response = requests.get(image_data_url, timeout=30)
                img_response.raise_for_status()
                content = img_response.content
            except Exception as e:
                print(f"Failed to download image URL for page {page_number}: {e}")
                raise

            try:
                img = Image.open(io.BytesIO(content))
                img.load()
                return img
            except Exception as e:
                print(f"PIL failed to open downloaded image for page {page_number}: {e}")
                dbg = _save_debug(content, suffix='.bin')
                print(f"Wrote failing image bytes to {dbg} for inspection")
                raise

    except Exception as e:
        print(f"Error generating image for page {page_number}: {str(e)}")
        # Create a placeholder image with error text
        img = Image.new('RGB', (512, 512), color='lightgray')
        # draw the error on the image
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), f"Error: {str(e)}", fill="red")
        return img


def save_book_to_folder(prompt: str, pages: list[str], images: list[Image.Image]) -> str:
    """
    Save the generated book to a timestamped folder with JSON metadata and numbered images.
    Returns the folder path.
    """
    # Create timestamp folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"book_{timestamp}"
    folder_path = os.path.join("generated_books", folder_name)

    # Create the folder
    os.makedirs(folder_path, exist_ok=True)

    # Prepare book data for JSON
    book_data = {
        "prompt": prompt,
        "generated_at": datetime.now().isoformat(),
        "pages": []
    }

    # Save each image and add metadata to JSON
    for i, (page_text, img) in enumerate(zip(pages, images), start=1):
        # Save image with numbered filename
        image_filename = f"page_{i:02d}.png"
        image_path = os.path.join(folder_path, image_filename)
        img.save(image_path, "PNG")

        # Add page data to JSON
        book_data["pages"].append({
            "page_number": i,
            "text": page_text,
            "image_file": image_filename
        })

    # Save JSON metadata
    json_path = os.path.join(folder_path, "book_data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(book_data, f, indent=2, ensure_ascii=False)

    return folder_path


def generate_childrens_book(prompt: str, progress=gr.Progress()):
    """
    Main function to generate the complete children's book.
    """
    if not prompt or not prompt.strip():
        return None, "Please enter a story prompt!"

    progress(0, desc="Generating story script...")

    # Step 1: Generate the story script
    pages = generate_story_script(prompt)

    if not pages or len(pages) == 0:
        return None, "Failed to generate story script. Please try again."

    # Step 2: Generate images for each page
    storyboard = []
    images = []
    reference_image = None  # Will store the first image for style consistency
    # Generate the first image serially to establish the reference style
    try:
        progress(0.05, desc=f"Generating image for page 1/10 (establishing style)...")
        first_image = generate_image(pages[0], 1, prompt, None)
    except Exception as e:
        print(f"Error generating first image: {e}")
        first_image = Image.new('RGB', (512, 512), color='lightgray')

    storyboard = [(first_image, pages[0])]
    images = [first_image]
    reference_image = first_image

    # Parallelize generation for the remaining pages (2..N)
    remaining_count = max(0, len(pages) - 1)
    if remaining_count > 0:
        # Tune max_workers as needed; keep it modest to avoid request throttling
        max_workers = min(4, remaining_count)

        # Prepare placeholders so we can place images into the correct order
        images += [None] * remaining_count
        storyboard += [(None, pages[i]) for i in range(1, len(pages))]

        # Map futures to page indexes (1-based page numbers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx in range(1, len(pages)):
                page_num = idx + 1
                page_text = pages[idx]
                # Submit generation task using the established reference image
                fut = executor.submit(generate_image, page_text, page_num, prompt, reference_image)
                futures[fut] = idx

            completed = 0
            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                page_num = idx + 1
                try:
                    img = fut.result()
                except Exception as e:
                    print(f"Error generating image for page {page_num}: {e}")
                    img = Image.new('RGB', (512, 512), color='lightgray')

                # Place image and storyboard in correct slot
                images[idx] = img
                storyboard[idx] = (img, pages[idx])

                completed += 1
                progress(0.05 + (completed / len(pages)) * 0.9, desc=f"Generating images... ({completed}/{remaining_count})")

    progress(1.0, desc="Saving book to folder...")

    # Step 3: Save the book to a timestamped folder
    try:
        folder_path = save_book_to_folder(prompt, pages, images)
        status_message = f"✅ Successfully generated a 10-page children's book!\n\nPrompt: {prompt}\n\n💾 Saved to: {folder_path}"
    except Exception as e:
        folder_path = None
        status_message = f"✅ Successfully generated a 10-page children's book!\n\nPrompt: {prompt}\n\n⚠️ Warning: Could not save to folder: {str(e)}"

    return storyboard, status_message


# Create the Gradio interface
with gr.Blocks(title="Children's Book Generator", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 📚 Children's Book Generator
    
    Generate a complete 10-page children's book with illustrations!
    """)

    with gr.Row():
        with gr.Column(scale=2):
            prompt_input = gr.Textbox(
                label="Story Prompt",
                placeholder="Example: A brave little mouse who goes on an adventure to find the moon cheese...",
                lines=3,
            )
            generate_btn = gr.Button(
                "🎨 Generate Book", variant="primary", size="lg")

        with gr.Column(scale=1):
            status_output = gr.Textbox(
                label="Status",
                lines=5,
                interactive=False
            )

    gr.Markdown("---")

    gallery_output = gr.Gallery(
        label="Your Children's Book Storyboard",
        show_label=True,
        columns=2,
        rows=5,
        height="auto",
        object_fit="contain"
    )

    # Connect the button to the function
    generate_btn.click(
        fn=generate_childrens_book,
        inputs=[prompt_input],
        outputs=[gallery_output, status_output]
    )

if __name__ == "__main__":
    demo.launch(share=False)
