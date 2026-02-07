from dataclasses import dataclass
import re

AUTH_EMAIL_KEY = "auth_email"
AUTH_EMAIL_INPUT_KEY = "auth_email_input"

EMAIL_REQUIRED_MESSAGE = "Enter your username or email to continue."
EMAIL_INVALID_MESSAGE = "Enter a valid email address (for example, you@example.com)."
EMAIL_SUBMIT_MESSAGE = "Enter your username or email and click Continue."
PENDING_REGISTRATION_MESSAGE = "Your registration is pending approval."
REJECTED_REGISTRATION_MESSAGE = "Your registration was rejected."

_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True)
class EmailFormDecision:
    should_stop: bool
    message_type: str | None = None
    message: str | None = None
    email: str | None = None
    should_rerun: bool = False


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def normalize_identifier(raw: str) -> str:
    return raw.strip()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_PATTERN.fullmatch(email))


def evaluate_email_form(submitted: bool, raw_email: str) -> EmailFormDecision:
    if not submitted:
        return EmailFormDecision(
            should_stop=True,
            message_type="info",
            message=EMAIL_SUBMIT_MESSAGE,
        )

    identifier = normalize_identifier(raw_email)
    if not identifier:
        return EmailFormDecision(
            should_stop=True,
            message_type="warning",
            message=EMAIL_REQUIRED_MESSAGE,
        )

    # If users type something that looks like an email, validate email syntax.
    # Otherwise treat it as a username.
    if "@" in identifier and not is_valid_email(identifier.lower()):
        return EmailFormDecision(
            should_stop=True,
            message_type="warning",
            message=EMAIL_INVALID_MESSAGE,
        )

    return EmailFormDecision(
        should_stop=False,
        email=normalize_email(identifier) if "@" in identifier else identifier,
        should_rerun=True,
    )


def booking_failure_message(error: Exception | str) -> str:
    text = str(error)
    if "email_not_allowed" in text:
        return "Booking failed: your email is not allowed yet."
    return "Booking failed. Please try again."


def registration_status_message(status: str) -> tuple[str, str] | None:
    if status == "pending":
        return ("warning", PENDING_REGISTRATION_MESSAGE)
    if status == "rejected":
        return ("error", REJECTED_REGISTRATION_MESSAGE)
    return None


def format_my_booking_line(notes: str | None, start_display: str) -> str:
    session_name = notes or "Net Session"
    return f"Confirmed: **{session_name}** - {start_display}"
