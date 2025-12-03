import os
import subprocess
import json
import unittest
import re
import shutil
from collections.abc import Callable

from pathlib import Path
from pydantic import BaseModel

BASELINE_PATH = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/baselines.json")
INPUT_PATH = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/sendfiles")
OUTPUT_PATH = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/recvfiles")
LOG_PATH = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/logs")
NETWORK_PY = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/network.py")
JSON_FILE = Path("/home/malinkyzubr/Desktop/ECE463/463lab4/01.json")


class NetworkTestResults(BaseModel):
    bytes: int
    time: float

TO_TEST = [0]

def extract_baselines(baseline_filepath: Path) -> dict[str, dict[int, NetworkTestResults]]:
    return_value: dict[str, dict[int, NetworkTestResults]] = dict()
    with open(baseline_filepath) as f:
        baselines = json.load(f)
        for filename, test_results in baselines.items():
            reformatted_test_results: dict[int, NetworkTestResults] = dict()
            for error_rate, result in test_results.items():
                reformatted_test_results[int(error_rate)] = NetworkTestResults(**result)

            return_value[filename] = reformatted_test_results
    return return_value


class TestNetworkFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline_values = extract_baselines(BASELINE_PATH)
        assert len(cls.baseline_values) > 0, "No baselines provided"
        assert len(set(filter(lambda x: ".txt" in x, os.listdir(INPUT_PATH))).difference(
            set(cls.baseline_values.keys()))) == 0, "Baselines dont match input files"

        cls.bytes_pattern = r"Total bytes sent\s*=\s*(\d+)"
        cls.time_pattern = r"Total time of transfer\s*=\s*([\d.]+)"

    @classmethod
    def _make_test_cls(cls, error_rate: int) -> Callable:
        def test(self):
            cls._test_percentage(error_rate)

        return test

    @classmethod
    def _run_individual_file(cls, input_file: Path, output_dir: Path, error_rate: int) -> tuple[
        NetworkTestResults, bool]:
        assert input_file.suffix == ".txt", f"Suffix for file {input_file.name} must be .txt"
        result: subprocess.CompletedProcess[str] = subprocess.run(
            f"python3 {NETWORK_PY} {JSON_FILE} {INPUT_PATH.resolve()}/{input_file.name} {output_dir.resolve()}/{input_file.name} {error_rate}".split(
                " "),
            capture_output=True, text=True, check=True)
        outputted_text = result.stdout

        is_correct: bool = "SUCCESS" in outputted_text
        test_result: NetworkTestResults = NetworkTestResults(
            bytes=int(re.search(cls.bytes_pattern, outputted_text).group(1)),
            time=float(re.search(cls.time_pattern, outputted_text).group(1))
        )

        return test_result, is_correct

    @classmethod
    def _test_percentage(cls, error_rate: int):
        output_filepath_root: Path = OUTPUT_PATH / f"{error_rate}/"
        os.mkdir(output_filepath_root)

        for input_filename, test_baseline in cls.baseline_values.items():
            output_filepath: Path = output_filepath_root / input_filename.replace(".txt", "")
            os.mkdir(output_filepath)
            result, correct = cls._run_individual_file(Path(input_filename), output_filepath, error_rate)
            shutil.copytree(LOG_PATH, output_filepath, dirs_exist_ok=True)
            assert correct == True, f"INCORRECT OUTPUT: {input_filename}, PERCENT DROP: {error_rate}"
            assert result.bytes <= test_baseline[
                error_rate].bytes, f"TOO MANY BYTES: Bytes sent by implementation for {input_filename} at {error_rate}% error rate exceeded baselines. Computed: {result.bytes} Maximum: {test_baseline.bytes}"
            assert result.time <= test_baseline[
                error_rate].time * 1.25, f"TOO LONG: Total time spent by implementation for {input_filename} at {error_rate}% exceeded baselines. Completed: {result.time} Maximum: {test_baseline.time * 1.25}"


# AFTER the class definition
def _attach_dynamic_tests():
    baselines = extract_baselines(BASELINE_PATH)
    baseline_percentages = list(list(baselines.values())[0].keys())

    for pct in baseline_percentages:
        if pct in TO_TEST:
            setattr(TestNetworkFlow, f"test_error_rate{pct}", TestNetworkFlow._make_test_cls(pct))


_attach_dynamic_tests()

if __name__ == "__main__":
    unittest.main()
