A silly little CLI to quickly see the output of a failed Travis build
and understand what parts of the build are failing.

### Installation

After cloning this repo, you can install the CLI with pip:

```bash
pip install -e path/to/travisfail
```

### Running commands

```bash
cd path/to/some/project/repo
travisfail --help

# Get categorized output for a failed build job that executed
# on the currently checked-out branch
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
