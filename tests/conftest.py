import sys
import shutil
from pathlib import Path
import pytest

# Ensure repo root on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session", autouse=True)
def generate_bin_outputs_once():
    """Run the bin generation step once per test session and copy outputs to Outputs/.

    This fixture calls `tools.generate_bins_fromexcel.main()` in a safe way
    (temporarily replacing sys.argv), then copies generated files from the
    Baselines locations used by the generator into `Door TestCases/BinPacking/Outputs`.
    """
    try:
        # import here to avoid import-time work; tools module expects repo on sys.path
        import tools.BaseLines.generate_bins_fromexcel as gen

        # destination outputs to pass to generator
        out_dxf = REPO_ROOT / "Door TestCases" / "BinPacking" / "Outputs" / "dxf"
        out_json = REPO_ROOT / "Door TestCases" / "BinPacking" / "Outputs" / "json"

        # ensure clean outputs dirs
        for p in (out_dxf, out_json):
            if p.exists():
                for f in p.iterdir():
                    try:
                        if f.is_file():
                            f.unlink()
                        else:
                            shutil.rmtree(f)
                    except Exception:
                        pass
            else:
                p.mkdir(parents=True, exist_ok=True)

        # run the generator passing dest paths so it writes directly into Outputs
        old_argv = sys.argv[:]  # save pytest args
        sys.argv[:] = [old_argv[0],
                       "--dest-dxf", str(out_dxf),
                       "--dest-json", str(out_json)]
        try:
            gen.main()
        finally:
            sys.argv[:] = old_argv

    except Exception as e:
        # If generation fails, raise to fail the test session early with a clear message
        raise RuntimeError(f"Pre-test bin generation failed: {e}")

    yield
