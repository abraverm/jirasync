#!/usr/bin/env python
from jira import JIRA
import logging
import argparse
import os
import sys
import json
import yaml
import hashlib
from datetime import datetime
import frontmatter
from jinja2 import Environment, FileSystemLoader
from jira2markdown import convert
from jira2markdown.elements import MarkupElements
from jira2markdown.markup.base import AbstractMarkup
from jira2markdown.markup.links import Mention
from jinja2.exceptions import TemplateSyntaxError, UndefinedError
from typing import Tuple

from string import punctuation

from pyparsing import (
    CaselessLiteral,
    Char,
    Combine,
    FollowedBy,
    Optional,
    ParserElement,
    ParseResults,
    PrecededBy,
    SkipTo,
    StringEnd,
    StringStart,
    Suppress,
    White,
    Word,
    alphanums,
)


class ObsidianMention(AbstractMarkup):
    def action(self, tokens) -> str:
        username = self.usernames.get(tokens.accountid)
        return f"[[{tokens.accountid}]]" if username is None else f"[[/people/{username}]]"

    @property
    def expr(self) -> ParserElement:
        MENTION = Combine(
            "["
            + Optional(
                SkipTo("|", fail_on="]") + Suppress("|"),
                default="",
            )
            + "~"
            + Optional(CaselessLiteral("accountid:"))
            + Word(alphanums + ":-").set_results_name("accountid")
            + Optional(CaselessLiteral("@redhat.com"))
            + "]",
        )
        return (
            (StringStart() | Optional(PrecededBy(White(), retreat=1), default=" "))
            + MENTION.set_parse_action(self.action)
            + (
                StringEnd()
                | Optional(FollowedBy(White() | Char(punctuation, exclude_chars="[") | MENTION), default=" ")
            )
        )

def parse_args():
    parser = argparse.ArgumentParser(description="Jira Sync Script")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose mode"
    )
    return parser.parse_args()


def configure_logging(destination_folder, log_level, verbose):
    log_file_path = os.path.join(destination_folder, "jirasync.log")

    if verbose:
        log_level = logging.DEBUG

    logging.basicConfig(
        filename=log_file_path,
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add a stream handler for printing to console if in verbose mode
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        logging.getLogger().addHandler(console_handler)


def load_configuration():
    config_file_path = os.getenv("JIRASYNC_CONFIG", "~/.jirasync.conf")
    config_file_path = os.path.expanduser(config_file_path)

    with open(config_file_path, "r") as config_file:
        config = json.load(config_file)

    # Respect $XDG_DATA_HOME and set default destination_folder
    local_share_path = os.path.expanduser("~/.local/share")
    xdg_data_home = os.getenv("XDG_DATA_HOME", local_share_path)
    default_destination_folder = os.path.join(xdg_data_home, "jirasync")

    # Define default values for missing keys
    default_config = {
        "auth_token": None,
        "auth_token_path": None,
        "destination_folder": default_destination_folder,
        "search_queries": [],
        "jira_server": "https://your-jira-instance",
        "verify_ssl": False,
        "log_level": "INFO",
    }

    # Update configurations with environment variables and defaults
    for key, default_value in default_config.items():
        env_variable = f"JIRASYNC_{key.upper()}"
        config[key] = os.getenv(env_variable, config.get(key, default_value))

    if len(config["search_queries"]) == 0:
        logging.warning("No search queries provided, nothing to do")
        sys.exit(0)

    return config


def get_auth_token(config):
    auth_token = config.get("auth_token")
    auth_token_path = config.get("auth_token_path")

    if auth_token_path:
        with open(auth_token_path, "r") as token_file:
            auth_token = token_file.read().strip()

    if auth_token is None:
        logging.error("Missing authentication token")
        sys.exit(1)

    return auth_token


def initialize_jira_client(config):
    auth_token = get_auth_token(config)
    jira_server = config["jira_server"]
    verify_ssl = config.get("verify_ssl", False)

    options = {"server": jira_server, "verify": verify_ssl}

    return JIRA(options=options, token_auth=(auth_token))


def create_destination_folder(destination_folder):
    os.makedirs(destination_folder, exist_ok=True)


def jira2md_filter(value):
    if value is None:
        return ''
    elements = MarkupElements()
    elements.replace(Mention, ObsidianMention)
    return convert(value, elements=elements)


def process_single_issue(client, issue, destination_folder) -> bool:
    issue_key = issue.key
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    last_updated = datetime.strptime(issue.fields.updated, date_format)

    local_file_path = os.path.join(destination_folder, f"{issue_key}.json")

    if os.path.exists(local_file_path):
        with open(local_file_path, "r") as local_file:
            local_data = json.load(local_file)

        local_last_updated = datetime.strptime(
            local_data["fields"]["updated"], date_format
        )

        if last_updated <= local_last_updated:
            logging.debug(f"Skipping {issue_key} as it is not updated.")
            return False

    with open(local_file_path, "w") as local_file:
        json.dump(client.issue(issue_key).raw, local_file, indent=2)

    logging.info(f"Updated {issue_key}.")
    return True


def fetch_and_store_issues(client, query, destination_folder, batch_size=50) -> list:
    logging.info(f"Processing query '{query}")
    start_at = 0
    total = 0
    results = []
    while start_at <= total:
        logging.debug(f"total: {total}, start_at: {start_at}")
        results_page = client.search_issues(
            query, startAt=start_at, maxResults=batch_size, fields=["key", "updated"]
        )
        if total not in [0, results_page.total]:
            logging.warning(f"Results changed? old: {total}, new: {results_page.total}")
        if total == 0 and results_page.total != 0:
            total = results_page.total

        results.extend(results_page)
        if results_page.isLast:
            break

        start_at += batch_size

    issues = []
    for result in results:
        issues.append(result.key)
        process_single_issue(client, result, destination_folder)

    logging.info(f"Finished query '{query}")
    return issues


def get_jira_issues(config, args) -> list:
    destination_folder = os.path.expanduser(config["destination_folder"])
    search_queries = config["search_queries"]

    create_destination_folder(destination_folder)
    configure_logging(destination_folder, config["log_level"], args.verbose)
    client = initialize_jira_client(config)

    issues = []
    for query in search_queries:
        fetched = fetch_and_store_issues(client, query, destination_folder)
        issues.extend(fetched)

    return issues

def calculate_md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def update_markdown_files(config: dict, issues: list):
    # TODO: Improve this part with click or something
    if config.get("markdown_destination") is None:
        logging.info("markdown destination folder is undefined, skipping")
        return

    if config.get("markdown_template") is None:
        logging.info("markdown template is undefined, skipping")
        return

    markdown_destination = os.path.expanduser(config["markdown_destination"])
    markdown_template = os.path.expanduser(config["markdown_template"])
    template_name = os.path.basename(markdown_template)
    template_folder = os.path.dirname(markdown_template)
    destination_folder = os.path.expanduser(config["destination_folder"])

    create_destination_folder(markdown_destination)

    env = Environment(loader=FileSystemLoader(template_folder))
    env.filters['jira2md'] = jira2md_filter
    env.filters['yaml'] = yaml.safe_dump
    try:
        template = env.get_template(template_name)
        version = calculate_md5(markdown_template)
    except TemplateSyntaxError as e:
        logging.error(f"Failed loading the template {template_name}:\n{e}")
        return

    for issue in issues:
        with open(os.path.join(destination_folder, f"{issue}.json")) as f:
            issue_data = json.load(f)

        if os.path.exists(os.path.join(markdown_destination, f"{issue}.md")):
            with open(os.path.join(markdown_destination, f"{issue}.md")) as f:
                old_content = frontmatter.load(f)

            metadata = old_content.metadata
            tmp = metadata.copy()
            for key in tmp.keys():
                if key.startswith("jira"):
                    metadata.pop(key)

            if metadata.get("template_version", "") != version:
                output = template.render(metadata=metadata, version=version, jira=issue_data)
            else:
                logging.debug(f"{issue}.md is current")
                continue
        else:
            output = template.render(version=version, jira=issue_data)

        with open(os.path.join(markdown_destination, f"{issue}.md"), "w") as f:
            f.write(output)


def main():
    args = parse_args()
    configuration = load_configuration()
    issues = get_jira_issues(configuration, args)
    update_markdown_files(configuration, issues)


if __name__ == "__main__":
    main()
