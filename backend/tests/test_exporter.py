import io
import pandas as pd
from app.services.exporter import export_to_csv

def test_mapping_export():
    q = {
        "Question": "Q", "Topic": "T", "Starter Code": "print(1)", "Correct Answer": "1"
    }
    cols = ["Question", "Topic", "Starter Code", "Correct Answer"]
    buf = export_to_csv([q], cols)
    df = pd.read_csv(io.StringIO(buf.getvalue().decode("utf-8")))
    assert list(df.columns) == cols
    assert df.iloc[0]["Correct Answer"] == "1"
