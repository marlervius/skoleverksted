"""
Custom CrewAI tools for the FOV Teacher Assistant.
"""

import logging
import requests
from typing import Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

logger = logging.getLogger(__name__)


class WikimediaImageSearchInput(BaseModel):
    """Input schema for WikimediaImageSearchTool."""
    search_query: str = Field(
        ...,
        description="The search query to find relevant images on Wikimedia Commons. "
                    "Use descriptive keywords in English. For educational content, "
                    "ALWAYS include one of these qualifiers: 'diagram', 'illustration', "
                    "'educational', 'scientific', 'map', 'chart', or 'photo'. "
                    "Example: 'Earth axis tilt diagram' or 'Industrial Revolution illustration'."
    )
    subject: str = Field(
        default="",
        description="The school subject context (e.g., 'Samfunnsfag', 'Naturfag', 'Historie'). "
                    "This helps filter out irrelevant images from other fields."
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
    
    def _run(self, search_query: str, subject: str = "") -> str:
        """
        Execute the image search on Wikimedia Commons.
        
        Args:
            search_query: Search terms to find relevant images
            subject: School subject context for better filtering
            
        Returns:
            Formatted string with image URL and attribution, or error message
        """
        # Try the search, and if no results, retry with simpler query
        result = self._search_wikimedia(search_query, subject)
        
        # If first search fails, retry with simpler query (just the topic)
        if not result.success or not result.image_url:
            simple_query = search_query.split('(')[0].strip()  # Remove parenthetical qualifiers
            if simple_query != search_query:
                logger.debug("First search failed, retrying with simpler query: %s", simple_query)
                result = self._search_wikimedia(simple_query, subject)
        
        # If still no result, try a very basic search without subject filtering
        if not result.success or not result.image_url:
            basic_query = ' '.join(w for w in search_query.split() if len(w) > 2)[:60]
            logger.debug("Retrying with basic query (no subject filter): %s", basic_query)
            result = self._search_wikimedia(basic_query, "")
        
        if result.success and result.image_url:
            # Prefer thumbnail URL for faster download (already 800px wide - good enough for PDF)
            best_url = result.thumbnail_url or result.image_url
            
            output = f"""
✓ Image found on Wikimedia Commons

Title: {result.title}
Image URL: {best_url}
Thumbnail: {result.thumbnail_url}
Description: {result.description or 'No description'}

Attribution:
  Author: {result.author or 'Unknown'}
  License: {result.license or 'See Wikimedia Commons'}

Credit line: {result.attribution}

USE THIS URL in your IMAGE_URL line: {best_url}
"""
            return output.strip()
        else:
            return f"✗ No suitable image found for '{search_query}'. {result.error or ''} Try different keywords."
    
    def _search_wikimedia(self, search_query: str, subject: str = "") -> WikimediaImageSearchResult:
        """
        Query the Wikimedia Commons API for images.
        
        Args:
            search_query: Search terms
            subject: School subject for context-aware filtering
            
        Returns:
            WikimediaImageSearchResult with image details or error
        """
        try:
            # Build negative keywords based on subject to filter out irrelevant images
            negative_keywords = self._get_negative_keywords(subject)
            
            # Keep the query simple - over-engineering causes zero results
            enhanced_query = search_query
            
            # Only add minimal context if the query is very short
            if len(search_query.split()) <= 2:
                subject_context = self._get_subject_context(subject)
                if subject_context:
                    enhanced_query = f"{search_query} {subject_context}"
            
            # Apply negative keywords at the API level so junk (logos, coins,
            # off-subject medical/anatomy images, etc.) is filtered before scoring.
            if negative_keywords:
                enhanced_query = f"{enhanced_query} {negative_keywords}"
            
            logger.debug("Search query: %s", enhanced_query)
            
            # Step 1: Search for files matching the query
            search_params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,  # File namespace
                "gsrsearch": enhanced_query,
                "gsrlimit": 30,  # Increased to get more candidates for filtering
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime",
                "iiurlwidth": 800,  # Request thumbnail at 800px width
            }
            
            response = requests.get(
                self.API_ENDPOINT,
                params=search_params,
                headers={"User-Agent": "FOV-Teacher-Assistant/1.0"},
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
            
            # Filter and find the best image, passing original query and subject for relevance check
            best_image = self._find_best_image(pages, search_query, subject)
            
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
    
    def _get_negative_keywords(self, subject: str) -> str:
        """
        Get negative keywords to exclude irrelevant images based on subject.
        
        Args:
            subject: School subject name
            
        Returns:
            String of negative keywords for Wikimedia search
        """
        subject_lower = subject.lower() if subject else ""
        
        # Default negative keywords for all subjects
        base_negatives = "-logo -icon -badge -stamp -coin -selfie -avatar -screenshot"
        
        # Subject-specific negative keywords
        if subject_lower in ['samfunnsfag', 'geografi', 'historie']:
            # For social sciences - exclude medical/anatomical images
            return f"{base_negatives} -anatomy -medical -surgical -cell -microscope -histology -pathology -clinical"
        elif subject_lower == 'naturfag':
            # For natural sciences - exclude purely historical/political images
            return f"{base_negatives} -political -election -parliament"
        elif subject_lower in ['norsk', 'engelsk']:
            # For language subjects - exclude technical diagrams
            return f"{base_negatives} -circuit -chemical -molecular -formula"
        elif subject_lower == 'matematikk':
            # For math - exclude purely artistic images
            return f"{base_negatives} -painting -portrait -landscape"
        else:
            return base_negatives
    
    def _get_subject_context(self, subject: str) -> str:
        """
        Get subject-specific context keywords to improve search relevance.
        
        Args:
            subject: School subject name
            
        Returns:
            String of context keywords
        """
        subject_lower = subject.lower() if subject else ""
        
        if subject_lower in ['samfunnsfag', 'geografi']:
            return "human geography society culture"
        elif subject_lower == 'historie':
            return "historical archive"
        elif subject_lower == 'naturfag':
            return "science biology physics chemistry"
        elif subject_lower == 'matematikk':
            return "mathematics geometry"
        elif subject_lower == 'norsk':
            return "norway norwegian literature"
        elif subject_lower == 'engelsk':
            return "english literature culture"
        elif subject_lower == 'religion':
            return "religion ethics philosophy"
        elif subject_lower == 'kroppsøving':
            return "sport exercise physical activity"
        else:
            return "educational"
    
    def _has_excessive_text_labels(self, title: str, description: str, categories: str) -> bool:
        """
        Check if an image likely has excessive text labels (often in wrong language).
        
        Args:
            title: Image title
            description: Image description
            categories: Image categories
            
        Returns:
            True if image likely has too many text labels
        """
        combined = f"{title} {description} {categories}".lower()
        
        # Indicators of heavily labeled diagrams (often medical/technical)
        label_indicators = [
            'labeled', 'labelled', 'annotated', 'with labels', 'mit beschriftung',
            'avec légendes', 'numbered parts', 'anatomy labeled', 'parts labeled'
        ]
        
        # Check for medical terminology that suggests labeled anatomical diagrams
        medical_terms = [
            'artery', 'vein', 'nerve', 'muscle', 'bone', 'organ', 'tissue',
            'anterior', 'posterior', 'lateral', 'medial', 'proximal', 'distal',
            'dorsal', 'ventral', 'cranial', 'caudal'
        ]
        
        # Count medical terms - if many, probably a labeled medical diagram
        medical_count = sum(1 for term in medical_terms if term in combined)
        
        if any(ind in combined for ind in label_indicators):
            return True
        
        if medical_count >= 3:
            return True
        
        return False
    
    def _find_best_image(self, pages: dict, original_query: str = "", subject: str = "") -> Optional[WikimediaImageSearchResult]:
        """
        Find the best image from the search results.
        
        Prioritizes:
        - Relevance to educational content (diagram, illustration, etc.)
        - JPEG and PNG formats
        - Images with good resolution (width >= 400px)
        - Images with proper metadata/attribution
        - Images WITHOUT excessive text labels
        
        Args:
            pages: Dictionary of page results from the API
            original_query: The original search query for relevance checking
            subject: School subject for context-aware filtering
            
        Returns:
            WikimediaImageSearchResult for the best image, or None
        """
        candidates = []
        
        # Words that indicate irrelevant images (clocks, logos, portraits of unrelated people)
        irrelevant_indicators = [
            'clock', 'watch', 'logo', 'icon', 'badge', 'stamp', 'coin', 
            'flag', 'coat of arms', 'selfie', 'avatar', 'screenshot'
        ]
        
        # Additional irrelevant indicators for social sciences
        subject_lower = subject.lower() if subject else ""
        if subject_lower in ['samfunnsfag', 'geografi', 'historie']:
            irrelevant_indicators.extend([
                'anatomy', 'anatomical', 'medical', 'surgical', 'clinical',
                'histology', 'pathology', 'dissection', 'cadaver', 'specimen',
                'cell diagram', 'microscopy', 'x-ray', 'ct scan', 'mri'
            ])
        
        # Words that indicate educational/relevant images
        relevance_indicators = [
            'diagram', 'illustration', 'chart', 'map', 'scheme', 'model',
            'drawing', 'educational', 'scientific', 'photo', 'painting',
            'engraving', 'lithograph', 'historical'
        ]
        
        for page_id, page_data in pages.items():
            if "imageinfo" not in page_data:
                continue
                
            imageinfo = page_data["imageinfo"][0]
            
            # Check MIME type - prefer JPEG and PNG
            mime = imageinfo.get("mime", "")
            if mime not in ["image/jpeg", "image/png", "image/webp"]:
                continue
            
            # Check minimum size - be lenient to allow more results
            width = imageinfo.get("width", 0)
            height = imageinfo.get("height", 0)
            if width < 200 or height < 150:
                continue
            
            # Extract metadata
            extmetadata = imageinfo.get("extmetadata", {})
            title = page_data.get("title", "").replace("File:", "")
            title_lower = title.lower()
            
            # Get description for relevance check
            description = None
            if "ImageDescription" in extmetadata:
                desc_html = extmetadata["ImageDescription"].get("value", "")
                description = self._strip_html(desc_html)[:300]
            
            # Get categories for relevance check
            categories = ""
            if "Categories" in extmetadata:
                categories = extmetadata["Categories"].get("value", "").lower()
            
            combined_metadata = f"{title_lower} {description or ''} {categories}".lower()
            
            # Filter out irrelevant images
            is_irrelevant = any(ind in combined_metadata for ind in irrelevant_indicators)
            if is_irrelevant:
                continue
            
            # Filter out images with excessive text labels (often in wrong language)
            if self._has_excessive_text_labels(title, description or "", categories):
                logger.debug("Skipping image with excessive labels: %s", title)
                continue
            
            # Calculate relevance score
            relevance_score = 0
            
            # Boost for educational indicators in title/description
            for indicator in relevance_indicators:
                if indicator in combined_metadata:
                    relevance_score += 100
            
            # Boost for matching original query terms
            if original_query:
                query_words = original_query.lower().split()
                for word in query_words:
                    if len(word) > 3 and word in combined_metadata:
                        relevance_score += 50
            
            # Get author/artist
            author = None
            if "Artist" in extmetadata:
                author_html = extmetadata["Artist"].get("value", "")
                author = self._strip_html(author_html)
            
            # Get license
            license_info = None
            if "LicenseShortName" in extmetadata:
                license_info = extmetadata["LicenseShortName"].get("value", "")
            
            # Build attribution string
            attribution = self._build_attribution(title, author, license_info)
            
            # Combined score: relevance + quality (resolution)
            quality_score = (width * height) / 10000  # Normalize
            total_score = relevance_score + quality_score
            
            candidates.append({
                "score": total_score,
                "relevance": relevance_score,
                "result": WikimediaImageSearchResult(
                    success=True,
                    image_url=imageinfo.get("url"),
                    thumbnail_url=imageinfo.get("thumburl"),
                    title=title,
                    author=author,
                    license=license_info,
                    description=description[:200] if description else None,
                    attribution=attribution
                )
            })
        
        if not candidates:
            return None

        # Sort by total score (relevance + quality) and return the best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]["result"]

    def find_top_images(self, pages: dict, original_query: str = "", subject: str = "", limit: int = 5) -> list:
        """Like _find_best_image but returns the top `limit` candidates."""
        candidates = []
        irrelevant_indicators = [
            'clock', 'watch', 'logo', 'icon', 'badge', 'stamp', 'coin',
            'flag', 'coat of arms', 'selfie', 'avatar', 'screenshot'
        ]
        subject_lower = subject.lower() if subject else ""
        if subject_lower in ['samfunnsfag', 'geografi', 'historie']:
            irrelevant_indicators.extend([
                'anatomy', 'anatomical', 'medical', 'surgical', 'clinical',
                'histology', 'pathology', 'dissection', 'cadaver', 'specimen',
            ])
        relevance_indicators = [
            'diagram', 'illustration', 'chart', 'map', 'scheme', 'model',
            'drawing', 'educational', 'scientific', 'photo', 'painting',
            'engraving', 'lithograph', 'historical'
        ]
        for page_id, page_data in pages.items():
            if "imageinfo" not in page_data:
                continue
            imageinfo = page_data["imageinfo"][0]
            mime = imageinfo.get("mime", "")
            if mime not in ["image/jpeg", "image/png", "image/webp"]:
                continue
            width = imageinfo.get("width", 0)
            height = imageinfo.get("height", 0)
            if width < 200 or height < 150:
                continue
            extmetadata = imageinfo.get("extmetadata", {})
            title = page_data.get("title", "").replace("File:", "")
            title_lower = title.lower()
            description = None
            if "ImageDescription" in extmetadata:
                description = self._strip_html(extmetadata["ImageDescription"].get("value", ""))[:300]
            categories = extmetadata.get("Categories", {}).get("value", "").lower()
            combined = f"{title_lower} {description or ''} {categories}"
            if any(ind in combined for ind in irrelevant_indicators):
                continue
            if self._has_excessive_text_labels(title, description or "", categories):
                continue
            relevance_score = sum(100 for ind in relevance_indicators if ind in combined)
            if original_query:
                for word in original_query.lower().split():
                    if len(word) > 3 and word in combined:
                        relevance_score += 50
            author = self._strip_html(extmetadata.get("Artist", {}).get("value", "")) or None
            license_info = extmetadata.get("LicenseShortName", {}).get("value") or None
            candidates.append({
                "score": relevance_score + (width * height) / 10000,
                "result": WikimediaImageSearchResult(
                    success=True,
                    image_url=imageinfo.get("url"),
                    thumbnail_url=imageinfo.get("thumburl"),
                    title=title,
                    author=author,
                    license=license_info,
                    description=description[:200] if description else None,
                    attribution=self._build_attribution(title, author, license_info),
                )
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return [c["result"] for c in candidates[:limit]]

    def search_candidates(self, search_query: str, subject: str = "", limit: int = 5) -> list:
        """Search Wikimedia and return the top `limit` image candidates."""
        try:
            params = {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrsearch": search_query,
                "gsrlimit": 50,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime",
                "iiurlwidth": 800,
            }
            response = requests.get(
                self.API_ENDPOINT,
                params=params,
                headers={"User-Agent": "VGS-Teacher-Assistant/1.0"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            return self.find_top_images(pages, search_query, subject, limit)
        except Exception as e:
            return []
    
    def _strip_html(self, html_string: str) -> str:
        """Remove HTML tags from a string."""
        import re
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
