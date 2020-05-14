import sys
import click
import json

import api
from utils import get_repo_name, get_pr_number_from_current_branch

# TODO: get raw output working with mult. failed jobs - provide choice

DIVIDER = '#' * 15
LONG_DIVIDER = DIVIDER * 3


@click.command()
@click.option('-r', '--repo', type=str, help='Repo name')
@click.option('-p', '--pr', type=int, help='PR number')
@click.option('-f', '--filepath', type=click.Path(exists=True), help='File path of a job log')
@click.option('--raw', is_flag=True, help='Get raw job log contents only')
@click.option('--gh-statuses', is_flag=True, help='Show Github PR statuses response only (for debugging purposes)')
def cli(repo, pr, filepath, raw, gh_statuses):
    if filepath:
        failure_report = api.compile_failure_report_from_file(filepath)
        print_failure_reports([failure_report], filepath)
        return

    if not repo:
        repo = get_repo_name()
    if not pr:
        pr = get_pr_number_from_current_branch(repo)
    if not filepath and not all([repo, pr]):
        click.echo('Need to pass in --repo and --pr, or --filepath', err=True)
        return

    if raw:
        output_raw_failed_build_log(repo, pr)
    elif gh_statuses:
        click.echo(json.dumps(api.get_pr_statuses(repo, pr)))
    else:
        failure_reports = api.compile_pr_failure_reports(repo, pr)
        print_failure_reports(failure_reports, '{} - PR #{}'.format(repo, pr))


def output_raw_failed_build_log(repo, pr):
    failed_pr_build_jobs = api.get_failed_pr_build_jobs(repo, pr)
    if len(failed_pr_build_jobs) == 0:
        click.echo('No build failures')
        return
    failed_pr_build_job = failed_pr_build_jobs[0]
    sys.stdout.write(api.get_raw_job_log_from_id(str(failed_pr_build_job.id)))


def print_failure_reports(failure_reports, error_source):
    if not failure_reports or not any(failure_reports):
        click.echo('No errors found in the Travis job log(s) (source: {})'.format(error_source))
        return
    for failure_report in failure_reports:
        if failure_report.errors:
            error_types_str = ", ".join(failure_report.errors.keys())
        else:
            error_types_str = "Build failed, but no error sections could be parsed. Review the raw log output."
        click.secho(
            '{}\n{}\nError Env: {}\nErrors: {}\n{}\n'.format(
                LONG_DIVIDER,
                error_source,
                failure_report.env_name,
                error_types_str,
                LONG_DIVIDER
            ),
            fg='green',
            bold=True
        )
        for error_title, error_body in failure_report.errors.items():
            click.secho(
                '{}\nError: {}\n{}\n'.format(DIVIDER, error_title, DIVIDER),
                fg='green',
                bold=True
            )
            click.echo(error_body)
            click.echo('')
