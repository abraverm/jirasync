from jira import JIRA
import os
import json
from datetime import datetime

def load_configuration():
    config_file_path = os.getenv('JIRASYNC_CONFIG', '~/jirasync.conf')
    config_file_path = os.path.expanduser(config_file_path)

    with open(config_file_path, 'r') as config_file:
        config = json.load(config_file)

    # Respect $XDG_DATA_HOME and set default destination_folder
    xdg_data_home = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
    default_destination_folder = os.path.join(xdg_data_home, 'jirasync')

    # Define default values for missing keys
    default_config = {
        'auth_token': None,
        'auth_token_path': None,
        'destination_folder': default_destination_folder,
        'search_queries': [],
        'jira_server': 'https://your-jira-instance',
        'verify_ssl': False,
    }

    # Update configurations with environment variables and defaults
    for key, default_value in default_config.items():
        env_variable = f'JIRASYNC_{key.upper()}'
        config[key] = os.getenv(env_variable, config.get(key, default_value))

    return config

def get_auth_token(config):
    auth_token = config.get('auth_token')
    auth_token_path = config.get('auth_token_path')

    if auth_token_path:
        with open(auth_token_path, 'r') as token_file:
            auth_token = token_file.read().strip()

    return auth_token


def initialize_jira_client(config):
    auth_token = get_auth_token(config)
    jira_server = config['jira_server']
    verify_ssl = config.get('verify_ssl', False)

    options = {
        'server': jira_server,
        'verify': verify_ssl
    }

    return JIRA(options=options, token_auth=(auth_token))

def create_destination_folder(destination_folder):
    os.makedirs(destination_folder, exist_ok=True)

def process_single_issue(client, issue, destination_folder):
    issue_key = issue.key
    date_format = '%Y-%m-%dT%H:%M:%S.%f%z'
    last_updated = datetime.strptime(issue.fields.updated, date_format)

    local_file_path = os.path.join(destination_folder, f'{issue_key}.json')

    if os.path.exists(local_file_path):
        with open(local_file_path, 'r') as local_file:
            local_data = json.load(local_file)
        
        local_last_updated = datetime.strptime(local_data['fields']['updated'], date_format)

        if last_updated <= local_last_updated:
            print(f'Skipping {issue_key} as it is not updated.')
            return

    with open(local_file_path, 'w') as local_file:
        json.dump(client.issue(issue_key).raw, local_file, indent=2)

    print(f'Downloaded and stored {issue_key}.')

def fetch_and_store_issues(client, query, destination_folder, batch_size=50):
    start_at = 0
    total = 0 
    issues = []
    while start_at <= total:
        print(f"total: {total}, start_at: {start_at}")
        results_page = client.search_issues(query, startAt=start_at, maxResults=batch_size, fields=['key', 'updated'])
        if total not in [0, results_page.total]:
            print(f"Results changed? old: {total}, new: {results_page.total}")
        if total == 0 and results_page.total != 0:
            total = results_page.total

        issues.extend(results_page)
        if results_page.isLast:
            break

        start_at += batch_size
    
    for issue in issues:
      process_single_issue(client, issue, destination_folder)

def get_jira_issues(config):
    destination_folder = config['destination_folder']
    search_queries = config['search_queries']

    create_destination_folder(destination_folder)
    client = initialize_jira_client(config)

    for query in search_queries:
        fetch_and_store_issues(client, query, destination_folder)


if __name__ == "__main__":
    configuration = load_configuration()
    get_jira_issues(configuration)
