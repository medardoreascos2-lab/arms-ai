class StrategyCertificationReportV1:
    """
    Genera reporte de certificación
    de estrategia ARMS AI.
    """

    def __init__(self):
        self.results = []

    def add_result(
        self,
        scenario: str,
        passed: bool,
    ):
        self.results.append(
            {
                "scenario": scenario,
                "passed": passed,
            }
        )

    def summary(self):

        total = len(self.results)

        passed = sum(
            1
            for r in self.results
            if r["passed"]
        )

        failed = total - passed

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "certified": (
                failed == 0
                and total > 0
            ),
        }


    def show(self):

        print(
            "================================="
        )

        print(
            "ARMS AI STRATEGY CERTIFICATION"
        )

        print(
            "================================="
        )

        for result in self.results:

            status = (
                "PASS"
                if result["passed"]
                else "FAIL"
            )

            print(
                f"{result['scenario']:<25}"
                f"{status}"
            )

        print(
            "---------------------------------"
        )

        summary = self.summary()

        print(
            "Total Tests:",
            summary["total"]
        )

        print(
            "Passed:",
            summary["passed"]
        )

        print(
            "Failed:",
            summary["failed"]
        )

        print(
            "Certification:",
            (
                "APPROVED"
                if summary["certified"]
                else "REJECTED"
            )
        )
