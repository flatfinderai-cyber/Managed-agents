import pytest
from services.vmc_validator import check_template_bypass

def test_check_template_bypass_valid():
    """Valid messages that do not match filler patterns should return True."""
    valid_messages = [
        "This is a perfectly valid and substantial message about the property.",
        "I would like to schedule a viewing for tomorrow afternoon.",
        "Can you provide more details about the lease agreement?",
        "Sounds good, but what about the pet policy?",
        "Thank you for your message regarding the deposit. I will send it shortly.",
        "Great apartment, I love the location.",
        "Okay, let me review the documents and get back to you.",
        "Yes, I can move in on the first of the month.",
    ]

    for msg in valid_messages:
        assert check_template_bypass(msg) is True, f"Failed on valid message: {msg}"

def test_check_template_bypass_filler():
    """Messages that match filler patterns should return False."""
    filler_messages = [
        "sounds good",
        "sounds good.",
        "sounds good, looking forward to it",
        "Sounds Good! Looking forward to it.",
        "as discussed please confirm",
        "As discussed, please confirm.",
        "thank you for your message",
        "Thank you for your email.",
        "thank you for your response",
        "great",
        "perfect!",
        "wonderful. thank you",
        "ok",
        "okay, thank you.",
        "sure",
        "absolutely!",
        "of course.",
        "noted",
        "understood.",
        "yes",
        "No!",
        "will do",
        "done.",
        "confirmed",
        "lorem ipsum dolor sit amet",
        "asdf",
        "qwerty",
        "zzzz",
        "hjkl",
    ]

    for msg in filler_messages:
        assert check_template_bypass(msg) is False, f"Failed on filler message: {msg}"

def test_check_template_bypass_whitespace():
    """Filler patterns should be detected even with leading/trailing whitespace."""
    filler_messages = [
        "  sounds good  ",
        "\nokay\n",
        "\tnoted\t",
    ]

    for msg in filler_messages:
        assert check_template_bypass(msg) is False, f"Failed on filler message with whitespace: {msg}"
