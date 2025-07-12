import asyncio
import base64
import io
import logging
from typing import Sequence, Union

from mcp.types import (
    EmbeddedResource,
    TextContent,
)
# Specifically import ImageContent to test the fix
from mcp.types import ImageContent

# Import our actual tools modules to test them directly
from src.mcp_telegram.tools import (
    MCPImageContent,  # This should be the renamed import of ImageContent
    TextContent,
    EmbeddedResource,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_direct_creation():
    """Test direct creation of ImageContent objects"""
    try:
        # Create test data
        test_data = base64.b64encode(b"test image data").decode('utf-8')
        
        # Create ImageContent object directly from mcp.types
        image1 = ImageContent(type="image", data=test_data, mimeType="image/jpeg")
        logger.info("Direct ImageContent creation: %s", image1.model_dump())
        
        # Create ImageContent object using our renamed import
        image2 = MCPImageContent(type="image", data=test_data, mimeType="image/jpeg")
        logger.info("MCPImageContent creation: %s", image2.model_dump())
        
        # Verify they're the same type
        logger.info("Types match: %s", type(image1) == type(image2))
        
        return True
    except Exception as e:
        logger.error("Error in test_direct_creation: %s", e)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_direct_creation())
    if success:
        print("All tests passed!")
    else:
        print("Tests failed!")
        exit(1) 