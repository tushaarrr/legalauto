Feature: The approval gate

  Two promises this firm's intake tool makes, in the language of the people who
  have to trust it:

    1. Nothing reaches the CRM until a human has reviewed and approved it.
    2. The conflict verdict that gets filed is the firm's own screen — re-run on
       whatever the reviewer finally typed, never the one the browser sent back.

  Background:
    Given an intake has been processed and screened "No conflict found"

  Scenario: The conflict screen is re-run on the reviewer's corrections
    When the reviewer corrects the client name to a party the firm has opposed
    Then the verdict on screen still reads "No conflict found"
    When the reviewer approves the intake
    Then the filed record reads "Conflict of interest — do not accept without review"

  Scenario: Nothing is filed until a human approves
    When the reviewer edits the intake without approving it
    Then nothing has been written to the CRM
    When the reviewer approves the intake
    Then the record is confirmed saved to the CRM
    And exactly one write reached the CRM

  Scenario: A drafted reply can be copied but never sent
    When the reviewer approves the intake
    Then the reply can be copied
    And there is no way to send it
