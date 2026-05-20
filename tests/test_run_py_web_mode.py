import unittest


class RunPyWebModeExpectationTests(unittest.TestCase):
    def test_run_py_contains_web_branch(self):
        with open("run.py", "r", encoding="utf-8") as handle:
            source = handle.read()

        self.assertIn("elif _RUN_TYPE == 'WEB':", source)
        self.assertIn('uvicorn.run(app, host="127.0.0.1", port=5000, reload=False, workers=1)', source)


if __name__ == "__main__":
    unittest.main()
