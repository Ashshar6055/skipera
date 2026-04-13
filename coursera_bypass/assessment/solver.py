import time

import requests

from .. import config
from .types import QUESTION_TYPE_MAP, MODEL_MAP, deep_blank_model, WHITELISTED_QUESTION_TYPES
from ..config import GRAPHQL_URL
from .queries import (GET_STATE_QUERY, SAVE_RESPONSES_QUERY, SUBMIT_DRAFT_QUERY,
                      GRADING_STATUS_QUERY, INITIATE_ATTEMPT_QUERY)
from loguru import logger
from ..llm.connector import PerplexityConnector, GeminiConnector


class GradedSolver(object):
    def __init__(self, session: requests.Session, course_id: str, item_id: str):
        self.session: requests.Session = session
        self.course_id: str = course_id
        self.item_id: str = item_id
        self.attempt_id = None
        self.draft_id = None
        self.discarded_questions = []

    def solve(self) -> None:
        state = self.get_state()

        if state is None:
            logger.error("Assessment state could not be retrieved. Ensure you have access to this assignment.")
            return

        if state["allowedAction"] in ["START_NEW_ATTEMPT", "RESUME_DRAFT"]:
            if state["outcome"] is not None:
                if state["outcome"]["isPassed"]:
                    logger.debug("Already passed!")
                    return

            if state["allowedAction"] == "START_NEW_ATTEMPT":
                if state["attempts"]["attemptsRemaining"] == 0:
                    logger.error("No more attempts can be made!")
                    return

                if not self.initiate_attempt():
                    logger.error("Could not start an attempt. Please file an issue.")
                    return

            # Proceed to solve for both START_NEW_ATTEMPT and RESUME_DRAFT
            self.solve_assessment()

        else:
            logger.error(f"Something went wrong! Allowed action: {state['allowedAction']}. Please file an issue.")

    def solve_assessment(self) -> None:
        """
        Main logic for retrieving questions, getting LLM answers, and submitting.
        """
        if config.PERPLEXITY_API_KEY:
            connector = PerplexityConnector()
        elif config.GEMINI_API_KEY:
            connector = GeminiConnector()
        else:
            raise RuntimeError("No API Key specified.")

        questions = self.retrieve_questions()
        answers = connector.get_response(questions)

        if not self.save_responses(answers["responses"]):
            logger.error("Could not save responses. Please file an issue.")
        else:
            if not self.submit_draft():
                logger.error("Could not submit the assignment. Please file an issue.")
            else:
                logger.debug("Waiting 3 seconds for grading..")
                time.sleep(3)  # delay for grading process
                if not self.get_grade():
                    logger.error("Sorry! Could not pass the assignment, maybe use a better model.")

    def get_state(self) -> dict:
        """
        Retrieves the current state of the assessment.
        """
        response = self.session.post(url=GRAPHQL_URL, params={
            "opname": "QueryState"
        }, json={
            "operationName": "QueryState",
            "variables": {
                "courseId": self.course_id,
                "itemId": self.item_id
            },
            "query": GET_STATE_QUERY
        })
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch assessment state: HTTP {response.status_code}")
            return None
            
        res = response.json()
        
        if "errors" in res:
            logger.error(f"GraphQL Errors encountered for item {self.item_id}:")
            for error in res["errors"]:
                logger.error(f"  - {error.get('message')}")
            return None

        state = res.get("data", {}).get("SubmissionState", {}).get("queryState")
        
        if state is None:
            logger.debug(f"SubmissionState.queryState returned null for item {self.item_id}")
            logger.trace(f"Full response: {res}")
            
        return state

    def initiate_attempt(self) -> bool:
        """
        Initiates a new attempt for the assessment.
        """
        res = self.session.post(url=GRAPHQL_URL, params={
            "opname": "Submission_StartAttempt"
        }, json={
            "operationName": "Submission_StartAttempt",
            "variables": {
                "courseId": self.course_id,
                "itemId": self.item_id
            },
            "query": INITIATE_ATTEMPT_QUERY
        })

        if "Submission_StartAttemptSuccess" in res.text:
            return True
        return False

    def retrieve_questions(self) -> dict:
        """
        Retrieves the questions for the particular attempt
        which are to be sent to the LLM Connector.
        """
        state = self.get_state()
        if state is None or state.get("attempts") is None or state["attempts"].get("inProgressAttempt") is None:
            logger.error(f"No in-progress attempt found for item {self.item_id}")
            return {}

        draft = state["attempts"]["inProgressAttempt"]
        self.draft_id = draft["id"] # attemptId
        self.attempt_id = draft["draft"]["id"] # submissionId
        questions = draft["draft"]["parts"]
        questions_formatted = {}
        for question in questions:
            
            type_name = question.get("__typename")
            if not type_name in QUESTION_TYPE_MAP:  # discard unknown question types
                continue

            resp_id = question["partId"]

            if not type_name in WHITELISTED_QUESTION_TYPES:
                self.discarded_questions.append({
                    "questionId": resp_id,
                    "questionType": QUESTION_TYPE_MAP[type_name][1],
                    "questionResponse": {
                        QUESTION_TYPE_MAP[type_name][0]:
                        deep_blank_model(MODEL_MAP[type_name])
                    }
                })
                continue

            options = []
            for option in question["questionSchema"]["options"]:
                options.append({
                    "option_id": option["optionId"],
                    "value": option["display"]["cmlValue"]
                })

            questions_formatted[resp_id] = {"Question": question["questionSchema"]["prompt"]["cmlValue"],
                                            "Options": options,
                                            "Type": "Single-Choice" if
                                            type_name == "Submission_MultipleChoiceQuestion"
                                            else "Multi-Choice"}
        return questions_formatted

    def save_responses(self, answers: dict) -> bool:
        """
        Saves the responses for the assessment to the draft.
        """
        answer_responses = []

        for answer in answers:
            answer_responses.append({
                "questionId": answer["question_id"],
                "questionType": "MULTIPLE_CHOICE" if answer["type"] == "Single" else "CHECKBOX",
                "questionResponse": {
                    "multipleChoiceResponse" if answer["type"] == "Single" else "checkboxResponse": {
                        "chosen": answer["option_id"][0] if answer["type"] == "Single" else answer["option_id"]
                    }
                }
            })

        res = self.session.post(url=GRAPHQL_URL, params={
            "opname": "Submission_SaveResponses"
        }, json={
            "operationName": "Submission_SaveResponses",
            "variables": {
                "input": {
                    "courseId": self.course_id,
                    "itemId": self.item_id,
                    "attemptId": self.draft_id,
                    "questionResponses": [*answer_responses, *self.discarded_questions]
                }
            },
            "query": SAVE_RESPONSES_QUERY
        })

        if "Submission_SaveResponsesSuccess" in res.text:
            return True

        logger.error(f"Failed to save responses for item {self.item_id}:")
        try:
            errors = res.json().get("data", {}).get("Submission_SaveResponses", {}).get("errors", [])
            for error in errors:
                logger.error(f"  - {error.get('errorCode')}: {error.get('message', '')}")
        except Exception:
            logger.error(res.text[:500])
        
        return False

    def submit_draft(self) -> bool:
        """
        Submits the draft for evaluation after the submission is saved.
        """
        res = self.session.post(url=GRAPHQL_URL, params={
            "opname": "Submission_SubmitLatestDraft"
        }, json={
            "operationName": "Submission_SubmitLatestDraft",
            "query": SUBMIT_DRAFT_QUERY,
            "variables": {
                "input": {
                    "courseId": self.course_id,
                    "itemId": self.item_id,
                    "submissionId": self.attempt_id
                }
            }
        })

        if "Submission_SubmitLatestDraftSuccess" in res.text:
            return True
            
        logger.error(f"Failed to submit assignment for item {self.item_id}:")
        try:
            errors = res.json().get("data", {}).get("Submission_SubmitLatestDraft", {}).get("errors", [])
            for error in errors:
                logger.error(f"  - {error.get('errorCode')}: {error.get('message', '')}")
        except Exception:
            logger.error(res.text[:500])
            
        return False

    def get_grade(self) -> bool:
        """
        Retrieves the outcome for the submitted assignment, polling until graded.
        """
        max_retries = 5
        for attempt in range(max_retries):
            res = self.session.post(url=GRAPHQL_URL, params={
                "opname": "QueryState"
            }, json={
                "operationName": "QueryState",
                "query": GET_STATE_QUERY,
                "variables": {
                    "courseId": self.course_id,
                    "itemId": self.item_id
                }
            }).json()

            state = res.get("data", {}).get("SubmissionState", {}).get("queryState", {})
            outcome = state.get("outcome")

            if outcome is not None:
                logger.debug(f"Achieved {outcome['earnedGrade']} grade. Passed? {outcome['isPassed']}")
                return outcome['isPassed']
            
            grading_status = state.get("gradingStatus")
            logger.debug(f"Grading in progress... Status: {grading_status} (Attempt {attempt+1}/{max_retries})")
            time.sleep(5)

        logger.debug("Outcome is still None after polling.")
        return False
