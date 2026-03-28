from __future__ import annotations

import io
import textwrap
from PIL import Image, ImageDraw, ImageFont
import uuid

class RenderService:
    @staticmethod
    def render_question_text(text: str) -> bytes:
        """
        Renders the question prompt into a PNG image to prevent text copying.
        """
        # Basic layout settings
        width = 800
        padding = 40
        font_size = 24
        bg_color = (255, 255, 255) # White
        text_color = (0, 0, 0) # Black
        
        # Wrap text
        # Assuming average char width for wrapping if font not loaded
        max_chars = 50 
        wrapper = textwrap.TextWrapper(width=max_chars)
        lines = wrapper.wrap(text=text)
        
        # Create image
        # Calculate height: padding + (lines * line_height) + padding
        line_height = font_size + 10
        total_height = padding * 2 + len(lines) * line_height
        
        img = Image.new('RGB', (width, total_height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Load a default font (System font or built-in)
        try:
            # Try to find a standard font on Linux
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except:
            font = ImageFont.load_default()
            
        # Draw text line by line
        current_y = padding
        for line in lines:
            draw.text((padding, current_y), line, fill=text_color, font=font)
            current_y += line_height
            
        # Add a subtle watermark or branding
        draw.text((width - 150, total_height - 20), "teleexam.ai", fill=(200, 200, 200), font=font)
        
        # Save to buffer
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
