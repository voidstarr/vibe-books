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

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


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
            model="google/gemini-2.5-flash-preview-09-2025",
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
            This is page {page_number} of the book.
            Page content: {page_text}
            
            IMPORTANT: Match the artistic style, character design, colors, and overall look of the reference image exactly.
            """
        else:
            image_prompt = f"""
            Children's book illustration style, colorful and friendly
            Scene from a story about {overall_prompt}.
            This is page {page_number} of the book.
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
            model="google/gemini-2.5-flash-image-preview",
            messages=messages,
            modalities=["image", "text"]
        )

        # Extract the image from the response
        message = response.choices[0].message

        if 'images' in message.model_extra and message.model_extra['images']:
            # Get the base64 data URL from the first image
            image_data_url = message.model_extra['images'][0]['image_url']['url']

            # Check if it's a base64 data URL
            if image_data_url.startswith('data:image'):
                # Extract the base64 data (remove the data:image/png;base64, prefix)
                base64_data = image_data_url.split(',', 1)[1]
                image_bytes = base64.b64decode(base64_data)
                img = Image.open(io.BytesIO(image_bytes))
                return img
            else:
                # If it's a URL, download it
                img_response = requests.get(image_data_url)
                img = Image.open(io.BytesIO(img_response.content))
                return img
        else:
            raise Exception("No images in response")

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

    for i, page_text in enumerate(pages):
        if i == 0:
            progress(
                (i + 1) / 10, desc=f"Generating image for page {i + 1}/10 (establishing style)...")
        else:
            progress(
                (i + 1) / 10, desc=f"Generating image for page {i + 1}/10 (matching style)...")

        # Pass reference_image to all generations after the first
        image = generate_image(page_text, i + 1, prompt, reference_image)
        storyboard.append((image, page_text))
        images.append(image)

        # Store the first image as the style reference
        if i == 0:
            reference_image = image

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
