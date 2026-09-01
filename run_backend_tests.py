import sys
import pytest

sys.path.insert(0, 'backend')
exit_code = pytest.main(['backend/tests', '-o', 'pythonpath=backend'])
sys.exit(exit_code)
