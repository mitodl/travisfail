A silly little CLI to quickly see the output of a failed Travis build
and understand what parts of the build are failing.

### Why you might want to use it

Have you gotten an email saying the Travis build for your PR is broken?
Of course you have. To see what broke, you need to click links here and there,
wait for the Travis web app to load your job log, then parse through the output 
to see which part of the build failed.

With this CLI, you can just run `travisfail` on your machine with your PR 
branch checked out, and you'll see the individual build steps that failed 
so you know what you need to fix. If the script can't parse the parts of the 
build that failed, you can also look at the raw output.


### Installation

After cloning this repo, you can install the CLI with pip:

```bash
pip install -e path/to/travisfail
```

You'll need to set two environment variables before running commands: `GITHUB_USERNAME` and `GITHUB_TOKEN`
(a [Github API token](https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/))

### Running commands

```bash
cd path/to/some/project/repo
travisfail --help

# Get categorized output for a failed build job that executed
# on the currently checked-out branch. The script will try to determine 
# the repo from the current directory and the PR number from the current
# branch.
travisfail

# Get categorized output for a failed build job that executed
# on the branch for PR #123
travisfail --pr 123

# Get categorized output for a failed build job that executed
# on the branch for PR #123 in the 'someproject' repo
travisfail --pr 123 --repo someproject 

# Get raw output for a failed build job 
# (don't attempt to categorize; takes same arguments as commands above)
travisfail --raw
```
