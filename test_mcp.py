import asyncio
import base64
import logging
from typing import Sequence

from mcp.types import ImageContent, TextContent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def create_photo_content() -> Sequence[TextContent | ImageContent]:
    """Test function that creates a sample response with an image, simulating what our tools do"""
    try:
        # Create sample response
        response = []
        
        # Add text content
        response.append(TextContent(type="text", text="This is a test message with an image"))
        
        # Create test image data
        test_data = base64.b64encode(b"test image data").decode('utf-8')
        
        # Add image content
        response.append(
            ImageContent(
                type="image",
                data=test_data,
                mimeType="image/jpeg"
            )
        )
        
        # Log what we've created
        for item in response:
            logger.info("Created content: %s", item.model_dump())
        
        return response
    except Exception as e:
        logger.error("Error creating photo content: %s", e)
        raise

if __name__ == "__main__":
    try:
        content = asyncio.run(create_photo_content())
        print(f"Successfully created {len(content)} content items")
    except Exception as e:
        print(f"Test failed with error: {e}")
        exit(1) 