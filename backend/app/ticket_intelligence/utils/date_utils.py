from datetime import datetime, timedelta, date
from typing import Optional, Tuple
import calendar

DATEDURATION_CHOICES = [
    "Yesterday", "Today", "This Week", "Last Week", "Next Week",
    "This Month", "Last Month", "Next Month", "This Quarter",
    "Last Quarter", "Next Quarter", "This Year", "Last Year", "Next Year"
]

def get_quarter_bounds(year: int, quarter: int) -> Tuple[date, date]:
    """Returns the start and end date of a given quarter (1-4)."""
    start_month = 3 * quarter - 2
    end_month = 3 * quarter
    start_date = date(year, start_month, 1)
    end_date = date(year, end_month, calendar.monthrange(year, end_month)[1])
    return start_date, end_date

def resolve_date_filter(
    date_duration: Optional[str] = None, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> Tuple[str, str]:
    """
    Resolves date string bounds dynamically based on the requested duration.
    Falls back to 'Last Month' if nothing is provided.
    """
    if not date_duration and not start_date and not end_date:
        date_duration = "Last Month"
        
    if date_duration:
        today = date.today()
        # Normalize casing
        dur = date_duration.strip().title()
        
        if dur == "Today":
            return today.isoformat(), today.isoformat()
            
        elif dur == "Yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday.isoformat(), yesterday.isoformat()
            
        elif "Week" in dur:
            # Week starts on Monday (weekday() == 0)
            start_of_this_week = today - timedelta(days=today.weekday())
            if dur == "This Week":
                s = start_of_this_week
            elif dur == "Last Week":
                s = start_of_this_week - timedelta(days=7)
            elif dur == "Next Week":
                s = start_of_this_week + timedelta(days=7)
            else:
                s = start_of_this_week
                
            e = s + timedelta(days=6)
            return s.isoformat(), e.isoformat()
            
        elif "Month" in dur:
            if dur == "This Month":
                year, month = today.year, today.month
            elif dur == "Last Month":
                month = today.month - 1
                year = today.year
                if month == 0:
                    month = 12
                    year -= 1
            elif dur == "Next Month":
                month = today.month + 1
                year = today.year
                if month == 13:
                    month = 1
                    year += 1
            else:
                year, month = today.year, today.month
                
            s = date(year, month, 1)
            e = date(year, month, calendar.monthrange(year, month)[1])
            return s.isoformat(), e.isoformat()
            
        elif "Quarter" in dur:
            current_quarter = (today.month - 1) // 3 + 1
            year = today.year
            
            if dur == "This Quarter":
                q = current_quarter
            elif dur == "Last Quarter":
                q = current_quarter - 1
                if q == 0:
                    q = 4
                    year -= 1
            elif dur == "Next Quarter":
                q = current_quarter + 1
                if q == 5:
                    q = 1
                    year += 1
            else:
                q = current_quarter
                
            s, e = get_quarter_bounds(year, q)
            return s.isoformat(), e.isoformat()
            
        elif "Year" in dur:
            if dur == "This Year":
                year = today.year
            elif dur == "Last Year":
                year = today.year - 1
            elif dur == "Next Year":
                year = today.year + 1
            else:
                year = today.year
                
            s = date(year, 1, 1)
            e = date(year, 12, 31)
            return s.isoformat(), e.isoformat()
            
    # If date_duration is not provided but custom dates are
    resolved_start = start_date if start_date else (end_date if end_date else date.today().isoformat())
    resolved_end = end_date if end_date else (start_date if start_date else date.today().isoformat())
    
    return resolved_start, resolved_end
