# github-issue-extract

There are two scripts in this repo that fetch issues from Github.

- git_issues_pull.py retrieves issues and converts them into a usable csv for analysis / business insights etc. 

- git_board_extract.py retrieves issues and project board data and ships them to Elasticsearch.

To run the script - clone the repo or download the .py files to your local machine.

Read through the script and populate the parameters as required. 

## To run git_board_extract.py:

1. Populate variables in the script - read through comments in detail before proceeding.
2. pip install -r requirements.txt
3. Create the index in the target cluster (issues_view.txt)
4. Run python git_project_board_extract.py 
5. Import the export.ndjson via Saved Objects
6. Establish a cron job to run on a schedule i.e to run every day at 12:00 AM:

```
0 0 * * * python /path_to_file/git_project_board_extract.py
```


