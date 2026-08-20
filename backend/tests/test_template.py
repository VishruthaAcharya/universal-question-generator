import pandas as pd
from app.services.template import read_template_schema

def test_template_read(tmp_path):
    p = tmp_path / "template.csv"
    cols = ["Question", "Topic", "Starter Code", "Correct Answer"]
    pd.DataFrame(columns=cols).to_csv(p, index=False)
    schema = read_template_schema(str(p))
    assert schema["columns"] == cols
    assert schema["column_schema"][0]["normalized_name"] == "question"
    assert schema["column_schema"][0]["required"] is True
