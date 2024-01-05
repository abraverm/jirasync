---
{% if metadata is defined -%}
    {{ metadata | yaml(indent=2) }}
{% endif %}
jira/key: {{ jira.key }}
jira/priority: {{ jira.fields.priority.name }}
jira/status: {{ jira.fields.status.name }}
jira/components:
{%- for c in jira.fields.components %}
  - {{ c.name }}
{% endfor -%}
{%- set creator = jira.fields.creator.emailAddress.split('@')[0] %}
jira/creator: [[/people/{{ creator }}]]
jira/type: {{ jira.fields.issuetype.name }}
jira/project_key: {{ jira.fields.project.key }}
jira/project_name: {{ jira.fields.project.name }}
---
# {{ jira.fields.summary }}

{{ jira.fields.description | jira2md }}

## Related

| link | relation | type | status | priority | summary |
|------|----------|------|--------|----------|---------|
{% for link in jira.fields.issuelinks -%}
    {% set direction = '' -%}
    {% if "inwardIssue" in link -%}
       {% set direction = "inwardIssue" -%}
       {% set relation = link.type.inward -%}
    {% else -%}
       {% set direction = "outwardIssue" -%}
       {% set relation = link.type.outward -%}
    {% endif -%}
    {% set key = link[direction].key -%}
    {% set issue_type = link[direction].fields.issuetype.name -%}
    {% set status = link[direction].fields.status.name -%}
    {% set priority = link[direction].fields.priority.name -%}
    {% set summary = link[direction].fields.summary -%}
| [[/jira/{{ key }}]] | {{ relation }} | {{ issue_type }} | {{ status }} | {{ priority }} | {{ summary }} |
{% endfor %}

## Comments
{% for comment in jira.fields.comment.comments %}
> [!comment]
> comment/author:: [[/people/{{ comment.author.emailAddress.split('@')[0] }}|{{ comment.author.displayName }}]]
> comment/created:: {{ comment.created }}
{%- if comment.visibility is defined %}
> comment/visibility:: {{ comment.visibility.value }}
{%- endif -%}
{%- set content = comment.body | jira2md %}
>
{% for line in content.splitlines() -%}
> {{ line }} 
{% endfor -%}

{% endfor -%}
