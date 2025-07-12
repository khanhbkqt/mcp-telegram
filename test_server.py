import asyncio
import base64
import logging
import typing as t
from typing import Sequence

from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
)

# These are the types of objects that can be returned from a tool
ContentTypes = t.Union[TextContent, ImageContent, EmbeddedResource]

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def simulate_call_tool() -> Sequence[ContentTypes]:
    """Simulate the call_tool function from the server"""
    try:
        # Create a sample response with text and image content
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
        logger.error("Error in simulate_call_tool: %s", e)
        raise
        
async def main():
    """Main function that simulates the MCP server flow"""
    try:
        result = await simulate_call_tool()
        logger.info("Successfully returned %d content items", len(result))
        
        # Verify that the ImageContent object is valid
        for item in result:
            if isinstance(item, ImageContent):
                logger.info("ImageContent validation:")
                logger.info("  type: %s", item.type)
                logger.info("  mimeType: %s", item.mimeType)
                logger.info("  data length: %d", len(item.data) if hasattr(item, 'data') else 0)
                
        return True
    except Exception as e:
        logger.error("Error in main: %s", e)
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    if success:
        print("Test completed successfully!")
    else:
        print("Test failed!")
        exit(1) 