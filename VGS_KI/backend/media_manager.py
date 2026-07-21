"""
Media Manager - Image processing service for FOV Teacher Assistant.

Handles downloading, validation, and optimization of images
before embedding them in PDF lesson plans.
"""

import os
import logging
import tempfile
import uuid
from typing import Optional
from pathlib import Path

import requests
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Robust image processor for downloading and optimizing images.
    
    All methods are fail-safe - they return None on any error
    rather than raising exceptions, allowing PDF generation to
    proceed without images if needed.
    """
    
    # Configuration
    DOWNLOAD_TIMEOUT = 20  # seconds - Wikimedia can be slow for large images
    MAX_WIDTH = 1200  # pixels (enough for A4 printing)
    JPEG_QUALITY = 75  # compression quality (1-100)
    USER_AGENT = "VGS-Larerassistent/1.0 (Educational tool; contact: github.com/marlervius/VGS_KI)"
    
    # Temporary directory for processed images
    TEMP_DIR = Path(tempfile.gettempdir()) / "fov_images"
    
    def __init__(self):
        """Initialize the image processor and ensure temp directory exists."""
        self._ensure_temp_dir()
    
    def _ensure_temp_dir(self) -> None:
        """Create the temporary directory if it doesn't exist."""
        try:
            self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create temp directory: {e}")
    
    def process_image(self, image_url: str) -> Optional[str]:
        """
        Download, validate, and optimize an image from a URL.
        
        Args:
            image_url: URL of the image to process
            
        Returns:
            Path to the optimized local JPG file, or None if processing failed
            
        Note:
            This method is fail-safe. Any error during processing
            will be logged and None will be returned.
        """
        if not image_url or not image_url.startswith('http'):
            logger.warning(f"Invalid image URL: {image_url}")
            return None
        
        try:
            # Step 1: Download the image
            image_data = self._download_image(image_url)
            if image_data is None:
                return None
            
            # Step 2: Validate and open the image
            image = self._validate_image(image_data)
            if image is None:
                return None
            
            # Step 3: Optimize the image
            output_path = self._optimize_image(image)
            return output_path
            
        except Exception as e:
            logger.error(f"Unexpected error processing image: {e}")
            return None
            
    def process_base64_image(self, base64_data: str) -> Optional[str]:
        """
        Validate and optimize an image from a base64 string.
        
        Args:
            base64_data: Base64 encoded image data (optionally with data URI scheme)
            
        Returns:
            Path to the optimized local JPG file, or None if processing failed
        """
        try:
            import base64
            
            # Strip data URI scheme if present
            if ',' in base64_data:
                base64_data = base64_data.split(',', 1)[1]
                
            image_bytes = base64.b64decode(base64_data)
            
            # Step 1: Validate and open the image
            image = self._validate_image(image_bytes)
            if image is None:
                return None
            
            # Step 2: Optimize the image
            output_path = self._optimize_image(image)
            return output_path
            
        except Exception as e:
            logger.error(f"Unexpected error processing base64 image: {e}")
            return None

    def process_image_from_path(self, local_path: str) -> Optional[str]:
        """Validate and optimize a local image for PDF embedding.

        AI-generated images are already stored on disk, so routing them
        through the URL downloader is both unnecessary and unsupported.  The
        source file remains owned by the caller and is not deleted here.
        """
        if not local_path or not os.path.isfile(local_path):
            logger.warning(f"Local image not found at path: {local_path}")
            return None

        try:
            with open(local_path, "rb") as image_file:
                image_data = image_file.read()
            if not image_data:
                logger.warning(f"Local image file is empty: {local_path}")
                return None

            image = self._validate_image(image_data)
            if image is None:
                return None
            output_path = self._optimize_image(image)
            if output_path:
                logger.info(f"Local image processed: {output_path}")
            return output_path
        except OSError as e:
            logger.warning(f"Could not read local image {local_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing local image: {e}")
            return None
    
    def _download_image(self, url: str) -> Optional[bytes]:
        """
        Download image bytes from a URL.
        
        Args:
            url: The image URL
            
        Returns:
            Raw image bytes, or None if download failed
        """
        try:
            logger.info(f"Downloading image from: {url[:80]}...")
            
            response = requests.get(
                url,
                timeout=self.DOWNLOAD_TIMEOUT,
                headers={"User-Agent": self.USER_AGENT},
                stream=True
            )
            
            if response.status_code != 200:
                logger.warning(
                    f"Image download failed with status {response.status_code}: {url}"
                )
                return None
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL did not return an image: {content_type}")
                return None
            
            # Read the image data (limit to 20MB to prevent memory issues)
            max_size = 20 * 1024 * 1024  # 20MB
            image_data = b''
            for chunk in response.iter_content(chunk_size=8192):
                image_data += chunk
                if len(image_data) > max_size:
                    logger.warning("Image too large (>20MB), skipping")
                    return None
            
            logger.info(f"Downloaded {len(image_data) / 1024:.1f} KB")
            return image_data
            
        except requests.exceptions.Timeout:
            logger.warning(f"Image download timed out after {self.DOWNLOAD_TIMEOUT}s: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Image download error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected download error: {e}")
            return None
    
    def _validate_image(self, image_data: bytes) -> Optional[Image.Image]:
        """
        Validate and open image data using PIL.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            PIL Image object, or None if validation failed
        """
        try:
            from io import BytesIO
            
            # Try to open the image
            image = Image.open(BytesIO(image_data))
            
            # Verify the image is valid by loading it
            image.verify()
            
            # Re-open after verify (verify() makes the image unusable)
            image = Image.open(BytesIO(image_data))
            
            # Check minimum dimensions - 200px minimum to allow thumbnails
            if image.width < 200 or image.height < 150:
                logger.warning(f"Image skipped: resolution too low ({image.width}x{image.height}, minimum 200x150)")
                return None
            
            logger.info(f"Validated image: {image.format} {image.width}x{image.height} {image.mode}")
            return image
            
        except Exception as e:
            logger.warning(f"Image validation failed: {e}")
            return None
    
    def _optimize_image(self, image: Image.Image) -> Optional[str]:
        """
        Optimize an image for PDF embedding.
        
        - Converts to RGB (handles transparency)
        - Resizes if too large
        - Compresses as JPEG
        
        Args:
            image: PIL Image object
            
        Returns:
            Path to the optimized JPG file, or None if optimization failed
        """
        try:
            # Step 1: Convert to RGB mode
            # This handles RGBA (transparent PNGs) by compositing onto white
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', image.size, (255, 255, 255))
                
                # Handle palette mode
                if image.mode == 'P':
                    image = image.convert('RGBA')
                
                # Composite the image onto the white background
                if image.mode in ('RGBA', 'LA'):
                    # Split the alpha channel
                    if image.mode == 'LA':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1])
                    image = background
                else:
                    image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Step 2: Resize if too large (maintain aspect ratio)
            if image.width > self.MAX_WIDTH:
                ratio = self.MAX_WIDTH / image.width
                new_height = int(image.height * ratio)
                image = image.resize(
                    (self.MAX_WIDTH, new_height),
                    Image.Resampling.LANCZOS
                )
                logger.info(f"Resized to {image.width}x{image.height}")
            
            # Step 3: Save as optimized JPEG
            # Generate unique filename
            filename = f"fov_img_{uuid.uuid4().hex[:12]}.jpg"
            output_path = self.TEMP_DIR / filename
            
            image.save(
                output_path,
                format='JPEG',
                quality=self.JPEG_QUALITY,
                optimize=True
            )
            
            # Get file size for logging
            file_size = output_path.stat().st_size / 1024
            logger.info(f"Saved optimized image: {output_path} ({file_size:.1f} KB)")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Image optimization failed: {e}")
            return None
    
    def cleanup_image(self, image_path: str) -> None:
        """
        Delete a processed image file.
        
        Args:
            image_path: Path to the image file to delete
        """
        try:
            if image_path and os.path.exists(image_path):
                os.unlink(image_path)
                logger.info(f"Cleaned up image: {image_path}")
        except Exception as e:
            logger.warning(f"Could not delete image {image_path}: {e}")
    
    def cleanup_all(self) -> None:
        """
        Delete all temporary images in the temp directory.
        
        Call this periodically or on application shutdown.
        """
        try:
            if self.TEMP_DIR.exists():
                for file in self.TEMP_DIR.glob("fov_img_*.jpg"):
                    try:
                        file.unlink()
                    except Exception:
                        pass
                logger.info("Cleaned up all temporary images")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


# Singleton instance for easy import
image_processor = ImageProcessor()


# Convenience function
def process_image(image_url: str) -> Optional[str]:
    """
    Process an image URL and return path to optimized local file.
    
    This is a convenience wrapper around ImageProcessor.process_image().
    
    Args:
        image_url: URL of the image to process
        
    Returns:
        Path to optimized JPG file, or None if processing failed
    """
    return image_processor.process_image(image_url)


# For testing purposes
if __name__ == "__main__":
    # Test with various image types
    test_urls = [
        # Standard JPEG
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Collage_of_Nine_Dogs.jpg/800px-Collage_of_Nine_Dogs.jpg",
        # PNG with transparency
        "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png",
        # Large image (should be resized)
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Image_created_with_a_mobile_phone.png/1920px-Image_created_with_a_mobile_phone.png",
        # Invalid URL (should fail gracefully)
        "https://example.com/nonexistent-image.jpg",
    ]
    
    processor = ImageProcessor()
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url[:60]}...")
        print('='*60)
        
        result = processor.process_image(url)
        
        if result:
            print(f"✓ Success: {result}")
            # Show file size
            size = os.path.getsize(result) / 1024
            print(f"  File size: {size:.1f} KB")
            # Cleanup
            processor.cleanup_image(result)
        else:
            print("✗ Failed (returned None)")
    
    print("\n" + "="*60)
    print("Testing complete!")
