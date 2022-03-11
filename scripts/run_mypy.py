"""
Invokes mypy and compare the reults with files in /pymc except tests
and a list of files that are expected to pass without mypy errors.

Exit code 0 indicates that there are no unexpected results.

Usage
-----
python scripts/run_mypy.py [--verbose]
"""
import argparse
import importlib
import os
import pathlib
import subprocess
import sys

from typing import Iterator

import pandas

DP_ROOT = pathlib.Path(__file__).absolute().parent.parent
PASSING = """
pymc/__init__.py
pymc/backends/__init__.py
pymc/backends/arviz.py
pymc/backends/base.py
pymc/backends/ndarray.py
pymc/backends/report.py
pymc/blocking.py
pymc/data.py
pymc/distributions/__init__.py
pymc/distributions/bound.py
pymc/distributions/censored.py
pymc/distributions/discrete.py
pymc/distributions/shape_utils.py
pymc/distributions/simulator.py
pymc/distributions/timeseries.py
pymc/distributions/transforms.py
pymc/exceptions.py
pymc/func_utils.py
pymc/gp/__init__.py
pymc/gp/cov.py
pymc/gp/gp.py
pymc/gp/mean.py
pymc/gp/util.py
pymc/math.py
pymc/ode/__init__.py
pymc/ode/ode.py
pymc/ode/utils.py
pymc/parallel_sampling.py
pymc/plots/__init__.py
pymc/smc/__init__.py
pymc/smc/sample_smc.py
pymc/stats/__init__.py
pymc/step_methods/__init__.py
pymc/step_methods/compound.py
pymc/step_methods/elliptical_slice.py
pymc/step_methods/hmc/__init__.py
pymc/step_methods/hmc/base_hmc.py
pymc/step_methods/hmc/integration.py
pymc/step_methods/hmc/quadpotential.py
pymc/step_methods/slicer.py
pymc/step_methods/step_sizes.py
pymc/tuning/__init__.py
pymc/tuning/scaling.py
pymc/tuning/starting.py
pymc/util.py
pymc/variational/__init__.py
pymc/variational/callbacks.py
pymc/variational/inference.py
pymc/variational/operators.py
pymc/variational/stein.py
pymc/variational/test_functions.py
pymc/variational/updates.py
pymc/vartypes.py
"""


def enforce_pep561(module_name):
    try:
        module = importlib.import_module(module_name)
        fp = pathlib.Path(module.__path__[0], "py.typed")
        if not fp.exists():
            fp.touch()
    except ModuleNotFoundError:
        print(f"Can't enforce PEP 561 for {module_name} because it is not installed.")
    return


def mypy_to_pandas(input_lines: Iterator[str]) -> pandas.DataFrame:
    """Reformats mypy output with error codes to a DataFrame.

    Adapted from: https://gist.github.com/michaelosthege/24d0703e5f37850c9e5679f69598930a
    """
    current_section = None
    data = {
        "file": [],
        "line": [],
        "type": [],
        "section": [],
        "message": [],
    }
    for line in input_lines:
        line = line.strip()
        elems = line.split(":")
        if len(elems) < 3:
            continue
        try:
            file, lineno, message_type, *_ = elems[0:3]
            message_type = message_type.strip()
            if message_type == "error":
                current_section = line.split("  [")[-1][:-1]
            message = line.replace(f"{file}:{lineno}: {message_type}: ", "").replace(
                f"  [{current_section}]", ""
            )
            data["file"].append(file)
            data["line"].append(lineno)
            data["type"].append(message_type)
            data["section"].append(current_section)
            data["message"].append(message)
        except Exception as ex:
            print(elems)
            print(ex)
    return pandas.DataFrame(data=data).set_index(["file", "line"])


def check_no_unexpected_results(mypy_lines: Iterator[str]):
    """Compares mypy results with list of known PASSING files.

    Exits the process with non-zero exit code upon unexpected results.
    """
    df = mypy_to_pandas(mypy_lines)

    all_files = {
        str(fp).replace(str(DP_ROOT), "").strip(os.sep).replace(os.sep, "/")
        for fp in DP_ROOT.glob("pymc/**/*.py")
        if not "tests" in str(fp)
    }
    failing = set(df.reset_index().file.str.replace(os.sep, "/", regex=False))
    if not failing.issubset(all_files):
        raise Exception(
            "Mypy should have ignored these files:\n"
            + "\n".join(sorted(map(str, failing - all_files)))
        )
    passing = all_files - failing
    expected_passing = set(PASSING.strip().split("\n")) - {""}
    unexpected_failing = expected_passing - passing
    unexpected_passing = passing - expected_passing

    if not unexpected_failing:
        print(f"{len(passing)}/{len(all_files)} files pass as expected.")
    else:
        print(f"{len(unexpected_failing)} files unexpectedly failed:")
        print("\n".join(sorted(map(str, unexpected_failing))))
        sys.exit(1)

    if unexpected_passing:
        print(f"{len(unexpected_passing)} files unexpectedly passed the type checks:")
        print("\n".join(sorted(map(str, unexpected_passing))))
        print("This is good news! Go to scripts/run-mypy.py and add them to the list.")
        sys.exit(1)
    return


if __name__ == "__main__":
    # Enforce PEP 561 for some important dependencies that
    # have relevant type hints but don't tell that to mypy.
    enforce_pep561("aesara")
    enforce_pep561("aeppl")

    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--verbose", action="count", default=0, help="Pass this to print mypy output."
    )
    args, _ = parser.parse_known_args()

    cp = subprocess.run(
        ["mypy", "--exclude", "pymc/tests", "pymc"],
        capture_output=True,
    )
    output = cp.stdout.decode()
    if args.verbose:
        print(output)
    check_no_unexpected_results(output.split("\n"))
    sys.exit(0)
