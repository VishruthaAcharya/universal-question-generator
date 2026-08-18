import pandas as pd
from app.services.template import read_template, REQUIRED_COLUMNS

def test_template_read(tmp_path):
    p = tmp_path / "template.csv"
    pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(p, index=False)
    assert read_template(str(p)) == REQUIRED_COLUMNS
