import datetime as dt
from utils import slug, timedelta_to_hms

def test_slug():
    # Test cases for the slug function
    test_cases = [
        ("Hello World!", "hello-world"),
        ("Python_3.9", "python39"),
        ("   Leading and trailing spaces   ", "leading-and-trailing-spaces"),
        ("Special #$%&* characters!", "special--characters"),
        ("Multiple   Spaces", "multiple-spaces"),
        ("", ""),
    ]
    for input_str, expected_output in test_cases:
        assert slug(input_str) == expected_output

def test_timedelta_to_hms():
    # Test cases for the timedelta_to_hms function
    test_cases = [
        (dt.timedelta(hours=1, minutes=30, seconds=15), "1:30:15"),
        (dt.timedelta(minutes=45, seconds=5), "45:05"),
        (dt.timedelta(seconds=59), "00:59"),
        (dt.timedelta(hours=2), "2:00:00"),
        (dt.timedelta(hours=0, minutes=0, seconds=0), "00:00"),
        (dt.timedelta(hours=23, minutes=59, seconds=59), "23:59:59"),
    ]
    for td, expected_output in test_cases:
        assert timedelta_to_hms(td) == expected_output
