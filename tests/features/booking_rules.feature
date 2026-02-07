Feature: Booking Rule Messaging
  Ensure user-facing messages stay friendly and stable.

  Scenario: Booking error for not-allowed email is specific
    When booking error is mapped from text "RPC failed: email_not_allowed"
    Then mapped booking error message should be "Booking failed: your email is not allowed yet."

  Scenario: Generic booking error gets generic message
    When booking error is mapped from text "timeout"
    Then mapped booking error message should be "Booking failed. Please try again."

  Scenario: Pending registration status has warning message
    When registration status is evaluated for "pending"
    Then a registration warning notice should be returned
    And the registration notice message should be "Your registration is pending approval."

  Scenario: Rejected registration status has error message
    When registration status is evaluated for "rejected"
    Then a registration error notice should be returned
    And the registration notice message should be "Your registration was rejected."

  Scenario: Approved registration has no special notice
    When registration status is evaluated for "approved"
    Then no registration notice should be returned

  Scenario Outline: Booking line formatting
    When booking line is formatted with notes "<notes>" and start "<start_text>"
    Then formatted booking line should be "<expected_line>"

    Examples:
      | notes       | start_text             | expected_line                                     |
      | Winter Nets | 10th Feb 2026 @7:00pm | Confirmed: **Winter Nets** - 10th Feb 2026 @7:00pm |
      | [none]      | 10th Feb 2026 @7:00pm | Confirmed: **Net Session** - 10th Feb 2026 @7:00pm |
