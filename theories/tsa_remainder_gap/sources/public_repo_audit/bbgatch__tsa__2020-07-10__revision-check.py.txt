import pandas as pd
from datetime import datetime, timedelta

# Getting today's and yesterday's dates for filenames.
today = datetime.today().strftime('%Y-%m-%d')
yesterday = (datetime.today() - timedelta(1)).strftime('%Y-%m-%d')

# Read in two latest data files.
data_today = pd.read_csv("tsa_" + today + ".csv")
data_yesterday = pd.read_csv("tsa_" + yesterday + ".csv")

# Calculate difference in today's and yesterday's traveler counts.
diff = data_today["2020"] - data_yesterday["2020"]

# Drop NaNs created from extra day in data_today.
diff = diff.dropna()

# Sum differences.
sum(diff)

