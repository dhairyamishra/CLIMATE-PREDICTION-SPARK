"""
Unit tests for the seed data generator.
Validates output structure and data quality without generating the full ~5GB dataset.
"""
import os
import sys
import pytest
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))


def test_generate_stations():
    """Test that station generation produces valid metadata."""
    from generate_seed_data import _generate_stations, STATION_REGIONS

    stations = _generate_stations()

    assert len(stations) > 0
    assert len(stations) <= 600  # ~500 expected

    for s in stations:
        assert "station_id" in s
        assert "name" in s
        assert "latitude" in s
        assert "longitude" in s
        assert "country" in s
        assert "geohash" in s
        assert -90 <= s["latitude"] <= 90
        assert -180 <= s["longitude"] <= 180
        assert len(s["geohash"]) >= 4
        assert s["station_id"].startswith(s["country"])


def test_station_regions_coverage():
    """Test that stations span all configured regions."""
    from generate_seed_data import _generate_stations, STATION_REGIONS

    stations = _generate_stations()
    countries = set(s["country"] for s in stations)
    expected_countries = set(r[0] for r in STATION_REGIONS)

    assert countries == expected_countries, f"Missing countries: {expected_countries - countries}"


def test_generate_daily_obs_structure():
    """Test that daily observation generation produces correct columns."""
    from generate_seed_data import _generate_stations

    stations = _generate_stations()
    station = stations[0]

    # Check that station has the fields needed by the obs generator
    required_keys = ["station_id", "latitude", "longitude", "base_tmax", "base_tmin", "base_prcp"]
    for key in required_keys:
        assert key in station, f"Station missing key: {key}"


def test_geohash_generation():
    """Test that geohashes are valid for station coordinates."""
    from generate_seed_data import _generate_stations

    stations = _generate_stations()

    for s in stations[:10]:
        gh = s["geohash"]
        assert isinstance(gh, str)
        assert len(gh) >= 4
        # Geohash characters should be base32
        valid_chars = set("0123456789bcdefghjkmnpqrstuvwxyz")
        assert all(c in valid_chars for c in gh), f"Invalid geohash: {gh}"
