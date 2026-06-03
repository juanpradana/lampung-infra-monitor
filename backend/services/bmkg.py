"""BMKG data fetcher - monitors earthquakes and extreme weather."""
import logging
from datetime import datetime
from typing import Optional
import httpx
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

BMKG_AUTO_GEMPA = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.xml"
BMKG_GEMPA_DIRASAKAN = "https://data.bmkg.go.id/DataMKG/TEWS/gempadirasakan.xml"
BMKG_GEMPA_TERKINI = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.xml"

# Tighter timeouts: 5s connect, 10s read — prevents indefinite hangs
BMKG_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)


async def fetch_latest_earthquake() -> Optional[dict]:
    """Fetch latest earthquake from BMKG."""
    try:
        async with httpx.AsyncClient(timeout=BMKG_TIMEOUT) as client:
            resp = await client.get(BMKG_AUTO_GEMPA)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        gempa = root.find(".//gempa")
        if gempa is None:
            return None

        coords_text = gempa.findtext("point/coordinates", "")
        lat, lon = None, None
        if coords_text:
            parts = coords_text.split(",")
            if len(parts) == 2:
                lat, lon = float(parts[0]), float(parts[1])

        return {
            "title": f"Gempa {gempa.findtext('Magnitude', '?')} SR - {gempa.findtext('Wilayah', '?')}",
            "description": (
                f"Magnitudo: {gempa.findtext('Magnitude', '?')} SR\n"
                f"Kedalaman: {gempa.findtext('Kedalaman', '?')}\n"
                f"Lokasi: {gempa.findtext('Wilayah', '?')}\n"
                f"Dirasakan: {gempa.findtext('Dirasakan', '-')}"
            ),
            "latitude": lat,
            "longitude": lon,
            "occurred_at": gempa.findtext("DateTime", None),
            "source": "BMKG",
            "source_url": "https://bmkg.go.id",
            "raw_xml": ET.tostring(gempa, encoding="unicode"),
        }
    except Exception as e:
        logger.error(f"BMKG fetch error: {e}")
        return None


async def fetch_recent_earthquakes() -> list[dict]:
    """Fetch recent felt earthquakes from BMKG."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=BMKG_TIMEOUT) as client:
            resp = await client.get(BMKG_GEMPA_DIRASAKAN)
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        for gempa in root.findall(".//gempa"):
            coords_text = gempa.findtext("point/coordinates", "")
            lat, lon = None, None
            if coords_text:
                parts = coords_text.split(",")
                if len(parts) == 2:
                    lat, lon = float(parts[0]), float(parts[1])

            results.append({
                "title": f"Gempa Dirasakan {gempa.findtext('Magnitude', '?')} SR - {gempa.findtext('Wilayah', '?')}",
                "description": (
                    f"Magnitudo: {gempa.findtext('Magnitude', '?')} SR\n"
                    f"Kedalaman: {gempa.findtext('Kedalaman', '?')}\n"
                    f"Lokasi: {gempa.findtext('Wilayah', '?')}\n"
                    f"Dirasakan: {gempa.findtext('Dirasakan', '-')}"
                ),
                "latitude": lat,
                "longitude": lon,
                "occurred_at": gempa.findtext("DateTime", None),
                "source": "BMKG",
                "source_url": "https://bmkg.go.id",
            })
    except Exception as e:
        logger.error(f"BMKG gempa dirasakan fetch error: {e}")

    return results


async def fetch_latest_earthquake_mmi() -> Optional[dict]:
    """Fetch latest earthquake MMI shakemap from BMKG."""
    try:
        async with httpx.AsyncClient(timeout=BMKG_TIMEOUT) as client:
            resp = await client.get("https://data.bmkg.go.id/DataMKG/TEWS/autogempa.xml")
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        gempa = root.find(".//gempa")
        if gempa is None:
            return None

        shakemap = gempa.findtext("Shakemap", None)
        if shakemap:
            return {
                "shakemap_url": f"https://data.bmkg.go.id/DataMKG/TEWS/{shakemap}"
            }
    except Exception as e:
        logger.error(f"BMKG shakemap error: {e}")
    return None
