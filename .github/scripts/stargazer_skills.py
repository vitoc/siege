import os
import requests
import json
from datetime import datetime, timedelta, timezone
from github import Github

def get_env_repo():
    repo_env = os.environ.get('GITHUB_REPOSITORY')
    if not repo_env or '/' not in repo_env:
        raise Exception('GITHUB_REPOSITORY env var not set or invalid')
    owner, repo = repo_env.split('/')
    return owner, repo

def get_stargazers(owner, repo, token):
    url = f'https://api.github.com/repos/{owner}/{repo}/stargazers'
    headers = {
        'Accept': 'application/vnd.github.star+json',
        'Authorization': f'token {token}'
    }
    stargazers = []
    page = 1
    while True:
        resp = requests.get(url, headers=headers, params={'per_page': 100, 'page': page})
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        stargazers.extend(data)
        if len(data) < 100:
            break
        page += 1
    return stargazers

def is_recent(starred_at):
    star_time = datetime.strptime(starred_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - star_time <= timedelta(days=1)

def get_user_forks(g, username):
    user = g.get_user(username)
    return [repo for repo in user.get_repos() if repo.fork and (repo.full_name.startswith('skills/') or repo.full_name.startswith('skills-dev/'))]

def get_commit_time_diff(repo):
    commits = list(repo.get_commits())
    if not commits:
        return None
    first_commit = commits[-1]
    last_commit = commits[0]
    if last_commit.commit.message.strip() != 'Congratulations!🎉':
        return None
    diff = last_commit.commit.committer.date - first_commit.commit.committer.date
    return int(diff.total_seconds())

def update_json_file(repo_name, user, time_diff):
    filename = f'{repo_name.replace("/", "-")}.json'
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
    else:
        data = []
    data.append({'user': user, 'time_diff_seconds': time_diff})
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def check_user_recent_skills(g, username):
    try:
        forks = get_user_forks(g, username)
    except Exception:
        return
    for fork in forks:
        commits = list(fork.get_commits())
        if not commits:
            continue
        last_commit = commits[0]
        last_commit_time = last_commit.commit.committer.date.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_commit_time > timedelta(days=1):
            continue
        if last_commit.commit.message.strip() != 'Congratulations!🎉':
            continue
        first_commit = commits[-1]
        diff = last_commit.commit.committer.date - first_commit.commit.committer.date
        update_json_file(fork.full_name, username, int(diff.total_seconds()))

def main():
    token = os.environ.get('GITHUB_TOKEN')
    owner, repo = get_env_repo()
    g = Github(token)
    input_username = os.environ.get('INPUT_USERNAME')
    if input_username:
        check_user_recent_skills(g, input_username)
    else:
        stargazers = get_stargazers(owner, repo, token)
        for s in stargazers:
            starred_at = s.get('starred_at')
            user = s.get('user', {}).get('login')
            if not starred_at or not user:
                continue
            if not is_recent(starred_at):
                continue
            try:
                forks = get_user_forks(g, user)
            except Exception:
                continue
            for fork in forks:
                time_diff = get_commit_time_diff(fork)
                if time_diff is not None:
                    update_json_file(fork.full_name, user, time_diff)

if __name__ == '__main__':
    main()
