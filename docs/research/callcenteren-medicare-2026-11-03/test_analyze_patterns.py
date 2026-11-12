"""Fictional boundary cases: enrollment evidence, boilerplate, and unknown roles."""
import unittest

from analyze_patterns import classify, enrollment_audit


class EnrollmentBoundaries(unittest.TestCase):
    def test_past_enrollment_does_not_become_active_sale(self):
        result = classify("I already enrolled in Medicare Part B last month. Can I make an appointment?")
        self.assertEqual(result["primary_type"], "basic_scheduling_or_intake")
        self.assertFalse(any(x["status"].startswith("insurance_") for x in result["enrollment_audit"]))

    def test_pet_daycare_is_not_insurance_enrollment(self):
        result = classify("Have you considered enrolling your dog in doggy daycare? Submit an application today.")
        self.assertFalse(result["primary_type"].startswith("insurance_enrollment"))

    def test_enrollee_id_is_not_enrollment(self):
        result = classify("What is the enrollee ID on your Medicare insurance card?")
        self.assertFalse(any(x["status"].startswith("insurance_") for x in result["enrollment_audit"]))

    def test_intent_is_not_completed_enrollment(self):
        result = classify("I want to enroll in a Medicare drug plan. Can you help me?")
        self.assertFalse(result["primary_type"].startswith("insurance_enrollment_completion"))
        self.assertFalse(any(x["status"] == "insurance_active_process_candidate" for x in result["enrollment_audit"]))

    def test_authorized_application_is_process_candidate(self):
        audit = enrollment_audit("I authorize you to submit my insurance enrollment application now.")
        self.assertIn("insurance_active_process_candidate", {x["status"] for x in audit})
        self.assertNotIn("insurance_completion_statement_candidate", {x["status"] for x in audit})

    def test_submission_language_is_candidate_not_verified_outcome(self):
        result = classify("We have submitted your Medicare enrollment application. Here is the confirmation.")
        self.assertEqual(result["primary_type"], "insurance_enrollment_completion_candidate")
        self.assertNotIn("verified_completed_enrollment", result)

    def test_provider_selection_is_not_plan_enrollment(self):
        result = classify("Call your Medicare insurance so they can enroll you into this dental office location.")
        self.assertFalse(result["primary_type"].startswith("insurance_enrollment"))

    def test_recording_existing_insurance_is_not_new_enrollment(self):
        result = classify("Let's start with the enrollment of your existing insurance information. What is your group number? I need to schedule an appointment for my child.")
        self.assertFalse(result["primary_type"].startswith("insurance_enrollment"))


class PassageBoundaries(unittest.TestCase):
    def test_menu_is_not_a_caller_billing_request(self):
        result = classify("For questions about bills, please press 1. I need to schedule an appointment.")
        self.assertEqual(result["primary_type"], "basic_scheduling_or_intake")
        self.assertNotIn("billing_payment_claim", result["type_scores"])

    def test_insurance_identity_does_not_mean_plan_advice(self):
        result = classify("What insurance do you have? Medicare. What is your member ID number?")
        self.assertNotIn("insurance_plan_choice_or_enrollment_inquiry", result["type_scores"])
        self.assertIn("insurance_identity_card_details", result["questions"])
        self.assertEqual(result["speaker_roles"], "unknown")

    def test_generic_check_and_teach_back_remain_distinct(self):
        generic = classify("Does that make sense? Do you have any other questions? Can you tell me in your own words?")
        # Count distinct support moves without asserting they explain or prove understanding.
        self.assertIn("teach_back_request", generic["explanations"])
        self.assertIn("generic_understanding_check", generic["explanations"])
        self.assertNotIn("reason_or_causal_language", generic["explanations"])

    def test_explanation_offset_points_to_exact_original(self):
        text = "Hello. You need to call your insurance because the amount depends on your benefits."
        result = classify(text)
        for spans in result["explanations"].values():
            for span in spans:
                self.assertIn("because", text[span["start"]:span["end"]])

    def test_leading_hold_promotion_is_not_a_price_request(self):
        text = "Our vision procedure costs far less than you think. How much screen time do you get? This is the office. How can I assist you today? I need to schedule an appointment. My insurance is Medicare."
        result = classify(text)
        self.assertEqual(result['primary_type'], 'basic_scheduling_or_intake')
        self.assertNotIn('price_estimate_or_affordability', result['type_scores'])

    def test_medicare_only_in_detected_hold_message_is_separate(self):
        text = "How may I help you? I have an eye problem. Let me put you on hold. We accept Medicare insurance. " + "Our office offers many services for your family. "*5 + "Thank you for holding. This is the nurse. What symptoms do you have?"
        result = classify(text)
        self.assertFalse(result['medicare_conversation_term_present'])

    def test_care_program_information_is_not_completed_enrollment(self):
        text = "How can I help you? I want information about your LIFE program for help with bathing and dressing. We can arrange a home visit and start enrollment later."
        result = classify(text)
        self.assertEqual(result['primary_type'], 'care_program_information_or_eligibility')
        self.assertFalse(result['primary_type'].startswith('insurance_enrollment'))

    def test_beneficiary_network_research_is_separate(self):
        text = "How may I help you? I am checking a Medicare plan for one of my beneficiaries. Do you accept this insurance?"
        self.assertEqual(classify(text)['primary_type'], 'third_party_plan_network_research_candidate')


if __name__ == "__main__":
    unittest.main()
