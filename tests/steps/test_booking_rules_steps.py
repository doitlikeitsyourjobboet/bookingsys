import pytest
from pytest_bdd import given, scenarios, then, when, parsers
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from booking_rules import (
    AUTH_EMAIL_INPUT_KEY,
    AUTH_EMAIL_KEY,
    booking_failure_message,
    evaluate_email_form,
    format_my_booking_line,
    registration_status_message,
)


scenarios("../features/email_form.feature")
scenarios("../features/booking_rules.feature")
scenarios("../features/session_keys.feature")


@pytest.fixture
def ctx():
    return {}


@given("the email form has not been submitted")
def email_form_not_submitted(ctx):
    ctx["submitted"] = False


@given("the email form has been submitted")
def email_form_submitted(ctx):
    ctx["submitted"] = True


@when(parsers.parse('email form is evaluated with input "{raw_email}"'))
def evaluate_email_form_with_input(ctx, raw_email):
    ctx["decision"] = evaluate_email_form(ctx["submitted"], raw_email)


@when("email form is evaluated with blank input")
def evaluate_email_form_blank(ctx):
    ctx["decision"] = evaluate_email_form(ctx["submitted"], "")


@then("the email decision should stop")
def email_decision_stops(ctx):
    assert ctx["decision"].should_stop is True


@then("the email decision should continue")
def email_decision_continues(ctx):
    assert ctx["decision"].should_stop is False


@then(parsers.parse('the email decision message type should be "{message_type}"'))
def email_decision_message_type(ctx, message_type):
    assert ctx["decision"].message_type == message_type


@then(parsers.parse('the email decision message should be "{message}"'))
def email_decision_message(ctx, message):
    assert ctx["decision"].message == message


@then("the email decision should not contain an email")
def email_decision_no_email(ctx):
    assert ctx["decision"].email is None


@then(parsers.parse('the email decision email should be "{email}"'))
def email_decision_email(ctx, email):
    assert ctx["decision"].email == email


@then("the email decision should request rerun")
def email_decision_rerun(ctx):
    assert ctx["decision"].should_rerun is True


@when(parsers.parse('booking error is mapped from text "{error_text}"'))
def map_booking_error(ctx, error_text):
    ctx["booking_error_message"] = booking_failure_message(error_text)


@then(parsers.parse('mapped booking error message should be "{message}"'))
def mapped_booking_error_message(ctx, message):
    assert ctx["booking_error_message"] == message


@when(parsers.parse('registration status is evaluated for "{status}"'))
def evaluate_registration_status(ctx, status):
    ctx["registration_notice"] = registration_status_message(status)


@then("a registration warning notice should be returned")
def registration_warning_notice(ctx):
    assert ctx["registration_notice"] is not None
    assert ctx["registration_notice"][0] == "warning"


@then("a registration error notice should be returned")
def registration_error_notice(ctx):
    assert ctx["registration_notice"] is not None
    assert ctx["registration_notice"][0] == "error"


@then(parsers.parse('the registration notice message should be "{message}"'))
def registration_notice_message(ctx, message):
    assert ctx["registration_notice"] is not None
    assert ctx["registration_notice"][1] == message


@then("no registration notice should be returned")
def registration_no_notice(ctx):
    assert ctx["registration_notice"] is None


@when(parsers.parse('booking line is formatted with notes "{notes}" and start "{start_text}"'))
def format_booking_line(ctx, notes, start_text):
    normalized_notes = None if notes == "[none]" else notes
    ctx["booking_line"] = format_my_booking_line(normalized_notes, start_text)


@then(parsers.parse('formatted booking line should be "{expected_line}"'))
def formatted_booking_line(ctx, expected_line):
    assert ctx["booking_line"] == expected_line


@then(parsers.parse('auth email key should be "{expected_key}"'))
def auth_email_key_is(expected_key):
    assert AUTH_EMAIL_KEY == expected_key


@then(parsers.parse('auth email input key should be "{expected_key}"'))
def auth_email_input_key_is(expected_key):
    assert AUTH_EMAIL_INPUT_KEY == expected_key


@then("auth keys should be distinct")
def auth_keys_are_distinct():
    assert AUTH_EMAIL_KEY != AUTH_EMAIL_INPUT_KEY


@then("auth keys should be namespaced")
def auth_keys_are_namespaced():
    assert AUTH_EMAIL_KEY.startswith("auth_")
    assert AUTH_EMAIL_INPUT_KEY.startswith("auth_")
