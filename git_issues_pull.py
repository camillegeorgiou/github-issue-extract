import requests
import csv

# GitHub Personal Access Token
token = '{{Git Token}}'
headers = {'Authorization': f'token {token}'}

# Base URL for fetching issues
base_url = '{{https://url}}'

# Parameters for API request
params = {
    'state': 'open',
    'per_page': 100  # Max per page allowed by GitHub
}

# Initialise empty list to hold fetched issues
all_issues = []

# Fetch issues from GitHub API with pagination
while True:
    response = requests.get(base_url, headers=headers, params=params)
    issues = response.json()
    all_issues.extend(issues)
    
    if 'next' in response.links.keys():
        base_url = response.links['next']['url']  # URL for the next page
    else:
        break  # Exit loop if no more pages

# Filter for issues containing specific terms in the title or body, accomodate handling None types
filtered_issues = [
    issue for issue in all_issues 
    if '{{search term}}'.lower() in (issue['title'] + (issue.get('body') or '')).lower()
]

# Define CSV file path and headers
csv_file = 'filtered_issues.csv'
csv_columns = ['Issue Number', 'Title', 'URL', 'State', 'Created At', 'Body']

# Write filtered issues to CSV file
with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.DictWriter(file, fieldnames=csv_columns)
    writer.writeheader()
    for issue in filtered_issues:
        writer.writerow({
            'Issue Number': issue['number'],
            'Title': issue['title'],
            'URL': issue['html_url'],
            'State': issue['state'],
            'Created At': issue['created_at'],
            'Body': issue['body']

        })

print(f'Data has been written to {csv_file}')
print(f"Status Code: {response.status_code}")
print(f"Total issues fetched: {len(all_issues)}")
print(f"Total issues containing search term: {len(filtered_issues)}")
