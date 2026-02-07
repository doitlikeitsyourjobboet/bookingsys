Feature: Email Form Flow
  Keep email-entry behavior predictable and safe.

  Scenario: User must submit form before continuing
    Given the email form has not been submitted
    When email form is evaluated with input "player@example.com"
    Then the email decision should stop
    And the email decision message type should be "info"
    And the email decision message should be "Enter your username or email and click Continue."
    And the email decision should not contain an email

  Scenario: Blank identifier is rejected
    Given the email form has been submitted
    When email form is evaluated with blank input
    Then the email decision should stop
    And the email decision message type should be "warning"
    And the email decision message should be "Enter your username or email to continue."

  Scenario: Invalid email format is rejected when it looks like an email
    Given the email form has been submitted
    When email form is evaluated with input "not-an-email@"
    Then the email decision should stop
    And the email decision message type should be "warning"
    And the email decision message should be "Enter a valid email address (for example, you@example.com)."

  Scenario: Username is accepted
    Given the email form has been submitted
    When email form is evaluated with input "wizard"
    Then the email decision should continue
    And the email decision email should be "wizard"
    And the email decision should request rerun

  Scenario: Valid email is normalized and accepted
    Given the email form has been submitted
    When email form is evaluated with input "  Test.User@Example.COM "
    Then the email decision should continue
    And the email decision email should be "test.user@example.com"
    And the email decision should request rerun
