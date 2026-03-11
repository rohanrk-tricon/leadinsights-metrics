import pandas as pd


class DataLoader:

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = None

    def load(self):
        df = pd.read_csv(self.csv_path)

        # normalize column names
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        self.df = df
        return df

    def get_dataframe(self):
        if self.df is None:
            raise ValueError("Data not loaded yet")
        return self.df