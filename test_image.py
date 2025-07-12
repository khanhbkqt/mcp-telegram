import asyncio
import base64
import logging

from mcp.types import ImageContent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_image_content():
    """Test function to verify ImageContent creation"""
    try:
        # Create test data
        test_data = base64.b64encode(b"test image data").decode('utf-8')
        
        # Create an image content object using the correct class
        image = ImageContent(type="image", data=test_data, mimeType="image/jpeg")
        
        # Verify that it works
        logger.info("Test ImageContent creation successful: %s", image.model_dump())
        
        return True
    except Exception as e:
        logger.error("Test ImageContent creation failed: %s", e)
        raise

if __name__ == "__main__":
    success = asyncio.run(test_image_content())
    if success:
        print("Test passed successfully!")
    else:
        print("Test failed!")
        exit(1) 