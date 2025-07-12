from __future__ import annotations

import logging
import sys
import typing as t
import io
import base64
import asyncio
from functools import singledispatch

from mcp.types import (
    EmbeddedResource,
    TextContent,
    Tool,
)
# Import ImageContent directly to avoid namespace conflicts
from mcp.types import ImageContent as MCPImageContent

from pydantic import BaseModel, ConfigDict
from telethon import TelegramClient, custom, functions, types, events  # type: ignore[import-untyped]

from .telegram import create_client

logger = logging.getLogger(__name__)

# How to add a new tool:
#
# 1. Create a new class that inherits from ToolArgs
#    ```python
#    class NewTool(ToolArgs):
#        """Description of the new tool."""
#        pass
#    ```
#    Attributes of the class will be used as arguments for the tool.
#    The class docstring will be used as the tool description.
#
# 2. Implement the tool_runner function for the new class
#    ```python
#    @tool_runner.register
#    async def new_tool(args: NewTool) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
#        pass
#    ```
#    The function should return a sequence of TextContent, MCPImageContent or EmbeddedResource.
#    The function should be async and accept a single argument of the new class.
#
# 3. Done! Restart the client and the new tool should be available.


class ToolArgs(BaseModel):
    model_config = ConfigDict()


@singledispatch
async def tool_runner(
    args,  # noqa: ANN001
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    raise NotImplementedError(f"Unsupported type: {type(args)}")


def tool_description(args: type[ToolArgs]) -> Tool:
    return Tool(
        name=args.__name__,
        description=args.__doc__,
        inputSchema=args.model_json_schema(),
    )


def tool_args(tool: Tool, *args, **kwargs) -> ToolArgs:  # noqa: ANN002, ANN003
    return sys.modules[__name__].__dict__[tool.name](*args, **kwargs)


### ListDialogs ###


class ListDialogs(ToolArgs):
    """List available dialogs, chats and channels."""

    unread: bool = False
    archived: bool = False
    ignore_pinned: bool = False


@tool_runner.register
async def list_dialogs(
    args: ListDialogs,
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ListDialogs] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        dialog: custom.dialog.Dialog
        async for dialog in client.iter_dialogs(archived=args.archived, ignore_pinned=args.ignore_pinned):
            if args.unread and dialog.unread_count == 0:
                continue
            msg = (
                f"name='{dialog.name}' id={dialog.id} "
                f"unread={dialog.unread_count} mentions={dialog.unread_mentions_count}"
            )
            response.append(TextContent(type="text", text=msg))

    return response


### ListMessages ###


class ListMessages(ToolArgs):
    """
    List messages in a given dialog, chat or channel. The messages are listed in order from newest to oldest.

    If `unread` is set to `True`, only unread messages will be listed. Once a message is read, it will not be
    listed again.

    If `limit` is set, only the last `limit` messages will be listed. If `unread` is set, the limit will be
    the minimum between the unread messages and the limit.
    """

    dialog_id: int
    unread: bool = False
    limit: int = 100


@tool_runner.register
async def list_messages(
    args: ListMessages,
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ListMessages] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        result = await client(functions.messages.GetPeerDialogsRequest(peers=[args.dialog_id]))
        if not result:
            raise ValueError(f"Channel not found: {args.dialog_id}")

        if not isinstance(result, types.messages.PeerDialogs):
            raise TypeError(f"Unexpected result: {type(result)}")

        for dialog in result.dialogs:
            logger.debug("dialog: %s", dialog)
        for message in result.messages:
            logger.debug("message: %s", message)

        iter_messages_args: dict[str, t.Any] = {
            "entity": args.dialog_id,
            "reverse": False,
        }
        if args.unread:
            iter_messages_args["limit"] = min(dialog.unread_count, args.limit)
        else:
            iter_messages_args["limit"] = args.limit

        logger.debug("iter_messages_args: %s", iter_messages_args)
        async for message in client.iter_messages(**iter_messages_args):
            logger.debug("message: %s", type(message))
            if isinstance(message, custom.Message) and message.text:
                logger.debug("message: %s", message.text)
                response.append(TextContent(type="text", text=message.text))

    return response

### GetMessagesWithMedia ###

class GetMessagesWithMedia(ToolArgs):
    """
    Get messages with media (photos, videos, documents, etc.) from a given dialog, chat or channel.
    
    This tool retrieves messages containing media and returns both the text and the media content.
    For images and other supported media, the content is returned as base64-encoded data that can be displayed.
    
    If `limit` is set, only the last `limit` messages with media will be retrieved.
    """
    
    dialog_id: int
    limit: int = 20
    include_documents: bool = True
    include_videos: bool = True
    include_audio: bool = True

@tool_runner.register
async def get_messages_with_media(
    args: GetMessagesWithMedia,
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetMessagesWithMedia] args[%s]", args)
    
    response: list[TextContent | MCPImageContent | EmbeddedResource] = []
    async with create_client() as client:
        result = await client(functions.messages.GetPeerDialogsRequest(peers=[args.dialog_id]))
        if not result:
            raise ValueError(f"Channel not found: {args.dialog_id}")

        if not isinstance(result, types.messages.PeerDialogs):
            raise TypeError(f"Unexpected result: {type(result)}")
        
        # First check if the dialog exists
        for dialog in result.dialogs:
            logger.debug("dialog: %s", dialog)
            
        # Get messages with media
        iter_messages_args: dict[str, t.Any] = {
            "entity": args.dialog_id,
            "limit": args.limit,
            "reverse": False,
        }
        
        async for message in client.iter_messages(**iter_messages_args):
            logger.debug("message type: %s", type(message))
            
            # Create a list to store content for this message
            message_contents: list[TextContent | MCPImageContent | EmbeddedResource] = []
            
            # Add text if available
            if message.text:
                message_contents.append(TextContent(type="text", text=message.text))
            
            # Process media if available
            if message.media:
                # Photos
                if message.photo:
                    # Download the photo
                    photo_bytes = io.BytesIO()
                    await client.download_media(message.photo, file=photo_bytes)
                    photo_bytes.seek(0)
                    
                    # Encode as base64
                    base64_data = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')
                    mime_type = "image/jpeg"  # Most Telegram photos are JPEG
                    
                    # Create image content
                    message_contents.append(
                        MCPImageContent(
                            type="image",
                            data=base64_data,
                            mimeType=mime_type
                        )
                    )
                
                # Documents
                elif message.document and args.include_documents:
                    # Check if it's an image document
                    mime_type = message.document.mime_type if message.document.mime_type else "application/octet-stream"
                    
                    if mime_type.startswith("image/"):
                        # Handle image document
                        doc_bytes = io.BytesIO()
                        await client.download_media(message.document, file=doc_bytes)
                        doc_bytes.seek(0)
                        
                        # Encode as base64
                        base64_data = base64.b64encode(doc_bytes.getvalue()).decode('utf-8')
                        
                        # Create image content
                        message_contents.append(
                            MCPImageContent(
                                type="image",
                                data=base64_data,
                                mimeType=mime_type
                            )
                        )
                    else:
                        # Handle non-image document (provide metadata)
                        file_name = getattr(message.document, 'attributes', [{}])[0].file_name if hasattr(getattr(message.document, 'attributes', [{}])[0], 'file_name') else "document"
                        file_size = message.document.size if hasattr(message.document, 'size') else "unknown size"
                        
                        message_contents.append(
                            TextContent(
                                type="text", 
                                text=f"Document: {file_name}, Type: {mime_type}, Size: {file_size} bytes"
                            )
                        )
                        
                        # For small files, we can also include the content as embedded resource
                        if hasattr(message.document, 'size') and message.document.size < 1024 * 1024:  # Less than 1MB
                            try:
                                doc_bytes = io.BytesIO()
                                await client.download_media(message.document, file=doc_bytes)
                                doc_bytes.seek(0)
                                
                                # Encode as base64
                                base64_data = base64.b64encode(doc_bytes.getvalue()).decode('utf-8')
                                
                                message_contents.append(
                                    EmbeddedResource(
                                        type="embedded_resource",
                                        name=file_name,
                                        data=f"data:{mime_type};base64,{base64_data}"
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Error downloading document: {e}")
                
                # Videos
                elif message.video and args.include_videos:
                    # For videos, we'll just provide metadata
                    duration = message.video.duration if hasattr(message.video, 'duration') else "unknown duration"
                    width = message.video.w if hasattr(message.video, 'w') else "unknown width"
                    height = message.video.h if hasattr(message.video, 'h') else "unknown height"
                    
                    message_contents.append(
                        TextContent(
                            type="text", 
                            text=f"Video: Duration: {duration}s, Resolution: {width}x{height}"
                        )
                    )
                    
                    # Try to get a thumbnail for the video
                    try:
                        if hasattr(message.video, 'thumbs') and message.video.thumbs:
                            thumb_bytes = io.BytesIO()
                            await client.download_media(message.video, thumb=-1, file=thumb_bytes)
                            thumb_bytes.seek(0)
                            
                            # Encode as base64
                            base64_data = base64.b64encode(thumb_bytes.getvalue()).decode('utf-8')
                            
                            # Create image content for thumbnail
                            message_contents.append(
                                MCPImageContent(
                                    type="image",
                                    data=base64_data,
                                    mimeType="image/jpeg"
                                )
                            )
                    except Exception as e:
                        logger.error(f"Error downloading video thumbnail: {e}")
                
                # Audio
                elif (message.audio or getattr(message, 'voice', None)) and args.include_audio:
                    media_obj = message.audio if message.audio else message.voice
                    
                    # Get audio metadata
                    duration = media_obj.duration if hasattr(media_obj, 'duration') else "unknown duration"
                    title = getattr(media_obj, 'title', None) if hasattr(media_obj, 'title') else None
                    performer = getattr(media_obj, 'performer', None) if hasattr(media_obj, 'performer') else None
                    
                    audio_info = f"Audio: Duration: {duration}s"
                    if title:
                        audio_info += f", Title: {title}"
                    if performer:
                        audio_info += f", Artist: {performer}"
                        
                    message_contents.append(
                        TextContent(
                            type="text", 
                            text=audio_info
                        )
                    )
            
            # Add all contents for this message to the response
            response.extend(message_contents)
    
    return response

### RequestUserMedia ###

class RequestUserMedia(ToolArgs):
    """
    Send a message to a chat requesting the user to send media (photos, videos, documents, etc.), and wait for the response.
    
    This tool sends a message with your specified prompt to the given dialog_id and waits
    for the user to respond with one or more media files. The tool returns both the text and 
    the media content that the user sends in response.
    
    Parameters:
    - dialog_id: The ID of the dialog to send the request to
    - message: The message to send to the user requesting media
    - accept_photos: Whether to accept photo media (default: True)
    - accept_documents: Whether to accept document media (default: True)
    - accept_videos: Whether to accept video media (default: True)
    - accept_audio: Whether to accept audio media (default: True)
    - timeout: Maximum seconds to wait for a response (default: 60)
    - max_media: Maximum number of media items to collect (default: 5)
    """
    
    dialog_id: int
    message: str
    accept_photos: bool = True
    accept_documents: bool = True
    accept_videos: bool = True
    accept_audio: bool = True
    timeout: int = 60
    max_media: int = 5

@tool_runner.register
async def request_user_media(
    args: RequestUserMedia,
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[RequestUserMedia] args[%s]", args)
    
    response: list[TextContent | MCPImageContent | EmbeddedResource] = []
    async with create_client() as client:
        # Send the request message
        await client.send_message(args.dialog_id, args.message)
        response.append(TextContent(type="text", text=f"Sent request: {args.message}"))
        
        # Define a collector for media
        media_received = 0
        start_time = asyncio.get_event_loop().time()
        
        # Add a handler to collect media
        @client.on(events.NewMessage(chats=args.dialog_id))
        async def handler(event):
            nonlocal media_received
            
            # Check if the event happened after we sent our request
            if event.date.timestamp() < start_time:
                return
                
            # Add the message text if available
            if event.message.text:
                response.append(TextContent(type="text", text=f"User response: {event.message.text}"))
            
            # Check if message has media
            has_media = False
            if event.message.media:
                # Photos
                if event.message.photo and args.accept_photos:
                    has_media = True
                    # Download the photo
                    photo_bytes = io.BytesIO()
                    await client.download_media(event.message.photo, file=photo_bytes)
                    photo_bytes.seek(0)
                    
                    # Encode as base64
                    base64_data = base64.b64encode(photo_bytes.getvalue()).decode('utf-8')
                    mime_type = "image/jpeg"  # Most Telegram photos are JPEG
                    
                    # Create image content
                    response.append(
                        MCPImageContent(
                            type="image",
                            data=base64_data,
                            mimeType=mime_type
                        )
                    )
                    media_received += 1
                
                # Documents
                elif event.message.document and args.accept_documents:
                    has_media = True
                    # Check if it's an image document
                    mime_type = event.message.document.mime_type if event.message.document.mime_type else "application/octet-stream"
                    
                    if mime_type.startswith("image/"):
                        # Handle image document
                        doc_bytes = io.BytesIO()
                        await client.download_media(event.message.document, file=doc_bytes)
                        doc_bytes.seek(0)
                        
                        # Encode as base64
                        base64_data = base64.b64encode(doc_bytes.getvalue()).decode('utf-8')
                        
                        # Create image content
                        response.append(
                            MCPImageContent(
                                type="image",
                                data=base64_data,
                                mimeType=mime_type
                            )
                        )
                    else:
                        # Handle non-image document (provide metadata)
                        file_name = getattr(event.message.document, 'attributes', [{}])[0].file_name if hasattr(getattr(event.message.document, 'attributes', [{}])[0], 'file_name') else "document"
                        file_size = event.message.document.size if hasattr(event.message.document, 'size') else "unknown size"
                        
                        response.append(
                            TextContent(
                                type="text", 
                                text=f"User sent document: {file_name}, Type: {mime_type}, Size: {file_size} bytes"
                            )
                        )
                        
                        # For small files, we can also include the content as embedded resource
                        if hasattr(event.message.document, 'size') and event.message.document.size < 1024 * 1024:  # Less than 1MB
                            try:
                                doc_bytes = io.BytesIO()
                                await client.download_media(event.message.document, file=doc_bytes)
                                doc_bytes.seek(0)
                                
                                # Encode as base64
                                base64_data = base64.b64encode(doc_bytes.getvalue()).decode('utf-8')
                                
                                response.append(
                                    EmbeddedResource(
                                        type="embedded_resource",
                                        name=file_name,
                                        data=f"data:{mime_type};base64,{base64_data}"
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Error downloading document: {e}")
                
                # Videos
                elif event.message.video and args.accept_videos:
                    has_media = True
                    # For videos, we'll just provide metadata
                    duration = event.message.video.duration if hasattr(event.message.video, 'duration') else "unknown duration"
                    width = event.message.video.w if hasattr(event.message.video, 'w') else "unknown width"
                    height = event.message.video.h if hasattr(event.message.video, 'h') else "unknown height"
                    
                    response.append(
                        TextContent(
                            type="text", 
                            text=f"User sent video: Duration: {duration}s, Resolution: {width}x{height}"
                        )
                    )
                    
                    # Try to get a thumbnail for the video
                    try:
                        if hasattr(event.message.video, 'thumbs') and event.message.video.thumbs:
                            thumb_bytes = io.BytesIO()
                            await client.download_media(event.message.video, thumb=-1, file=thumb_bytes)
                            thumb_bytes.seek(0)
                            
                            # Encode as base64
                            base64_data = base64.b64encode(thumb_bytes.getvalue()).decode('utf-8')
                            
                            # Create image content for thumbnail
                            response.append(
                                MCPImageContent(
                                    type="image",
                                    data=base64_data,
                                    mimeType="image/jpeg"
                                )
                            )
                    except Exception as e:
                        logger.error(f"Error downloading video thumbnail: {e}")
                    media_received += 1
                
                # Audio
                elif (event.message.audio or getattr(event.message, 'voice', None)) and args.accept_audio:
                    has_media = True
                    media_obj = event.message.audio if event.message.audio else event.message.voice
                    
                    # Get audio metadata
                    duration = media_obj.duration if hasattr(media_obj, 'duration') else "unknown duration"
                    title = getattr(media_obj, 'title', None) if hasattr(media_obj, 'title') else None
                    performer = getattr(media_obj, 'performer', None) if hasattr(media_obj, 'performer') else None
                    
                    audio_info = f"User sent audio: Duration: {duration}s"
                    if title:
                        audio_info += f", Title: {title}"
                    if performer:
                        audio_info += f", Artist: {performer}"
                        
                    response.append(
                        TextContent(
                            type="text", 
                            text=audio_info
                        )
                    )
                    media_received += 1
            
            if has_media and media_received >= args.max_media:
                raise asyncio.CancelledError("Received maximum number of media items")
        
        try:
            # Wait for the timeout or until we receive max_media
            await asyncio.sleep(args.timeout)
            if media_received == 0:
                response.append(TextContent(type="text", text="Timeout reached without receiving any media"))
            else:
                response.append(TextContent(type="text", text=f"Timeout reached after receiving {media_received} media items"))
        except asyncio.CancelledError as e:
            if str(e) == "Received maximum number of media items":
                response.append(TextContent(type="text", text=f"Received maximum of {media_received} media items"))
            else:
                raise
        finally:
            # Clean up by removing the event handler
            client.remove_event_handler(handler)
            
    return response


# Keep the RequestUserPhotos for backward compatibility
class RequestUserPhotos(ToolArgs):
    """
    Send a message to a chat requesting the user to send photos, and wait for the response.
    
    This tool sends a message with your specified prompt to the given dialog_id and waits
    for the user to respond with one or more photos. The tool returns both the text and 
    the images that the user sends in response.
    
    Parameters:
    - dialog_id: The ID of the dialog to send the request to
    - message: The message to send to the user requesting photos
    - timeout: Maximum seconds to wait for a response (default: 60)
    - max_photos: Maximum number of photos to collect (default: 5)
    """
    
    dialog_id: int
    message: str
    timeout: int = 60
    max_photos: int = 5

@tool_runner.register
async def request_user_photos(
    args: RequestUserPhotos,
) -> t.Sequence[TextContent | MCPImageContent | EmbeddedResource]:
    # Convert to RequestUserMedia and call that
    media_args = RequestUserMedia(
        dialog_id=args.dialog_id,
        message=args.message,
        accept_photos=True,
        accept_documents=False,
        accept_videos=False,
        accept_audio=False,
        timeout=args.timeout,
        max_media=args.max_photos
    )
    return await request_user_media(media_args)


# Test function for debugging purposes
async def test_image_content() -> None:
    """Test function to verify ImageContent creation"""
    try:
        # Create test data
        test_data = base64.b64encode(b"test image data").decode('utf-8')
        
        # Create an image content object using the correct class
        image = MCPImageContent(type="image", data=test_data, mimeType="image/jpeg")
        
        # Verify that it works
        logger.info("Test ImageContent creation successful: %s", image.model_dump())
        
        # This is how we should create ImageContent objects:
        correct_way = """
        message_contents.append(
            MCPImageContent(
                type="image",
                data=base64_data,
                mimeType=mime_type
            )
        )
        """
        logger.info("Correct way to create ImageContent: %s", correct_way)
        
    except Exception as e:
        logger.error("Test ImageContent creation failed: %s", e)
        raise
