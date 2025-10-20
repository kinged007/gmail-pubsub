from src.utils.logger import setup_logger
import re
from datetime import datetime, timezone, timedelta
from hashlib import md5


logger = setup_logger(__name__)

# Default date format for parsing date strings like '20-Oct-2025 11:32 CEST'
# All parsed dates are converted to UTC for standardization
DEFAULT_DATE_FORMAT = "%d-%b-%Y %H:%M"

def parse_date(date_string: str) -> datetime:
    """
    Parse date string with timezone awareness and convert to UTC.

    Handles date strings like '20-Oct-2025 11:32 CEST' and converts them to
    UTC datetime objects for standardization across the application.
    
    Args:
        date_string: Date string to parse (e.g., '20-Oct-2025 11:32 CEST')
        
    Returns:
        UTC datetime object or None if parsing fails
    """
    try:
        date_string = date_string.strip()
        
        # Define timezone mappings using UTC offsets (hours)
        timezone_offsets = {
            'UTC': 0,
            'GMT': 0,
            'CEST': 2,    # Central European Summer Time (UTC+2)
            'CET': 1,     # Central European Time (UTC+1)
            'EST': -5,    # Eastern Standard Time (UTC-5)
            'EDT': -4,    # Eastern Daylight Time (UTC-4)
            'PST': -8,    # Pacific Standard Time (UTC-8)
            'PDT': -7,    # Pacific Daylight Time (UTC-7)
        }
        
        # Extract timezone abbreviation if present
        timezone_match = re.search(r'\s+([A-Z]{2,4})$', date_string)
        
        if timezone_match:
            # Has timezone info
            timezone_abbr = timezone_match.group(1)
            date_part = date_string[:timezone_match.start()]
            
            # Parse the datetime without timezone
            dt_naive = datetime.strptime(date_part, DEFAULT_DATE_FORMAT)
            
            # Apply timezone offset and convert to UTC
            if timezone_abbr in timezone_offsets:
                offset_hours = timezone_offsets[timezone_abbr]
                # Create timezone-aware datetime in the original timezone
                tz = timezone(timedelta(hours=offset_hours))
                dt_aware = dt_naive.replace(tzinfo=tz)
                # Convert to UTC
                dt_utc = dt_aware.astimezone(timezone.utc)
            else:
                # Unknown timezone, default to UTC but log warning
                logger.warning("Unknown timezone '%s', treating as UTC", timezone_abbr)
                dt_utc = dt_naive.replace(tzinfo=timezone.utc)
        else:
            # No timezone info, treat as UTC
            dt_naive = datetime.strptime(date_string, DEFAULT_DATE_FORMAT)
            dt_utc = dt_naive.replace(tzinfo=timezone.utc)
            
        return dt_utc
        
    except (ValueError, AttributeError) as e:
        logger.warning("Failed to parse date '%s': %s", date_string, e)
        return None
    

def create_hash(string: str) -> str:
    """
    Create a simple hash of the input string for deduplication.

    Args:
        string: Input string to hash.
    """
    # Simple hash function - not sure if this is the best way to do it?
    return md5(string.encode('utf-8')).hexdigest()


