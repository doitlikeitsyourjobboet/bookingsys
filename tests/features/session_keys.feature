Feature: Session State Keys
  Prevent widget/session key collisions that crash Streamlit.

  Scenario: Auth keys are distinct and namespaced
    Then auth email key should be "auth_email"
    And auth email input key should be "auth_email_input"
    And auth keys should be distinct
    And auth keys should be namespaced
