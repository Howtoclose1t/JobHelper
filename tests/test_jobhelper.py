import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from jobhelper import DEMO_CHECK, Application, Tracker, duplicate_candidates, match_skills, search_demo


class JobHelperTests(unittest.TestCase):
    def test_match_explains_hits_and_respects_skill_boundaries(self):
        result = match_skills("SQL, sql, C, C++, AWS", "Use PostgreSQL, C++, and Amazon Web Services.")
        self.assertEqual(result.matched, ("C++", "AWS"))
        self.assertEqual(result.unmentioned, ("SQL", "C"))
        self.assertEqual(result.percent, 50)

    def test_sample_search_combines_filters(self):
        results = search_demo("StepStone", "data engineer", "berlin")
        self.assertEqual([posting.title for posting in results], ["Junior Data Engineer"])
        self.assertEqual(search_demo("StepStone", "data engineer", "Munich"), [])
        self.assertEqual(len(search_demo("All sources", "", "")), 6)

    def test_duplicate_requires_same_company_and_core_title(self):
        records = [Application(1, "Northstar Example Labs", "Data Engineer", "", "Applied", "2026-01-15"),
                   Application(2, "Other Example Labs", "Data Engineer", "", "Saved", "2026-01-15")]
        self.assertEqual(duplicate_candidates(*DEMO_CHECK[:2], records), records[:1])
        self.assertEqual(duplicate_candidates("Northstar Example Labs", "Data Scientist", records), [])

    def test_tracker_round_trip_and_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tracker.sqlite3"
            tracker = Tracker(path)
            with self.assertRaises(ValueError):
                tracker.add(" ", "Data Engineer", "Python")
            tracker.add(*DEMO_CHECK)
            record, = tracker.list()
            tracker.set_status(record.id, "Interview")
            self.assertEqual(Tracker(path).list()[0].status, "Interview")
            with self.assertRaises(ValueError):
                tracker.set_status(record.id, "Unknown")

    def test_demo_search_to_tracker(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "60%")
        self.assertTrue(app.warning)
        self.assertTrue(app.button(key="demo_save").disabled)
        app.text_input[0].set_value("machine learning")
        app.text_input[1].set_value("Munich")
        next(button for button in app.button if button.label == "Search sample jobs").click().run()
        app.button(key="sample_0").click().run()
        self.assertEqual(app.text_input(key="demo_title").value, "Machine Learning Engineer")
        app.button(key="demo_save").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="demo_record").value, 3)
        app.selectbox(key="demo_status_3").set_value("Applied").run()
        app.button(key="demo_update").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.demo_records[0].status, "Applied")
