import re
import json
import requests
from collections import namedtuple

from settings import GITHUB_API_URL, GITHUB_OWNER
from utils import first_or_none, gh_get

# TODO: get working w/ both JS & python errors in same report

FAILED_STATUS = "failure"
ANSI_SPACE_PATTERN = '[\s\x1b\[\d+(\;\d+)?m]+'
#
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
TRAVIS_BUILDS_URL = "https://api.travis-ci.org/builds/{build_id}"
TRAVIS_JOB_LOG_URL = "https://api.travis-ci.org/jobs/{job_id}/log.txt"
#


class ErrorFinder:
    error_title = None
    start_indicator = None
    end_indicator = None
    include_start = False
    include_end = False
    error_if_end_missing = True

    @classmethod
    def get_error_body(cls, string_to_search):
        match = re.search(cls.start_indicator, string_to_search)
        if not match:
            return
        if not cls.end_indicator:
            return match.group()
        compiled_end_indicator = re.compile(cls.end_indicator)
        error_start_pos = match.end() if not cls.include_start else match.start()
        error_end_match = compiled_end_indicator.search(string_to_search, error_start_pos)
        if not error_end_match:
            if cls.error_if_end_missing:
                raise Exception('Could not find the end of the error section: {} (pattern = {})'.format(
                    cls.error_title,
                    cls.end_indicator
                ))
            else:
                return
        error_end_pos = error_end_match.start() if not cls.include_end else error_end_match.end()
        return string_to_search[error_start_pos:error_end_pos].strip()


class FlowErrorFinder(ErrorFinder):
    error_title = "Flow"
    start_indicator = r'\> flow check[\s|\x1b\[31m]+Error\ [^\w]+[\s]*'
    end_indicator = r'Found [\d]+ error[s]?'
    include_start = True
    include_end = True


class JsTestErrorFinder(ErrorFinder):
    error_title = "JS Tests"
    start_indicator = r'{ANSISPACE}[\d]+ passing{ANSISPACE}\([\d\w]+\){ANSISPACE}\d+ failing'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    end_indicator = r'[\s\x1b\[\d+m]+Uploading coverage[\.]+'


class EsLintErrorFinder(ErrorFinder):
    error_title = "ES Lint"
    # A file path after "eslint.js" line means an error was found
    start_indicator = r'> node \./node_modules/eslint/bin/eslint\.js [^\s]+{ANSISPACE}[^\s]+\.js'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    end_indicator = r'[1-9][\d]* problem[s]? \([\d]+ error[s]?, [\d]+ warning[s]?\)'
    include_start = True
    include_end = True


class SassLintErrorFinder(ErrorFinder):
    error_title = "Sass Lint"
    # A file path after "sass-lint.js" line means an error was found
    start_indicator = r'> node \./node_modules/sass-lint/bin/sass-lint\.js .*\s{ANSISPACE}[^\s]+\.scss'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    end_indicator = r'[1-9][\d]* problem[s]? \([\d]+ error[s]?, [\d]+ warning[s]?\)'
    include_start = True
    include_end = True


class NpmFmtErrorFinder(ErrorFinder):
    error_title = "NPM Fmt"
    start_indicator = r'npm{ANSISPACE}ERR!{ANSISPACE}Failed at the [^\s]+ fmt:check script'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )


class PyLintErrorFinder(ErrorFinder):
    error_title = "Python Linting"
    start_indicator = r'=* FAILURES =*{ANSISPACE}_+\s+\[pylint\]'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    end_indicator = r'{ANSISPACE}\-+ coverage'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    include_start = True


class PyTestErrorFinder(ErrorFinder):
    error_title = "Python Tests"
    start_indicator = r'=* FAILURES =*{ANSISPACE}_+\s+[a-zA-Z]+'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    # end_indicator = r'=+ \d+ failed'
    end_indicator = r'{ANSISPACE}\-+ coverage'.format(
        ANSISPACE=ANSI_SPACE_PATTERN
    )
    include_start = True


python_error_finders = [PyTestErrorFinder, PyLintErrorFinder]
js_error_finders = [
    JsTestErrorFinder,
    NpmFmtErrorFinder,
    FlowErrorFinder,
    EsLintErrorFinder,
    SassLintErrorFinder,
]

FailedBuildJob = namedtuple('FailedBuildJob', ['id', 'url', 'env_name', 'result'])
BuildEnv = namedtuple('BuildEnv', ['full_name', 'suite_start_pattern', 'error_finders'])

JS_ERROR_ENV_NAME = 'name=JavaScript'
PY_ERROR_ENV_NAME = 'name=Python'
ENV_MAP = {
    "javascript": BuildEnv(
        full_name=JS_ERROR_ENV_NAME,
        suite_start_pattern=r'\/travis\/js\_tests\.sh',
        error_finders=js_error_finders
    ),
    "python": BuildEnv(
        full_name=PY_ERROR_ENV_NAME,
        suite_start_pattern=r'py\d+ installed',
        error_finders=python_error_finders
    ),
}


class JobLog:
    def __init__(self, raw):
        self.raw = raw
        self._formatted = None

    def format(self, log):
        return log

    @staticmethod
    def trim(log):
        test_suite_start_match = None
        for env in ENV_MAP.values():
            test_suite_start_match = re.search(env.suite_start_pattern, log)
            if test_suite_start_match:
                break
        if not test_suite_start_match:
            raise Exception(
                "Couldn't find the expected starting line of test suite output. Review the raw output instead."
                "\nPatterns tried:\n{}".format(
                    "\n".join([env.suite_start_pattern for env in ENV_MAP.values()])
                )
            )
        return log[test_suite_start_match.start():]

    @property
    def cleaned(self):
        if not self._formatted:
            trimmed_log = self.trim(self.raw)
            self._formatted = self.format(trimmed_log)
        return self._formatted


class TravisJobLog(JobLog):
    def format(self, log):
        return re.sub(r'\r\n', '\n', log)


class FileJobLog(JobLog):
    def format(self, log):
        return re.sub(r'\n\n', '\n', log)


class ErrorReport:
    def __init__(self, env_name):
        self.env_name = env_name
        self.errors = {}

    def __repr__(self):
        return "<{} - env={}, errors={}>".format(
            self.__class__.__name__,
            self.env_name,
            list(self.errors.keys())
        )


def get_env_by_name(env_name):
    env = first_or_none(
        env for env in ENV_MAP.values() if env.full_name == env_name
    )
    if not env:
        raise Exception("No env found with name '{}'".format(env_name))
    return env


def determine_env_from_job_log(job_log):
    for env in ENV_MAP.values():
        if re.search(env.suite_start_pattern, job_log):
            return env.full_name
    raise Exception("Build env could not be determined from the log.")


def get_failed_build_jobs(build_id):
    build_url = TRAVIS_BUILDS_URL.format(build_id=build_id)
    builds_resp = requests.get(build_url)
    failed_jobs = [
        FailedBuildJob(
            id=job_data["id"],
            url=build_url,
            env_name=job_data["config"]["env"],
            result=job_data["result"]
        )
        for job_data in json.loads(builds_resp.content)["matrix"]
        if job_data["result"] == 1
    ]
    return failed_jobs


def get_raw_job_log_from_id(job_id):
    job_log_resp = requests.get(TRAVIS_JOB_LOG_URL.format(job_id=job_id))
    return job_log_resp.content.decode("utf-8")


def get_job_log_from_id(job_id_str):
    raw_job_log = get_raw_job_log_from_id(job_id_str)
    return TravisJobLog(raw=raw_job_log)


def get_job_log_from_file(filepath):
    with open(filepath, 'r') as f:
        raw_job_log = f.read()
    return FileJobLog(raw=raw_job_log)


def get_error_report_from_job_log(job_log, env_name):
    env_report = ErrorReport(env_name)
    env = get_env_by_name(env_name)
    for error_env_finder in env.error_finders:
        error_body = error_env_finder.get_error_body(job_log.cleaned)
        if error_body:
            env_report.errors[error_env_finder.error_title] = error_body
    return env_report


def get_pr_statuses(repo_name, pr_number):
    pr_api_url = "{host}/repos/{owner}/{repo_name}/pulls/{pr_number}".format(
        host=GITHUB_API_URL,
        owner=GITHUB_OWNER,
        repo_name=repo_name,
        pr_number=pr_number
    )
    pr_resp = gh_get(pr_api_url)
    if not pr_resp.ok:
        raise Exception('Request for PR statuses failed\n{}\n{}\n{}'.format(
            pr_api_url, pr_resp.status_code, pr_resp.content.decode("utf-8")
        ))
    pr_data = json.loads(pr_resp.content)
    statuses_url = pr_data["statuses_url"]
    statuses_resp = gh_get(statuses_url)
    return json.loads(statuses_resp.content)


def get_build_id_from_url(url):
    res = re.search(r'/builds/(\d+)', url)
    return None if not res.groups() else res.groups()[0]


def get_failed_pr_build_jobs(repo_name, pr_number):
    statuses_data = get_pr_statuses(repo_name, pr_number)
    failed_statuses = [
        dict(state=status["state"], target_url=status["target_url"])
        for status in statuses_data
        if status["state"] == FAILED_STATUS
    ]
    top_failed_status = first_or_none(failed_statuses)
    if not top_failed_status:
        return []
    build_id = get_build_id_from_url(top_failed_status["target_url"])
    return get_failed_build_jobs(build_id)


def compile_pr_failure_reports(repo_name, pr_number):
    failed_pr_build_jobs = get_failed_pr_build_jobs(repo_name, pr_number)
    build_failure_reports = []
    for failed_build_job in failed_pr_build_jobs:
        job_log = get_job_log_from_id(str(failed_build_job.id))
        error_report = get_error_report_from_job_log(job_log, failed_build_job.env_name)
        if error_report:
            build_failure_reports.append(error_report)
    return build_failure_reports


def compile_failure_report_from_file(filepath):
    job_log = get_job_log_from_file(filepath)
    env_name = determine_env_from_job_log(job_log.raw)
    return get_error_report_from_job_log(job_log, env_name)
