import click
import requests
from .config import fetch_browser_cookies, CONFIG_FILE, DEFAULT_CONFIG, BASE_URL, HEADERS, COOKIES
import json
from loguru import logger
from .assessment.solver import GradedSolver
from .watcher.watch import Watcher


class CourseraBypass(object):
    def __init__(self, course: str, llm: bool):
        self.user_id = None
        self.course_id = None
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.cookies.update(COOKIES)
        self.course = course
        self.llm = llm
        if not self.get_userid():
            self.refresh_cookies()
            if not self.get_userid():
                logger.error("Cookies are invalid. Log into Coursera in your browser, close it, and retry.")
                raise SystemExit

    def refresh_cookies(self):
        logger.warning("Session expired — re-fetching cookies from browser...")
        cookies = fetch_browser_cookies()
        if not cookies:
            return
        self.session.cookies.clear()
        self.session.cookies.update(cookies)
        cfg = json.loads(CONFIG_FILE.read_text()) if CONFIG_FILE.exists() else DEFAULT_CONFIG.copy()
        cfg["cookies"] = cookies
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

    def get_userid(self) -> bool:
        r = self.session.get(self.base_url + "adminUserPermissions.v1?q=my").json()
        try:
            self.user_id = r["elements"][0]["id"]
            logger.info("User ID: " + self.user_id)
        except KeyError:
            if r.get("errorCode"):
                logger.error("Error Encountered: " + r["errorCode"])
            return False
        return True

    def get_course(self) -> None:
        r = self.session.get(self.base_url + f"onDemandCourseMaterials.v2/", params={
            "q": "slug",
            "slug": self.course,
            "includes": "modules,lessons,passableItemGroups,passableItemGroupChoices,passableLessonElements,items,"
                        "tracks,gradePolicy,gradingParameters,embeddedContentMapping",
            "fields": "moduleIds,onDemandCourseMaterialModules.v1(name,slug,description,timeCommitment,lessonIds,"
                      "optional,learningObjectives),onDemandCourseMaterialLessons.v1(name,slug,timeCommitment,"
                      "elementIds,optional,trackId),onDemandCourseMaterialPassableItemGroups.v1(requiredPassedCount,"
                      "passableItemGroupChoiceIds,trackId),onDemandCourseMaterialPassableItemGroupChoices.v1(name,"
                      "description,itemIds),onDemandCourseMaterialPassableLessonElements.v1(gradingWeight,"
                      "isRequiredForPassing),onDemandCourseMaterialItems.v2(name,originalName,slug,timeCommitment,"
                      "contentSummary,isLocked,lockableByItem,itemLockedReasonCode,trackId,lockedStatus,itemLockSummary,"
                      "customDisplayTypenameOverride),onDemandCourseMaterialTracks.v1(passablesCount),"
                      "onDemandGradingParameters.v1(gradedAssignmentGroups),"
                      "contentAtomRelations.v1(embeddedContentSourceCourseId,subContainerId)",
            "showLockedItems": True
        })

        if r.status_code != 200:
            logger.error("Please check if you are enrolled in the course!")
            raise SystemExit

        r = r.json()

        self.course_id = r["elements"][0]["id"]
        module_ids = r["elements"][0]["moduleIds"]

        # Create lookups for faster access
        modules_lookup = {v["id"]: v for v in r["linked"]["onDemandCourseMaterialModules.v1"]}
        lessons_lookup = {v["id"]: v for v in r["linked"]["onDemandCourseMaterialLessons.v1"]}
        items_lookup = {v["id"]: v for v in r["linked"]["onDemandCourseMaterialItems.v2"]}

        logger.info(f"Course ID: {self.course_id}")
        logger.info(f"Number of Modules: {len(module_ids)}")
        logger.debug("Processing course materials sequentially..")

        for module_id in module_ids:
            module = modules_lookup.get(module_id)
            if not module:
                continue
            
            logger.info(f"Module: {module['name']}")
            for lesson_id in module.get("lessonIds", []):
                lesson = lessons_lookup.get(lesson_id)
                if not lesson:
                    continue
                
                logger.info(f"  Lesson: {lesson['name']}")
                for item_id in lesson.get("elementIds", []):
                    # Handle 'item~' prefix if present in the elementalIds
                    actual_id = item_id.split("~")[-1] if "~" in item_id else item_id
                    item = items_lookup.get(actual_id)
                    
                    if not item:
                        continue
                    
                    if item.get("isLocked"):
                        logger.warning(f"    [LOCKED] Item: {item['name']} (Reason: {item.get('itemLockedReasonCode', 'Unknown')})")
                        continue

                    self.process_item(item)

    def process_item(self, item: dict) -> None:
        """
        Processes a single course item based on its type.
        """
        type_name = item["contentSummary"]["typeName"]
        item_id = item["id"]
        item_name = item["name"]

        if type_name == "lecture":
            logger.info(f"    Watching Video: {item_name}")
            self.watch_item(item, self.get_video_metadata(item_id))
        elif type_name == "supplement":
            logger.info(f"    Reading: {item_name}")
            self.complete_item(item_id)
        elif type_name == "ungradedAssignment":
            # Always attempt ungraded assignments — they're required to unlock next modules
            logger.info(f"    Solving ungraded assessment: {item_name}")
            solver = GradedSolver(self.session, self.course_id, item_id)
            solver.solve()
        elif type_name == "staffGraded":
            if self.llm:
                logger.info(f"    Attempting to solve graded assessment: {item_name}")
                solver = GradedSolver(self.session, self.course_id, item_id)
                solver.solve()
            else:
                logger.info(f"    Skipping graded assessment (LLM disabled): {item_name}")
        else:
            logger.debug(f"    Skipping unknown item type '{type_name}': {item_name}")

    def get_video_metadata(self, item_id: str) -> dict:
        r = self.session.get(self.base_url + f"onDemandLectureVideos.v1/{self.course_id}~{item_id}", params={
            "includes": "video",
            "fields": "disableSkippingForward,startMs,endMs"
        }).json()

        return {"can_skip": not r["elements"][0]["disableSkippingForward"],
                "tracking_id": r["linked"]["onDemandVideos.v1"][0]["id"]}

    def watch_item(self, item: dict, metadata: dict) -> None:
        watcher = Watcher(self.session, item, metadata, self.user_id, self.course, self.course_id)
        watcher.watch_item()

    def complete_item(self, item_id) -> None:
        """
        Marks a supplement as completed.
        """
        r = self.session.post(self.base_url + "onDemandSupplementCompletions.v1", json={
            "courseId": self.course_id,
            "itemId": item_id,
            "userId": int(self.user_id)
        })
        if "Completed" not in r.text:
            logger.debug(f"Supplement completion failed for {item_id}: {r.status_code} {r.text[:100]}")


@logger.catch
@click.command()
@click.argument('slug')
@click.option('--llm', is_flag=True, help="Whether to use an LLM to solve graded assignments.")
def main(slug: str, llm: bool) -> None:
    bypass = CourseraBypass(slug, llm)
    bypass.get_course()


if __name__ == '__main__':
    main()
