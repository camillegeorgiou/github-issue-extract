import requests
import subprocess
import json
from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from elasticsearch.helpers import BulkIndexError

# GitHub Personal Access Token - MODIFY - YOU NEED A TOKEN WITH PROJECT PERMISSIONS
token = 'TOKEN'
headers = {'Authorization': f'token {token}'}

# Elasticsearch settings for Elastic Cloud - UPDATE. 
cloud_id = 'CLOUD_ID'
es_user = '`ES USER'
es_password = 'ES PASSWORD'
index_name = 'issues_github'
es = Elasticsearch(
    cloud_id=cloud_id,
    basic_auth=(es_user, es_password)
)

# GraphQL query to fetch project board data - MODIFY ORG and PROJECTV2 Number.
query = '''
query {
  organization(login: "ORG") {
    projectV2(number: 1) {
      title
      items(first: 100) {
        nodes {
          id
          content {
            ... on Issue {
              url
              title
              body
              comments(first: 100) {
                nodes {
                  body
                }
              }
              assignees(first: 10) {
                nodes {
                  login
                }
              }
            }
            ... on PullRequest {
              url
              title
              body
              comments(first: 100) {
                nodes {
                  body
                }
              }
              assignees(first: 10) {
                nodes {
                  login
                }
              }
            }
          }
          fieldValues(first: 20) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldTextValue {
                text
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldDateValue {
                date
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2FieldCommon {
                    name
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
'''

# Run the graph command
result = subprocess.run(['gh', 'api', 'graphql', '-f', f'query={query}'], capture_output=True, text=True)

# Validate success
if result.returncode != 0:
    print(f"Error: {result.stderr}")
    exit(1)

# Parse response
try:
    project_data = json.loads(result.stdout)
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    print("Raw output:")
    print(result.stdout)
    exit(1)

# Extract  project items
project = project_data['data']['organization']['projectV2']
items = project['items']['nodes']

# URL for fetching issues - i.e'https://api.github.com/repos/ORG/PROJECT/issues'
base_url = 'https://api.github.com/repos/PATH'

# Parameters for the API request
params = {
    'per_page': 100  # Max per page allowed by GitHub
}

# Initialize list
all_issues = []

# Fetch issues
while True:
    response = requests.get(base_url, headers=headers, params=params)
    issues = response.json()
    all_issues.extend(issues)
    
    if 'next' in response.links.keys():
        base_url = response.links['next']['url'] 
    else:
        break  

# Create a dictionary to map issue URLs to their details
issue_dict = {issue['html_url']: issue for issue in all_issues}

# Calculate age of the issue based on creation date
def calculate_age(created_at):
    if created_at:
        created_at_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
        age = (datetime.utcnow() - created_at_date).days
        return age
    return None

actions = []

for item in items:
    content = item['content']
    if content is None:
        continue
    url = content['url']
    title = content.get('title', '')
    description = content.get('body', '')
    comments = '\n'.join([comment['body'] for comment in content.get('comments', {}).get('nodes', [])])
    assignees = ', '.join([assignee['login'] for assignee in content.get('assignees', {}).get('nodes', [])])
    
    # Initialize field values
    priority = status = theme = product_area = date = 'Unknown'
    
    for fieldValue in item['fieldValues']['nodes']:
        field_name = fieldValue.get('field', {}).get('name', '')
        if fieldValue['__typename'] == 'ProjectV2ItemFieldTextValue' and field_name == 'Title':
            title = fieldValue['text']
        elif fieldValue['__typename'] == 'ProjectV2ItemFieldDateValue' and field_name == 'Date':
            date = fieldValue['date']
        elif fieldValue['__typename'] == 'ProjectV2ItemFieldSingleSelectValue':
            if field_name == 'Priority':
                priority = fieldValue['name']
            elif field_name == 'Status':
                status = fieldValue['name']
            elif field_name == 'Theme':
                theme = fieldValue['name']
            elif field_name == 'Product Area':
                product_area = fieldValue['name']
    
    issue_details = issue_dict.get(url, {})
    issue_number = issue_details.get('number', '')
    state = issue_details.get('state', '')
    created_at = issue_details.get('created_at', '')
    labels = ', '.join([label['name'] for label in issue_details.get('labels', [])])
    age = calculate_age(created_at)
    last_updated = datetime.utcnow().isoformat()

    # Fetch existing documents to check for changes
    existing_doc = es.get(index=index_name, id=item['id'], ignore=[404])
    
    if existing_doc['found']:
        existing_doc = existing_doc['_source']
        if (existing_doc.get('Title') == title and
            existing_doc.get('Description') == description and
            existing_doc.get('Comments') == comments and
            existing_doc.get('Assignees') == assignees and
            existing_doc.get('Priority') == priority and
            existing_doc.get('Status') == status and
            existing_doc.get('Theme') == theme and
            existing_doc.get('Product Area') == product_area and
            existing_doc.get('Date') == date and
            existing_doc.get('Issue Number') == issue_number and
            existing_doc.get('URL') == url and
            existing_doc.get('State') == state and
            existing_doc.get('Created At') == created_at and
            existing_doc.get('Labels') == labels and
            existing_doc.get('Age') == age):
            continue  # No changes detected, skip update
    
    action = {
        "_op_type": "update",
        "_index": index_name,
        "_id": item['id'],
        "doc_as_upsert": True,
        "doc": {
            "ID": item['id'],
            "Title": title,
            "Description": description,
            "Comments": comments,
            "Assignees": assignees,
            "Priority": priority,
            "Status": status,
            "Theme": theme,
            "Product Area": product_area,
            "Date": date,
            "Issue Number": issue_number,
            "URL": url,
            "State": state,
            "Created At": created_at,
            "Labels": labels,
            "Age": age,
            "Last Updated": last_updated
        }
    }
    actions.append(action)

# Bulk index the data to Elasticsearch
try:
    helpers.bulk(es, actions)
except BulkIndexError as e:
    print(f"Bulk indexing error: {e}")
    for error in e.errors:
        print(json.dumps(error, indent=2))

print(f'Data has been written to Elasticsearch')
print(f"Total issues fetched: {len(all_issues)}")
