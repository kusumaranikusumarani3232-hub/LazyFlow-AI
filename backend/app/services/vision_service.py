import io
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List
from PIL import Image

from app.config import settings

logger = logging.getLogger("lazyflow.vision")

# Clean concept taxonomy mapping ImageNet labels to friendly user categories & filenames
IMAGENET_CONCEPT_MAP: List[Tuple[Tuple[str, ...], str, str, str]] = [
    # (Keywords in ImageNet label, Clean Concept Name, High-level Category, Destination Folder)
    # Clothing / Apparel
    (("jersey", "t-shirt", "tee shirt"), "T-Shirt", "Clothing", "Images"),
    (("sweatshirt", "hoodie"), "Sweatshirt", "Clothing", "Images"),
    (("suit", "tuxedo"), "Suit", "Clothing", "Images"),
    (("jean", "blue jean", "denim"), "Jeans", "Clothing", "Images"),
    (("cardigan", "sweater", "wool"), "Cardigan", "Clothing", "Images"),
    (("trench coat", "fur coat", "coat", "overcoat"), "Coat", "Clothing", "Images"),
    (("dress", "gown", "kimono", "sarong"), "Dress", "Clothing", "Images"),
    (("running shoe", "sneaker", "sandal", "clog", "boot", "loafer", "shoe"), "Shoes", "Clothing", "Images"),
    (("backpack", "knapsack", "rucksack"), "Backpack", "Accessories", "Images"),
    (("umbrella",), "Umbrella", "Accessories", "Images"),
    (("tie", "bow tie"), "Necktie", "Clothing", "Images"),
    (("swimming trunks", "bathing cap", "bikini", "maillot"), "Swimwear", "Clothing", "Images"),

    # Animals
    (("golden retriever", "labrador", "terrier", "poodle", "pug", "beagle", "collie", "chihuahua", "dog", "hound", "shepherd"), "Dog", "Animals", "Images"),
    (("tabby", "persian cat", "siamese cat", "egyptian cat", "tiger cat", "cougar", "lynx", "leopard", "jaguar", "lion", "cheetah", "tiger", "cat"), "Cat", "Animals", "Images"),
    (("robin", "sparrow", "eagle", "owl", "penguin", "hummingbird", "parrot", "peacock", "flamingo", "swan", "bird"), "Bird", "Animals", "Images"),
    (("horse", "zebra", "elephant", "bear", "panda", "monkey", "rabbit", "deer", "camel", "fox"), "Wildlife", "Animals", "Images"),
    (("goldfish", "clown fish", "shark", "whale", "dolphin", "fish"), "Marine-Life", "Animals", "Images"),

    # Nature / Landscapes
    (("alp", "volcano", "mountain"), "Mountain", "Nature", "Images"),
    (("valley", "cliff", "promontory"), "Valley", "Nature", "Images"),
    (("seashore", "sandbar", "coast", "beach"), "Beach", "Nature", "Images"),
    (("coral reef",), "Coral-Reef", "Nature", "Images"),
    (("lakeside", "lake"), "Lake", "Nature", "Images"),

    # Technology & Everyday Products
    (("cellular telephone", "cell phone", "mobile phone"), "Smartphone", "Products", "Images"),
    (("laptop", "notebook computer"), "Laptop", "Products", "Images"),
    (("coffee mug", "cup", "espresso"), "Coffee-Mug", "Products", "Images"),
    (("water bottle", "water jug", "pop bottle"), "Water-Bottle", "Products", "Images"),
    (("space bar", "computer keyboard", "typewriter keyboard"), "Keyboard", "Products", "Images"),
    (("computer mouse", "mouse"), "Computer-Mouse", "Products", "Images"),
    (("camera", "reflex camera", "polaroid camera"), "Camera", "Products", "Images"),
    (("sports car", "convertible", "minivan", "cab", "limousine", "car"), "Car", "Vehicles", "Images"),
    (("mountain bike", "bicycle", "tandem bicycle"), "Bicycle", "Vehicles", "Images"),
    (("desk",), "Desk", "Products", "Images"),
    (("dining table",), "Table", "Products", "Images"),
    (("guitar", "acoustic guitar", "electric guitar"), "Guitar", "Products", "Images"),

    # Documents & Printed Items (fallback when OCR was minimal)
    (("envelope",), "Envelope", "Documents", "Documents"),
    (("menu",), "Menu", "Documents", "Documents"),
    (("book jacket", "comic book", "binder"), "Book-Cover", "Documents", "Documents"),

    # Screenshots / Screens
    (("television", "screen", "monitor", "web site", "scoreboard"), "UI-Screenshot", "Screenshots", "Images"),
]


class VisionClassifierService:
    """
    Lightweight, local visual image classifier using MobileNetV3-Small.
    Identifies common objects, apparel, nature, animals, and products when OCR cannot read text.
    Lazy-loads weights on demand to ensure instant startup and minimal RAM footprint.
    """

    def __init__(self):
        self._model = None
        self._preprocess = None
        self._categories = None
        self._lock = threading.Lock()
        self._available = None

    def is_available(self) -> bool:
        """Check if torchvision and torch runtime dependencies are available."""
        if not settings.VISION_ENABLED:
            return False
        if self._available is not None:
            return self._available
        try:
            import torch
            import torchvision
            self._available = True
        except Exception as e:
            logger.warning(f"Vision classification unavailable: {e}")
            self._available = False
        return self._available

    def get_engine_info(self) -> Dict[str, Any]:
        """Diagnostic engine status report."""
        avail = self.is_available()
        return {
            "available": avail,
            "engine": "torchvision-mobilenet-v3-small",
            "model_family": "MobileNetV3-Small (ImageNet-1K)",
            "classes_supported": 1000,
            "enabled": settings.VISION_ENABLED,
            "confidence_threshold": settings.VISION_CONFIDENCE_THRESHOLD,
            "initialized": self._model is not None,
        }

    def _ensure_model_loaded(self) -> bool:
        """Thread-safe lazy initialization of MobileNetV3-Small weights."""
        if self._model is not None:
            return True
        if not self.is_available():
            return False

        with self._lock:
            if self._model is not None:
                return True
            try:
                import torch
                from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights

                logger.info("Initializing MobileNetV3-Small vision classification model...")
                weights = MobileNet_V3_Small_Weights.DEFAULT
                model = mobilenet_v3_small(weights=weights)
                model.eval()

                self._model = model
                self._preprocess = weights.transforms()
                self._categories = weights.meta.get("categories", [])
                logger.info(f"MobileNetV3-Small ready with {len(self._categories)} classes.")
                return True
            except Exception as e:
                logger.error(f"Failed to load vision model: {e}")
                self._available = False
                return False

    def classify_image(
        self,
        image_input: Union[bytes, str, Path, Image.Image],
        filename: str = ""
    ) -> Dict[str, Any]:
        """
        Classifies visual content of an image.
        Returns:
            {
                "success": bool,
                "concept": Optional[str],        # e.g. "T-Shirt", "Dog", "Laptop"
                "category": Optional[str],       # e.g. "Clothing", "Animals", "Products"
                "folder": Optional[str],         # e.g. "Images", "Documents"
                "confidence_score": float,       # 0.0 to 1.0
                "confidence_level": str,         # "high", "medium", "low", "ambiguous"
                "raw_label": str,                # raw ImageNet class name
                "is_ambiguous": bool,
                "error": Optional[str]
            }
        """
        if not self._ensure_model_loaded():
            return {
                "success": False,
                "concept": None,
                "category": None,
                "folder": None,
                "confidence_score": 0.0,
                "confidence_level": "ambiguous",
                "raw_label": "",
                "is_ambiguous": True,
                "error": "Vision model not available",
            }

        try:
            import torch

            # 1. Load Image
            if isinstance(image_input, (str, Path)):
                img = Image.open(str(image_input))
            elif isinstance(image_input, bytes):
                img = Image.open(io.BytesIO(image_input))
            elif isinstance(image_input, Image.Image):
                img = image_input
            else:
                return {
                    "success": False,
                    "concept": None,
                    "category": None,
                    "folder": None,
                    "confidence_score": 0.0,
                    "confidence_level": "ambiguous",
                    "raw_label": "",
                    "is_ambiguous": True,
                    "error": "Invalid image input format",
                }

            # 2. Convert to RGB with white background for alpha channels
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 3. Cap max dimension to save RAM and speed up preprocessing
            max_dim = settings.VISION_MAX_INPUT_DIMENSION
            w, h = img.size
            if max(w, h) > max_dim:
                ratio = max_dim / float(max(w, h))
                new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
                img = img.resize(new_size, Image.Resampling.BILINEAR)

            # 4. Preprocess and infer
            batch = self._preprocess(img).unsqueeze(0)
            with torch.no_grad():
                logits = self._model(batch).squeeze(0)
                probs = logits.softmax(0)

            top_k = torch.topk(probs, 5)
            top_scores = [top_k.values[i].item() for i in range(5)]
            top_indices = [top_k.indices[i].item() for i in range(5)]
            top_labels = [self._categories[idx] if idx < len(self._categories) else "" for idx in top_indices]

            best_score = top_scores[0]
            best_raw_label = top_labels[0]

            # 5. Semantic Mapping to clean concept
            matched_concept: Optional[str] = None
            matched_category: Optional[str] = None
            matched_folder: Optional[str] = None
            matched_score: float = best_score

            # Check top-1 first, then top-3 if top-1 is a subtle sub-breed or related label
            for label, score in zip(top_labels[:3], top_scores[:3]):
                l_lower = label.lower()
                for keywords, concept, category, folder in IMAGENET_CONCEPT_MAP:
                    if any(kw in l_lower for kw in keywords):
                        matched_concept = concept
                        matched_category = category
                        matched_folder = folder
                        matched_score = score
                        break
                if matched_concept:
                    break

            # 6. Confidence gating
            # If the best score or matched concept score meets threshold:
            threshold = settings.VISION_CONFIDENCE_THRESHOLD
            is_confident = (matched_concept is not None) and (matched_score >= threshold)

            if is_confident:
                confidence_level = "high" if matched_score >= 0.35 else "medium"
                logger.info(
                    f"[Diagnostic:Vision] Image '{filename}': raw='{best_raw_label}' ({matched_score:.2%}) "
                    f"-> Concept: '{matched_concept}', Category: '{matched_category}', Conf: '{confidence_level}'"
                )
                return {
                    "success": True,
                    "concept": matched_concept,
                    "category": matched_category,
                    "folder": matched_folder or "Images",
                    "confidence_score": matched_score,
                    "confidence_level": confidence_level,
                    "raw_label": best_raw_label,
                    "is_ambiguous": False,
                    "error": None,
                }

            # Uncertain, ambiguous, or generic texture
            logger.info(
                f"[Diagnostic:Vision] Image '{filename}': raw='{best_raw_label}' ({best_score:.2%}) "
                f"-> Below confidence threshold or unmapped; retained original filename."
            )
            return {
                "success": False,
                "concept": None,
                "category": "Images",
                "folder": "Images",
                "confidence_score": best_score,
                "confidence_level": "ambiguous",
                "raw_label": best_raw_label,
                "is_ambiguous": True,
                "error": None,
            }

        except Exception as e:
            logger.warning(f"Error during vision classification for {filename}: {e}")
            return {
                "success": False,
                "concept": None,
                "category": None,
                "folder": None,
                "confidence_score": 0.0,
                "confidence_level": "ambiguous",
                "raw_label": "",
                "is_ambiguous": True,
                "error": str(e),
            }


vision_service = VisionClassifierService()
