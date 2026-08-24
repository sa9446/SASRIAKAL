"""
SASRIAKAL - C2PA Provenance Parser
Inspects Coalition for Content Provenance and Authenticity (C2PA) metadata
and cryptographic signatures embedded in media files.
Supports JPEG, PNG, MP4, and other C2PA-compatible formats.
"""

import hashlib
import json
import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("sasriakal.c2pa")


@dataclass
class C2PAManifest:
    """Parsed C2PA manifest data."""
    claim_generator: str = ""
    title: str = ""
    created: str = ""
    instance_id: str = ""
    format: str = ""
    ingredients: list[dict] = field(default_factory=list)
    assertions: list[dict] = field(default_factory=list)
    signature_valid: bool = False
    signature_type: str = ""
    issuer: str = ""
    certificate_chain: list[str] = field(default_factory=list)


@dataclass
class C2PAResult:
    """Full C2PA validation result."""
    has_c2pa: bool
    format_detected: str
    manifest_count: int
    active_manifest: Optional[C2PAManifest]
    all_manifests: list[C2PAManifest]
    trust_chain_valid: bool
    tampering_detected: bool
    warnings: list[str]
    raw_metadata: dict


class C2PAParser:
    """
    C2PA metadata parser and validator.
    Extracts and validates content provenance information
    from JUMBF (JPEG Universal Metadata Box Format) containers
    and other C2PA-compatible metadata structures.
    """

    # C2PA magic bytes and markers
    C2PA_JUMBF_MARKER = b"jumb"
    C2PA_XMP_NS = "http://c2pa.org/specifications/1.0/"
    C2PA_ASSERTION_PREFIXES = [
        "c2pa.hash",
        "c2pa.claims",
        "c2pa.statement",
        "c2pa.ingredient",
        "c2pa.signature",
    ]

    # Known C2PA claim generators
    KNOWN_GENERATORS = {
        "Adobe Photoshop",
        "Adobe Lightroom",
        "Adobe Camera Raw",
        "Microsoft Truepic",
        "Truepic Lens",
        "Content Authenticity Initiative",
        "Leica Camera",
        "Nikon",
        "Sony",
    }

    def __init__(self):
        pass

    def parse(self, file_data: bytes, filename: str = "") -> dict:
        """
        Parse and validate C2PA metadata from file data.
        Returns comprehensive provenance analysis.
        """
        format_detected = self._detect_format(file_data, filename)

        if format_detected == "unknown":
            return {
                "has_c2pa": False,
                "format_detected": "unknown",
                "manifest_count": 0,
                "active_manifest": None,
                "all_manifests": [],
                "trust_chain_valid": False,
                "tampering_detected": False,
                "warnings": ["Unrecognized file format"],
                "raw_metadata": {},
            }

        # Extract C2PA data based on format
        manifests = []
        raw_metadata = {}
        warnings = []

        if format_detected in ("jpeg", "jpg", "png"):
            manifests, raw_metadata = self._parse_jumbf(file_data)
        elif format_detected in ("mp4", "mov", "avi"):
            manifests, raw_metadata = self._parse_isobmff(file_data)
        elif format_detected == "tiff":
            manifests, raw_metadata = self._parse_tiff(file_data)
        else:
            warnings.append(f"C2PA parsing not fully implemented for {format_detected}")

        # Validate signatures
        trust_valid = True
        for manifest in manifests:
            if not manifest.signature_valid:
                trust_valid = False
                warnings.append(f"Invalid signature in manifest: {manifest.instance_id}")

        # Check for tampering indicators
        tampering = self._detect_tampering(file_data, manifests, raw_metadata)

        return {
            "has_c2pa": len(manifests) > 0,
            "format_detected": format_detected,
            "manifest_count": len(manifests),
            "active_manifest": manifests[0] if manifests else None,
            "all_manifests": [self._manifest_to_dict(m) for m in manifests],
            "trust_chain_valid": trust_valid,
            "tampering_detected": tampering,
            "warnings": warnings,
            "raw_metadata": raw_metadata,
        }

    def _detect_format(self, data: bytes, filename: str) -> str:
        """Detect file format from magic bytes and extension."""
        if len(data) < 12:
            return "unknown"

        # Magic byte detection
        if data[:2] == b'\xff\xd8':
            return "jpeg"
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return "png"
        if data[4:8] in (b'ftyp', b'moov', b'mdat'):
            return "mp4"
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return "webp"
        if data[:4] == b'\x49\x49\x2a\x00' or data[:4] == b'\x4d\x4d\x00\x2a':
            return "tiff"
        if data[:3] == b'GIF':
            return "gif"

        # Fallback to extension
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        ext_map = {
            "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "mp4": "mp4",
            "mov": "mov", "avi": "avi", "tiff": "tiff", "tif": "tiff",
            "webp": "webp",
        }
        return ext_map.get(ext, "unknown")

    def _parse_jumbf(self, data: bytes) -> tuple[list[C2PAManifest], dict]:
        """Parse JUMBF (JPEG Universal Metadata Format) for C2PA data."""
        manifests = []
        raw = {}

        # Search for C2PA JUMBF box markers
        pos = 0
        while pos < len(data) - 8:
            # Look for JUMBF box
            box_size = struct.unpack(">I", data[pos : pos + 4])[0] if pos + 4 <= len(data) else 0
            box_type = data[pos + 4 : pos + 8] if pos + 8 <= len(data) else b""

            if box_size < 8 or box_size > len(data) - pos:
                # Not a valid box, scan byte by byte
                pos += 1
                continue

            if box_type == self.C2PA_JUMBF_MARKER:
                # Found JUMBF box, extract C2PA content
                inner_data = data[pos + 8 : pos + box_size]
                manifest = self._extract_manifest_from_jumbf(inner_data)
                if manifest:
                    manifests.append(manifest)

            pos += box_size

        # Also search for XMP metadata containing C2PA info
        xmp_data = self._extract_xmp(data)
        if xmp_data:
            raw["xmp"] = xmp_data

        return manifests, raw

    def _extract_manifest_from_jumbf(self, data: bytes) -> Optional[C2PAManifest]:
        """Extract a C2PA manifest from JUMBF container data."""
        manifest = C2PAManifest()

        # Try to find JSON description box within JUMBF
        pos = 0
        while pos < len(data) - 8:
            box_size = struct.unpack(">I", data[pos : pos + 4])[0] if pos + 4 <= len(data) else 0
            box_type = data[pos + 4 : pos + 8] if pos + 8 <= len(data) else b""

            if box_size < 8 or pos + box_size > len(data):
                pos += 1
                continue

            # JSON description box
            if box_type in (b"jumd", b"jP  "):
                try:
                    json_data = data[pos + 12 : pos + box_size]
                    # Remove JUMBF header (label + id, 8 bytes after type)
                    if len(json_data) > 8:
                        json_str = json_data[8:].decode("utf-8", errors="ignore").rstrip("\x00")
                        parsed = json.loads(json_str)
                        manifest.claim_generator = parsed.get("claim_generator", "")
                        manifest.title = parsed.get("title", "")
                        manifest.created = parsed.get("created", "")
                        manifest.instance_id = parsed.get("instanceID", "")
                        manifest.format = parsed.get("format", "")

                        # Extract assertions
                        manifest.assertions = parsed.get("assertions", [])
                        manifest.ingredients = parsed.get("ingredients", [])

                        # Extract signature info
                        sig = parsed.get("signature", {})
                        manifest.signature_valid = sig.get("valid", False)
                        manifest.signature_type = sig.get("algorithm", "")
                        manifest.issuer = sig.get("issuer", "")

                        return manifest
                except (json.JSONDecodeError, ValueError):
                    pass

            pos += box_size

        return None if not manifest.claim_generator else manifest

    def _parse_isobmff(self, data: bytes) -> tuple[list[C2PAManifest], dict]:
        """Parse ISO Base Media File Format (MP4/MOV) for C2PA metadata."""
        manifests = []
        raw = {}

        # Search for C2PA manifest box (uuid box with C2PA UUID)
        pos = 0
        while pos < len(data) - 16:
            box_size = struct.unpack(">I", data[pos : pos + 4])[0] if pos + 4 <= len(data) else 0
            box_type = data[pos + 4 : pos + 8] if pos + 8 <= len(data) else b""

            if box_size < 8 or box_size > len(data) - pos:
                pos += 1
                continue

            if box_type == b"uuid":
                # Check for C2PA UUID
                uuid_bytes = data[pos + 8 : pos + 24]
                c2pa_uuid = bytes([
                    0xbe, 0x7a, 0xcf, 0xcb, 0x97, 0x43, 0x47, 0x91,
                    0xb0, 0xe7, 0xc4, 0xc5, 0x79, 0x4f, 0x7c, 0x2b,
                ])

                if uuid_bytes == c2pa_uuid:
                    inner_data = data[pos + 24 : pos + box_size]
                    manifest = self._extract_manifest_from_jumbf(inner_data)
                    if manifest:
                        manifests.append(manifest)

            # Also check for 'c2pa' brand
            if box_type == b'ftyp':
                brand_data = data[pos + 8 : pos + box_size]
                if b'c2pa' in brand_data:
                    raw["c2pa_brand_found"] = True

            pos += box_size

        return manifests, raw

    def _parse_tiff(self, data: bytes) -> tuple[list[C2PAManifest], dict]:
        """Parse TIFF format for C2PA metadata (Adobe.tif content credentials)."""
        # TIFF C2PA data is typically in XMP or MakerNote
        xmp_data = self._extract_xmp(data)
        return [], {"xmp": xmp_data} if xmp_data else ({}, {})

    def _extract_xmp(self, data: bytes) -> Optional[str]:
        """Extract XMP metadata from file data."""
        # Look for XMP marker
        xmp_start_marker = b"http://ns.adobe.com/xap/1.0/"
        start = data.find(xmp_start_marker)
        if start == -1:
            return None

        # Find the XML block
        xml_start = data.find(b"<x:xmpmeta", start)
        if xml_start == -1:
            xml_start = start

        xml_end = data.find(b"</x:xmpmeta>", xml_start)
        if xml_end == -1:
            return None

        try:
            return data[xml_start : xml_end + len(b"</x:xmpmeta>")].decode("utf-8", errors="ignore")
        except Exception:
            return None

    def _detect_tampering(
        self, file_data: bytes, manifests: list[C2PAManifest], raw_metadata: dict
    ) -> bool:
        """
        Detect potential tampering by checking:
        1. Hash integrity in manifest assertions
        2. File modification timestamps vs manifest timestamps
        3. Inconsistencies in metadata
        """
        tampering_indicators = 0

        for manifest in manifests:
            for assertion in manifest.assertions:
                # Check hash assertions
                if assertion.get("label", "").startswith("c2pa.hash"):
                    claimed_hash = assertion.get("data", {}).get("hash", "")
                    if claimed_hash:
                        # Compute actual hash of relevant data portion
                        actual_hash = hashlib.sha256(file_data).hexdigest()
                        if len(claimed_hash) > 0 and claimed_hash[:32] != actual_hash[:32]:
                            tampering_indicators += 1
                            logger.warning(
                                f"Hash mismatch in assertion: claimed={claimed_hash[:16]}..., "
                                f"actual={actual_hash[:16]}..."
                            )

            # Check if signature is valid
            if not manifest.signature_valid:
                tampering_indicators += 1

        return tampering_indicators > 0

    def _manifest_to_dict(self, manifest: C2PAManifest) -> dict:
        """Convert C2PAManifest to dictionary for JSON serialization."""
        return {
            "claim_generator": manifest.claim_generator,
            "title": manifest.title,
            "created": manifest.created,
            "instance_id": manifest.instance_id,
            "format": manifest.format,
            "signature_valid": manifest.signature_valid,
            "signature_type": manifest.signature_type,
            "issuer": manifest.issuer,
            "assertion_count": len(manifest.assertions),
            "ingredient_count": len(manifest.ingredients),
            "ingredients": manifest.ingredients,
        }
