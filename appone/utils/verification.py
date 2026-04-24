import requests
from django.core.cache import cache

NIGERIA_COUNTRY_CODE = "NG"
NIGERIA_COUNTRY_NAME = "Nigeria"
_LOCAL_IP_PREFIXES = ("127.", "192.168.", "10.", "172.", "::1")


def _build_location_result(
    country_code: str,
    country_name: str,
    city: str,
    region: str,
    latitude,
    longitude,
) -> dict:
    """Normalise the result dict and add the convenience `is_nigeria` flag."""
    return {
        "country_code": country_code,
        "country_name": country_name,
        "city": city,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "is_nigeria": country_code.upper() == NIGERIA_COUNTRY_CODE,
    }


def get_ip_location(ip_address: str) -> dict | None:
    cache_key = f"ip_location_{ip_address}"
    cached_location = cache.get(cache_key)

    if cached_location:
        return cached_location
    result = None
    try:
        resp = requests.get(
            f"https://ipapi.co/{ip_address}/json/",
            timeout=5,
            headers={"User-Agent": "VirtualCitizenship/1.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("error"):
                result = _build_location_result(
                    country_code=data.get("country_code", ""),
                    country_name=data.get("country_name", ""),
                    city=data.get("city", ""),
                    region=data.get("region", ""),
                    latitude=data.get("latitude"),
                    longitude=data.get("longitude"),
                )
    except requests.RequestException:
        pass

    if not result:
        try:
            resp = requests.get(
                f"https://ip-api.com/json/{ip_address}"
                "?fields=status,country,countryCode,regionName,city,lat,lon",
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    result = _build_location_result(
                        country_code=data.get("countryCode", ""),
                        country_name=data.get("country", ""),
                        city=data.get("city", ""),
                        region=data.get("regionName", ""),
                        latitude=data.get("lat"),
                        longitude=data.get("lon"),
                    )
        except requests.RequestException:
            pass
    if result:
        cache.set(cache_key, result, timeout=86400)

    return result


def verify_user_is_in_nigeria(ip_address: str) -> tuple[bool, dict | None, str]:
    if ip_address.startswith(_LOCAL_IP_PREFIXES):
        return (
            True,
            {
                "country_code": "NG",
                "country_name": "Nigeria",
                "city": "Localhost",
                "is_nigeria": True,
            },
            "Local environment bypassed",
        )
    location = get_ip_location(ip_address)

    if location is None:
        return False, None, "Unable to determine your location. Please try again later."

    if location["is_nigeria"]:
        msg = f"Location verified: {location['city']}, {location['country_name']}"
        return True, location, msg

    country = location.get("country_name") or location.get("country_code") or "Unknown"
    msg = (
        f"Access restricted: your detected location ({country}) is outside Nigeria. "
        "You must be physically located in Nigeria to register."
    )
    return False, location, msg


def verify_nigerian_nin(nin):
    from django.conf import settings

    try:
        url = f"{settings.GOVT_API_BASE_URL}nin/verify"
        headers = {
            "Authorization": f"Bearer {settings.GOVT_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json={"nin": nin})
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def verify_company_registration(registration_number, country):
    from django.conf import settings

    try:
        api_endpoints = {
            "USA": f"{settings.GOVT_API_BASE_URL}us/company/verify",
            "UK": f"{settings.GOVT_API_BASE_URL}uk/company/verify",
            "NG": f"{settings.GOVT_API_BASE_URL}ng/cac/verify",
        }
        url = api_endpoints.get(country, api_endpoints["USA"])
        headers = {
            "Authorization": f"Bearer {settings.GOVT_API_KEY}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            json={"registration_number": registration_number},
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None
