import re
import os
import subprocess
import requests
from functools import wraps, partial

import settings


def needs_env(*env_var_names):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            missing_vars = list(filter(
                lambda env_var_name: not getattr(settings, env_var_name, None),
                env_var_names
            ))
            assert not missing_vars, "Need to set env variables: {}".format(
                ", ".join(missing_vars)
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


gh_get = needs_env("GITHUB_TOKEN")(
    partial(requests.get, headers={'Authorization': 'token {}'.format(settings.GITHUB_TOKEN)})
)


def current_dir_name():
    return os.path.split(os.getcwd())[1]


def get_repo_name():
    output = (
        subprocess
        .Popen("git config --get remote.origin.url", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        .stdout
        .readlines()[0]
        .decode()
        .strip()
    )
    if not output:
        raise Exception("Could not get the remote repo URL. Current directory might not be a git repository.")
    return re.search(r'/([^/]*)\.git$', output).group(1)


def get_current_branch():
    output = (
        subprocess
        .Popen("git rev-parse --abbrev-ref HEAD", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        .stdout
        .readlines()[0]
        .decode()
    )
    if output.startswith("fatal"):
        raise Exception("Current directory is not a git repository.")
    return output.strip()


def get_pr_number_from_current_branch(repo=None):
    current_branch = get_current_branch()
    if not current_branch:
        return None
    if not repo:
        repo = get_repo_name()
    resp = gh_get(
        "{url}/repos/{owner}/{repo}/pulls?head={owner}:{branch}".format(
            url=settings.GITHUB_API_URL,
            owner=settings.GITHUB_OWNER,
            repo=repo,
            branch=current_branch
        )
    )
    if not resp.ok:
        raise Exception(
            "Github API request to get PR info failed: {}\n{}".format(resp.status_code, resp.content)
        )
    resp_json = resp.json()
    if len(resp_json) == 0:
        raise Exception("No PR found on Github for the current branch ({}).".format(current_branch))
    return resp_json[0]["number"]


def first_or_none(iterable):
    try:
        return next(x for x in iterable)
    except StopIteration:
        return None


def first_group_or_none(re_search_result):
    if re_search_result is None:
        return None
    return first_or_none(re_search_result.groups())
