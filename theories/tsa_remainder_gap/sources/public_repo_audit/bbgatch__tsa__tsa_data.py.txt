import pull_tsa_data as tsa

url = "https://www.tsa.gov/coronavirus/passenger-throughput"

# Pull data from URL. Data is now split onto two pages. The '?page=1' addition
# accesses the second page.
page_0 = tsa.pull_tsa_data(url)
page_1 = tsa.pull_tsa_data(url + '?page=1')

df = page_0.append(page_1)

# Sorting by Date.
df = df.sort_values(by = 'Date')

# Save dataframe as CSV.
df.to_csv("tsa.csv", index = False)