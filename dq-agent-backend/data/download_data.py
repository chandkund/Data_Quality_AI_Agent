import pandas as pd

URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"

columns = [
    "age", "workclass", "fnlwgt", "education", "education_num",
    "marital_status", "occupation", "relationship", "race", "sex",
    "capital_gain", "capital_loss", "hours_per_week", "native_country", "income",
]

# The raw file has no header row, so we add one
df = pd.read_csv(URL, names=columns, skipinitialspace=True)

# Keep it small (stays under the 5 MB / 50,000 row limits)
df = df.sample(5000, random_state=42).reset_index(drop=True)

df.to_csv("clean.csv", index=False)
print("Saved clean.csv:", df.shape)