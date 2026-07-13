"""
Custom CrewAI tools for Scriptorium.
"""

import re
import requests
import logging
from typing import Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class WikimediaImageSearchInput(BaseModel):
    """Input schema for WikimediaImageSearchTool."""
    search_query: str = Field(
        ...,
        description="The search query to find relevant images on Wikimedia Commons. "
                    "Use descriptive keywords in English for best results."
    )


class WikimediaImageSearchResult(BaseModel):
    """Result from a Wikimedia image search."""
    success: bool
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    description: Optional[str] = None
    attribution: Optional[str] = None
    error: Optional[str] = None


class WikimediaImageSearchTool(BaseTool):
    """
    A CrewAI tool to search for images on Wikimedia Commons.
    
    This tool queries the Wikimedia Commons API to find high-quality,
    freely-licensed images that can be used in educational materials.
    
    Returns the image URL and attribution information for proper crediting.
    """
    
    name: str = "wikimedia_image_search"
    description: str = (
        "Search for images on Wikimedia Commons. "
        "Use this tool to find relevant, freely-licensed images for educational content. "
        "Provide a descriptive search query in English. "
        "Returns the image URL and attribution information."
    )
    args_schema: Type[BaseModel] = WikimediaImageSearchInput
    
    # Wikimedia Commons API endpoint
    API_ENDPOINT: str = "https://commons.wikimedia.org/w/api.php"
    
    def _run(self, search_query: str) -> str:
        """
        Execute the image search on Wikimedia Commons.
        
        Args:
            search_query: Search terms to find relevant images
            
        Returns:
            Formatted string with image URL and attribution, or error message
        """
        result = self._search_wikimedia(search_query)
        
        if result.success and result.image_url:
            # Prefer thumbnail URL (800px) - much faster to download and good enough for PDF
            best_url = result.thumbnail_url or result.image_url
            output = f"""
✓ Image found on Wikimedia Commons

Title: {result.title}
Image URL: {best_url}

Attribution:
  Author: {result.author or 'Unknown'}
  License: {result.license or 'See Wikimedia Commons'}

Credit line: {result.attribution}
"""
            return output.strip()
        else:
            return f"✗ No suitable image found for '{search_query}'. {result.error or ''}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
        reraise=True
    )
    def _search_wikimedia(self, search_query: str) -> WikimediaImageSearchResult:
        """
        Query the Wikimedia Commons API for images.
        
        Args:
            search_query: Search terms
            
        Returns:
            WikimediaImageSearchResult with image details or error
        """
        try:
            # Sanitize search query - remove special characters that could cause API issues
            clean_query = re.sub(r'[<>{}|\\^\[\]`]', '', search_query).strip()
            if not clean_query:
                return WikimediaImageSearchResult(
                    success=False,
                    error="Empty search query after sanitization."
                )
            
            # Step 1: Search for files matching the query
            search_params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,  # File namespace
                "gsrsearch": clean_query,
                "gsrlimit": 20,  # Increased to top 20 results
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime",
                "iiurlwidth": 800,  # Request thumbnail at 800px width
            }
            
            response = requests.get(
                self.API_ENDPOINT,
                params=search_params,
                headers={"User-Agent": "Scriptorium/1.0"},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            
            # Check if we got any results
            if "query" not in data or "pages" not in data["query"]:
                return WikimediaImageSearchResult(
                    success=False,
                    error="No images found matching the search query."
                )
            
            pages = data["query"]["pages"]
            
            # Filter and find the best image
            best_image = self._find_best_image(pages)
            
            if not best_image:
                return WikimediaImageSearchResult(
                    success=False,
                    error="No suitable images found (filtered by quality/format)."
                )
            
            return best_image
            
        except requests.exceptions.Timeout:
            return WikimediaImageSearchResult(
                success=False,
                error="Request timed out. Wikimedia Commons may be slow."
            )
        except requests.exceptions.RequestException as e:
            return WikimediaImageSearchResult(
                success=False,
                error=f"API request failed: {str(e)}"
            )
        except Exception as e:
            return WikimediaImageSearchResult(
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
    
    def _find_best_image(self, pages: dict) -> Optional[WikimediaImageSearchResult]:
        """
        Find the best image from the search results.
        
        Prioritizes:
        - JPEG and PNG formats
        - Images with good resolution (width >= 400px)
        - Images with proper metadata/attribution
        
        Args:
            pages: Dictionary of page results from the API
            
        Returns:
            WikimediaImageSearchResult for the best image, or None
        """
        candidates = []
        
        for page_id, page_data in pages.items():
            if "imageinfo" not in page_data:
                continue
            
            imageinfo_list = page_data["imageinfo"]
            if not imageinfo_list or len(imageinfo_list) == 0:
                continue
                
            imageinfo = imageinfo_list[0]
            
            # Check MIME type - prefer JPEG and PNG
            mime = imageinfo.get("mime", "")
            if mime not in ["image/jpeg", "image/png", "image/webp"]:
                continue
            
            # Check minimum size (lowered to accept more results)
            width = imageinfo.get("width", 0)
            height = imageinfo.get("height", 0)
            if width < 200 or height < 100:
                continue
            
            # Extract metadata
            extmetadata = imageinfo.get("extmetadata", {})
            
            # Get author/artist
            author = None
            if "Artist" in extmetadata:
                author_html = extmetadata["Artist"].get("value", "")
                # Strip HTML tags for clean author name
                author = self._strip_html(author_html)
            
            # Get license
            license_info = None
            if "LicenseShortName" in extmetadata:
                license_info = extmetadata["LicenseShortName"].get("value", "")
            
            # Get description
            description = None
            if "ImageDescription" in extmetadata:
                desc_html = extmetadata["ImageDescription"].get("value", "")
                description = self._strip_html(desc_html)[:200]  # Limit length
            
            # Build attribution string
            title = page_data.get("title", "").replace("File:", "")
            attribution = self._build_attribution(title, author, license_info)
            
            candidates.append({
                "score": width * height,  # Simple quality score
                "result": WikimediaImageSearchResult(
                    success=True,
                    image_url=imageinfo.get("url"),
                    thumbnail_url=imageinfo.get("thumburl"),
                    title=title,
                    author=author,
                    license=license_info,
                    description=description,
                    attribution=attribution
                )
            })
        
        if not candidates:
            return None
        
        # Sort by quality score (resolution) and return the best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]["result"]
    
    def _strip_html(self, html_string: str) -> str:
        """Remove HTML tags from a string."""
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', html_string)
        # Decode common HTML entities
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&#39;", "'")
        clean = clean.replace("&nbsp;", " ")
        # Clean up whitespace
        clean = " ".join(clean.split())
        return clean.strip()
    
    def _build_attribution(
        self,
        title: str,
        author: Optional[str],
        license_info: Optional[str]
    ) -> str:
        """Build a proper attribution string for the image."""
        parts = []
        
        if title:
            parts.append(f'"{title}"')
        
        if author:
            parts.append(f"by {author}")
        
        parts.append("via Wikimedia Commons")
        
        if license_info:
            parts.append(f"({license_info})")
        
        return " ".join(parts)


# Convenience function to create an instance
def get_wikimedia_tool() -> WikimediaImageSearchTool:
    """Get an instance of the WikimediaImageSearchTool."""
    return WikimediaImageSearchTool()


# For testing purposes
if __name__ == "__main__":
    tool = WikimediaImageSearchTool()
    
    # Test searches
    test_queries = [
        "Norwegian parliament Storting",
        "recycling waste sorting",
        "photosynthesis plant",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Searching for: {query}")
        print('='*60)
        result = tool._run(query)
        print(result)
